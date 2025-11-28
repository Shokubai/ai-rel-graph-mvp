"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import { useListDriveFiles, useSearchDriveFiles } from "@/hooks/useGoogleDrive";
import { useState } from "react";

export function DriveFileBrowser() {
  const { data: session, status } = useSession();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolderId, setSelectedFolderId] = useState<string>();

  // List files from current folder
  const {
    data: filesData,
    isLoading,
    error,
  } = useListDriveFiles(selectedFolderId);

  // Search functionality
  const { data: searchResults, isLoading: isSearching } =
    useSearchDriveFiles(searchQuery);

  // Show sign in button if not authenticated
  if (status === "unauthenticated") {
    return (
      <div className="p-4">
        <h2 className="text-xl font-bold mb-4">Google Drive Browser</h2>
        <p className="mb-4">Sign in to access your Google Drive files</p>
        <button
          onClick={() => signIn("google")}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Sign in with Google
        </button>
      </div>
    );
  }

  // Show loading state while checking auth
  if (status === "loading") {
    return <div className="p-4">Loading...</div>;
  }

  // Check for token error
  if (session?.error === "RefreshAccessTokenError") {
    return (
      <div className="p-4">
        <p className="text-red-600 mb-4">
          Session expired. Please sign in again.
        </p>
        <button
          onClick={() => signIn("google")}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Sign in
        </button>
      </div>
    );
  }

  const displayFiles = searchQuery ? searchResults?.files : filesData?.files;

  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Google Drive Files</h2>
        <button
          onClick={() => signOut()}
          className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
        >
          Sign out
        </button>
      </div>

      {/* Search bar */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-4 py-2 border rounded"
        />
      </div>

      {/* Loading state */}
      {(isLoading || isSearching) && <div>Loading files...</div>}

      {/* Error state */}
      {error && (
        <div className="text-red-600">Error loading files: {error.message}</div>
      )}

      {/* File list */}
      {displayFiles && displayFiles.length > 0 && (
        <div className="space-y-2">
          {displayFiles.map((file) => (
            <div
              key={file.id}
              className="p-4 border rounded hover:bg-gray-50 cursor-pointer"
              onClick={() => {
                if (file.mimeType === "application/vnd.google-apps.folder") {
                  setSelectedFolderId(file.id);
                  setSearchQuery("");
                }
              }}
            >
              <div className="font-medium">{file.name}</div>
              <div className="text-sm text-gray-600">
                {file.mimeType.includes("folder") ? "Folder" : "File"} •{" "}
                {new Date(file.modifiedTime).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {displayFiles && displayFiles.length === 0 && (
        <div className="text-gray-500">No files found</div>
      )}

      {/* Back button if in a folder */}
      {selectedFolderId && (
        <button
          onClick={() => setSelectedFolderId(undefined)}
          className="mt-4 px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
        >
          ← Back to root
        </button>
      )}
    </div>
  );
}
