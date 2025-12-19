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
    console.log("[PROXY] GET /api/graph/documents - API_BASE:", API_BASE);

    // Get auth token
    const token = await getAuthToken(req);
    console.log("[PROXY] Got auth token, first 20 chars:", token.substring(0, 20));

    // Fetch documents from backend
    const backendUrl = `${API_BASE}/api/v1/graph/documents`;
    console.log("[PROXY] Calling backend:", backendUrl);

    const response = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    console.log("[PROXY] Backend response status:", response.status);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error("[PROXY] Backend error:", errorData);
      return NextResponse.json(
        { error: errorData.detail || "Failed to fetch documents" },
        { status: response.status }
      );
    }

    const data = await response.json();
    console.log("[PROXY] Success, returning", data.documents?.length || 0, "documents");
    return NextResponse.json(data);
  } catch (error) {
    console.error("[PROXY] Error in proxy route:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    );
  }
}
