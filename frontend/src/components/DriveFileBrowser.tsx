"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import { useListDriveFiles, useSearchDriveFiles } from "@/hooks/useGoogleDrive";
import {
  useStartProcessing,
  useProcessingStatus,
} from "@/hooks/useFileProcessing";
import {
  useGenerateGraph,
  useGraphGenerationStatus,
} from "@/hooks/useGraph";
import { useState, useEffect } from "react";

interface DriveFileBrowserProps {
  onGraphGenerated?: () => void;
}

export function DriveFileBrowser({ onGraphGenerated }: DriveFileBrowserProps) {
  const { data: session, status } = useSession();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolderId, setSelectedFolderId] = useState<string>();
  const [processingTaskId, setProcessingTaskId] = useState<string>();
  const [graphTaskId, setGraphTaskId] = useState<string>();

  // List files from current folder
  const {
    data: filesData,
    isLoading,
    error,
  } = useListDriveFiles(selectedFolderId);

  // Search functionality
  const { data: searchResults, isLoading: isSearching } =
    useSearchDriveFiles(searchQuery);

  // Processing functionality
  const startProcessing = useStartProcessing();
  const { data: processingStatus } = useProcessingStatus(processingTaskId);

  // Graph generation functionality
  const generateGraph = useGenerateGraph();
  const { data: graphStatus } = useGraphGenerationStatus(graphTaskId);

  // Handle start processing
  const handleStartProcessing = async () => {
    try {
      const result = await startProcessing.mutateAsync({
        folder_id: selectedFolderId,
      });
      setProcessingTaskId(result.task_id);
    } catch (error) {
      console.error("Failed to start processing:", error);
    }
  };

  // Handle graph generation
  const handleGenerateGraph = async () => {
    try {
      const result = await generateGraph.mutateAsync({
        documents_file: "processed_files/extracted_documents.json",
        use_top_k_similarity: true,
        top_k_neighbors: 3,
        min_similarity: 0.3,
      });
      setGraphTaskId(result.task_id);
    } catch (error) {
      console.error("Failed to generate graph:", error);
    }
  };

  // Auto-trigger graph generation when processing completes successfully
  useEffect(() => {
    if (
      processingStatus?.state === "SUCCESS" &&
      !graphTaskId &&
      !generateGraph.isPending
    ) {
      handleGenerateGraph();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processingStatus?.state]);

  // Notify parent when graph generation completes
  useEffect(() => {
    if (graphStatus?.state === "SUCCESS" && onGraphGenerated) {
      onGraphGenerated();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphStatus?.state]);

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

      {/* Action Buttons */}
      <div className="mb-4 flex gap-2">
        <button
          onClick={handleStartProcessing}
          disabled={startProcessing.isPending || processingStatus?.state === "PROCESSING"}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {startProcessing.isPending
            ? "Starting..."
            : processingStatus?.state === "PROCESSING"
            ? "Processing..."
            : "Process Files"}
        </button>
        <button
          onClick={handleGenerateGraph}
          disabled={generateGraph.isPending || graphStatus?.state === "PROCESSING"}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {generateGraph.isPending
            ? "Starting..."
            : graphStatus?.state === "PROCESSING"
            ? "Generating..."
            : "Generate Graph"}
        </button>
        <span className="ml-2 text-sm text-gray-600 self-center">
          {selectedFolderId ? "Process files in current folder" : "Process all Drive files"}
        </span>
      </div>

      {/* Processing Status */}
      {processingStatus && (
        <div className="mb-4 p-4 border rounded bg-gray-50">
          <h3 className="font-bold mb-2">Processing Status</h3>

          {processingStatus.state === "PENDING" && (
            <div className="text-gray-600">Waiting to start...</div>
          )}

          {processingStatus.state === "PROCESSING" && (
            <div>
              <div className="mb-2">
                <span className="font-medium">Progress: </span>
                {processingStatus.current}/{processingStatus.total} files
              </div>
              <div className="mb-2">
                <span className="font-medium">Current file: </span>
                {processingStatus.current_file}
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-green-600 h-2 rounded-full transition-all"
                  style={{
                    width: `${((processingStatus.current || 0) / (processingStatus.total || 1)) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          {processingStatus.state === "SUCCESS" && processingStatus.result && (
            <div className="text-green-600">
              <div className="font-bold mb-2">✓ Processing Complete!</div>
              <div className="text-sm space-y-1">
                <div>Files processed: {processingStatus.result.stats.processed}</div>
                <div>Total words: {processingStatus.result.stats.total_words.toLocaleString()}</div>
                <div>
                  Average words per file: {processingStatus.result.stats.average_words.toLocaleString()}
                </div>
                {processingStatus.result.stats.failed > 0 && (
                  <div className="text-red-600">
                    Failed: {processingStatus.result.stats.failed} files
                  </div>
                )}
              </div>
            </div>
          )}

          {processingStatus.state === "FAILURE" && (
            <div className="text-red-600">
              <div className="font-bold">✗ Processing Failed</div>
              <div className="text-sm mt-1">{processingStatus.error}</div>
            </div>
          )}
        </div>
      )}

      {/* Graph Generation Status */}
      {graphStatus && (
        <div className="mb-4 p-4 border rounded bg-blue-50">
          <h3 className="font-bold mb-2">Graph Generation Status</h3>

          {graphStatus.state === "PENDING" && (
            <div className="text-gray-600">Waiting to start graph generation...</div>
          )}

          {graphStatus.state === "PROCESSING" && (
            <div>
              <div className="mb-2 text-blue-600">
                Generating knowledge graph...
              </div>
              {graphStatus.status && (
                <div className="text-sm text-gray-700">{graphStatus.status}</div>
              )}
            </div>
          )}

          {graphStatus.state === "SUCCESS" && graphStatus.result && (
            <div className="text-green-600">
              <div className="font-bold mb-2">✓ Graph Generated!</div>
              <div className="text-sm space-y-1">
                <div>Nodes: {graphStatus.result.stats.total_nodes}</div>
                <div>Edges: {graphStatus.result.stats.total_edges}</div>
              </div>
            </div>
          )}

          {graphStatus.state === "FAILURE" && (
            <div className="text-red-600">
              <div className="font-bold">✗ Graph Generation Failed</div>
              <div className="text-sm mt-1">{graphStatus.error}</div>
            </div>
          )}
        </div>
      )}

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
                {(file.mimeType || "").includes("folder") ? "Folder" : "File"} •{" "}
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
