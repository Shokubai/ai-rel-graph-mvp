import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token;

    // Check for token refresh errors
    if (token?.error === "RefreshAccessTokenError") {
      const url = new URL("/", req.url);
      url.searchParams.set("error", "SessionExpired");
      return NextResponse.redirect(url);
    }

    return NextResponse.next();
  },
  {
    secret: process.env.NEXTAUTH_SECRET,
    callbacks: {
      authorized: ({ token }) => {
        // Allow access if token exists and no refresh error
        if (!token) return false;
        if (token.error === "RefreshAccessTokenError") return false;
        return true;
      },
    },
    pages: {
      signIn: "/",
    },
  },
);

export const config = {
  // Protect all routes except public ones
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (all API routes - auth, graph proxies, etc.)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.png$).*)",
  ],
};
