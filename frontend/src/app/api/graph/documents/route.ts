import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { SignJWT } from "jose";
import { authOptions } from "@/lib/auth";

// Use INTERNAL_API_URL for Docker, NEXT_PUBLIC_API_URL for Vercel
const API_BASE =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export async function GET() {
  try {
    // Get session directly (no HTTP request needed)
    const session = await getServerSession(authOptions);

    if (!session?.user?.id) {
      return NextResponse.json(
        { error: "Unauthorized", details: "No session found" },
        { status: 401 }
      );
    }

    // Generate JWT token directly
    if (!process.env.NEXTAUTH_SECRET) {
      return NextResponse.json(
        { error: "Server configuration error", details: "NEXTAUTH_SECRET not set" },
        { status: 500 }
      );
    }

    const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET);
    const token = await new SignJWT({
      sub: session.user.id,
      email: session.user.email,
      name: session.user.name,
    })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("1h")
      .sign(secret);

    // Fetch documents from backend
    const backendUrl = `${API_BASE}/api/v1/graph/documents`;

    const response = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorData;
      try {
        errorData = JSON.parse(errorText);
      } catch {
        errorData = { detail: errorText };
      }
      return NextResponse.json(
        { error: errorData.detail || "Failed to fetch documents", backendStatus: response.status },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("[PROXY] Error:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      },
      { status: 500 }
    );
  }
}
