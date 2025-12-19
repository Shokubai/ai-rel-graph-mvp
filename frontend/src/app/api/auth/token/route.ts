import { getServerSession } from "next-auth";
import { NextResponse } from "next/server";
import { authOptions } from "@/lib/auth";
import { SignJWT } from "jose";

/**
 * GET /api/auth/token
 * Returns a signed JWT token for authenticating with the backend API
 */
export async function GET() {
  const session = await getServerSession(authOptions);

  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Check for token refresh errors
  if (session.error === "RefreshAccessTokenError") {
    return NextResponse.json(
      { error: "Token expired. Please sign in again." },
      { status: 401 },
    );
  }

  try {
    const payload = {
      sub: session.user.id,
      email: session.user.email,
      name: session.user.name,
    };

    if (!process.env.NEXTAUTH_SECRET) {
      throw new Error("NEXTAUTH_SECRET is required");
    }
    const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!);

    const token = await new SignJWT(payload)
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("1h")
      .sign(secret);

    return NextResponse.json({ token });
  } catch {
    console.error("Error signing JWT");
    return NextResponse.json(
      { error: "Failed to generate token" },
      { status: 500 },
    );
  }
}
