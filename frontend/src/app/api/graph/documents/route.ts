import { NextRequest, NextResponse } from "next/server";

// Use INTERNAL_API_URL for server-side requests (Docker network)
const API_BASE = process.env.INTERNAL_API_URL || "http://localhost:8000";

/**
 * Get JWT token from backend auth endpoint
 */
async function getAuthToken(req: NextRequest): Promise<string> {
  const tokenResponse = await fetch(
    `${req.nextUrl.origin}/api/auth/token`,
    {
      headers: {
        cookie: req.headers.get("cookie") || "",
      },
    }
  );

  if (!tokenResponse.ok) {
    throw new Error("Failed to get authentication token");
  }

  const data = await tokenResponse.json();
  return data.token;
}

export async function GET(req: NextRequest) {
  try {
    // Get auth token
    const token = await getAuthToken(req);

    // Fetch documents from backend
    const response = await fetch(`${API_BASE}/api/v1/graph/documents`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || "Failed to fetch documents" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching documents:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
