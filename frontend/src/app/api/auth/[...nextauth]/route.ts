import NextAuth, { NextAuthOptions } from "next-auth";
import { JWT } from "next-auth/jwt";
import GoogleProvider from "next-auth/providers/google";
import { z } from "zod";

// Schema for validating session update data from client
const sessionUpdateSchema = z.object({
  // Only allow updating specific safe fields
  user: z
    .object({
      name: z.string().max(255).optional(),
      image: z.string().max(500).url().optional(),
    })
    .strict()
    .optional(),
  // Explicitly reject any attempts to update sensitive fields
  accessToken: z.never().optional(),
  error: z.never().optional(),
});

// add on to this from https://next-auth.js.org/configuration/options
export const authOptions: NextAuthOptions = {
  // Secret for signing JWTs
  secret: process.env.NEXTAUTH_SECRET,
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
      authorization: {
        params: {
          // Request Google Drive API scopes
          scope: [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
          ].join(" "),
          // Request offline access to get refresh token
          access_type: "offline",
          prompt: "consent",
        },
      },
    }),
  ],
  cookies: {
    sessionToken: {
      name: 'next-auth.session-token',
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
      },
    },
  },
  callbacks: {
    async jwt({ token, user, account, trigger }) {
      if (trigger === "signIn" || trigger === "signUp") {
        // Store access token and refresh token on sign in/sign up
        if (account) {
          token.accessToken = account.access_token;
          token.refreshToken = account.refresh_token;
          token.accessTokenExpires = account.expires_at;

          // Sync user tokens
          if (user) {
            try {
              const apiUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
              await fetch(
                `${apiUrl}/api/v1/users/sync`,
                {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    "X-Internal-Key": process.env.NEXTAUTH_SECRET || "",
                  },
                  body: JSON.stringify({
                    google_id: user.id,
                    email: user.email,
                    name: user.name,
                    google_access_token: account.access_token,
                    google_refresh_token: account.refresh_token,
                    google_token_expires_at: account.expires_at
                      ? new Date(account.expires_at * 1000).toISOString()
                      : null,
                  }),
                },
              );
            } catch (error) {
              console.error("Failed to sync user tokens to backend:", error);
            }
          }
        }

        // Store user info on initial sign in
        if (user) {
          token.id = user.id;
          token.email = user.email;
        }

        // Log signup events for tracking
        if (trigger === "signUp") {
          console.log("New user signed up:", user?.email);
        }

        return token;
      }

      // Return previous token if the access token has not expired yet
      if (
        token.accessTokenExpires &&
        Date.now() < (token.accessTokenExpires as number) * 1000
      ) {
        return token;
      }

      // Access token has expired, try to update it
      return refreshAccessToken(token);
    },
    async session({ session, token, trigger, newSession }) {
      session.error = token.error as string;

      // Set user ID from token
      if (token.id) {
        session.user.id = token.id;
      }

      // Handle session updates from client
      if (trigger === "update" && newSession) {
        // Validate client-sent data
        const validation = sessionUpdateSchema.safeParse(newSession);

        if (!validation.success) {
          console.error("Invalid session update data");
          return session;
        }

        // Merge validated data
        const validatedData = validation.data;
        if (validatedData.user) {
          session.user = {
            ...session.user,
            ...validatedData.user,
          };
        }

        console.log("Session updated successfully:", validatedData);
      }

      return session;
    },
  },
};

async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    if (!token.refreshToken) {
      return token;
    }

    const url =
      "https://oauth2.googleapis.com/token?" +
      new URLSearchParams({
        client_id: process.env.GOOGLE_CLIENT_ID || "",
        client_secret: process.env.GOOGLE_CLIENT_SECRET || "",
        grant_type: "refresh_token",
        refresh_token: token.refreshToken,
      });

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      method: "POST",
    });

    const refreshedTokens = await response.json();

    if (!response.ok) {
      throw refreshedTokens;
    }

    const newToken = {
      ...token,
      accessToken: refreshedTokens.access_token,
      accessTokenExpires: Date.now() + refreshedTokens.expires_in * 1000,
      refreshToken: refreshedTokens.refresh_token ?? token.refreshToken,
    };

    // Sync refreshed token to backend
    if (token.id && token.email) {
      try {
        const apiUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        await fetch(
          `${apiUrl}/api/v1/users/sync`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Internal-Key": process.env.NEXTAUTH_SECRET || "",
            },
            body: JSON.stringify({
              google_id: token.id,
              email: token.email,
              name: token.name,
              google_access_token: newToken.accessToken,
              google_refresh_token: newToken.refreshToken,
              google_token_expires_at: new Date(
                newToken.accessTokenExpires as number,
              ).toISOString(),
            }),
          },
        );
      } catch (error) {
        console.error("Failed to sync refreshed tokens to backend:", error);
      }
    }

    return newToken;
  } catch {
    console.error("Error refreshing access token");
    return {
      ...token,
      error: "RefreshAccessTokenError",
    };
  }
}

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
