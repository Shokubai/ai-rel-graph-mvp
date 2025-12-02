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

export async function DELETE(req: NextRequest) {
  try {
    // Get auth token
    const token = await getAuthToken(req);

    // Delete all user data from backend
    const response = await fetch(`${API_BASE}/api/v1/graph/documents/delete-all`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || "Failed to delete all data" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error deleting all data:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
