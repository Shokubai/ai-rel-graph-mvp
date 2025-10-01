import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export", // Enable static HTML export
  images: {
    unoptimized: true, // Required for static export
  },
  // Optional: add base path if deploying to subdirectory
  // basePath: '/app',

  // API URL from environment
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000",
  },
};

export default nextConfig;
