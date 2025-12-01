"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import axios, { AxiosError } from "axios";
import { GraphNode, GraphEdge } from "@/hooks/useGraph";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Get JWT token for backend authentication
 */
async function getAuthToken(): Promise<string> {
  const response = await fetch("/api/auth/token");
  if (!response.ok) {
    throw new Error("Failed to get authentication token");
  }
  const data = await response.json();
  return data.token;
}

interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime?: string;
  size?: string;
  webViewLink?: string;
  thumbnailLink?: string;
  parents?: string[];
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, unknown>;
}

interface FileExplorerProps {
  onProcessingStart: (taskId: string) => void;
  onGraphDataUpload: (graphData: GraphData) => void;
}

export function FileExplorer({ onProcessingStart, onGraphDataUpload }: FileExplorerProps) {
  const { data: session } = useSession();
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [folderPath, setFolderPath] = useState<{ id: string | null; name: string }[]>([
    { id: null, name: "My Drive" },
  ]);

  const loadFiles = useCallback(async (folderId: string | null) => {
    if (!session) return;

    setLoading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const params: Record<string, string> = {};
      if (folderId) {
        params.folderId = folderId;
      }

      const response = await axios.get(`${API_BASE}/api/v1/drive/files`, {
        params,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      setFiles(response.data.files || []);
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>;
      console.error("Failed to load files:", err);
      setError(axiosError.response?.data?.detail || "Failed to load files from Google Drive");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (session) {
      loadFiles(currentFolder);
    }
  }, [session, currentFolder, loadFiles]);

  const handleFolderClick = (file: DriveFile) => {
    if (file.mimeType === "application/vnd.google-apps.folder") {
      setCurrentFolder(file.id);
      setFolderPath([...folderPath, { id: file.id, name: file.name }]);
    }
  };

  const handleBreadcrumbClick = (index: number) => {
    const folder = folderPath[index];
    setCurrentFolder(folder.id);
    setFolderPath(folderPath.slice(0, index + 1));
  };

  const toggleFileSelection = (fileId: string) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(fileId)) {
      newSelected.delete(fileId);
    } else {
      newSelected.add(fileId);
    }
    setSelectedFiles(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(files.map((f) => f.id)));
    }
  };

  const handleProcessFiles = async () => {
    if (selectedFiles.size === 0) {
      setError("Please select at least one file or folder to process");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const response = await axios.post(
        `${API_BASE}/api/v1/processing/start`,
        {
          file_ids: Array.from(selectedFiles),
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      onProcessingStart(response.data.task_id);
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>;
      console.error("Failed to start processing:", err);
      setError(axiosError.response?.data?.detail || "Failed to start file processing");
      setLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const graphData = JSON.parse(text) as GraphData;

      // Validate graph data structure
      if (!graphData.nodes || !graphData.edges) {
        throw new Error("Invalid graph data format. Must contain 'nodes' and 'edges'.");
      }

      onGraphDataUpload(graphData);
    } catch (err) {
      const error = err as Error;
      console.error("Failed to upload graph data:", err);
      setError(error.message || "Failed to upload graph data");
    }
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType === "application/vnd.google-apps.folder") {
      return "📁";
    } else if (mimeType.includes("document")) {
      return "📄";
    } else if (mimeType.includes("spreadsheet")) {
      return "📊";
    } else if (mimeType.includes("presentation")) {
      return "📽️";
    } else if (mimeType.includes("pdf")) {
      return "📕";
    }
    return "📎";
  };

  return (
    <div className="w-full h-full bg-gray-900 p-8 overflow-auto">
      <div className="max-w-6xl mx-auto">
        <div className="bg-gray-950 border border-gray-800 rounded-lg shadow-xl">
          {/* Header */}
          <div className="p-6 border-b border-gray-800">
            <h1 className="text-3xl font-bold text-white mb-2">Google Drive File Explorer</h1>
            <p className="text-gray-400">
              Select files and folders from your Google Drive to process and create a knowledge graph
            </p>
          </div>

          {/* Upload Existing Graph Section */}
          <div className="p-6 border-b border-gray-800 bg-gray-900/50">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white mb-1">Already have a graph?</h2>
                <p className="text-sm text-gray-400">
                  Upload an existing graph_data.json file to skip processing
                </p>
              </div>
              <label className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors cursor-pointer font-medium">
                Upload Graph JSON
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="mx-6 mt-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
              {error}
            </div>
          )}

          {/* Breadcrumb Navigation */}
          <div className="p-6 border-b border-gray-800">
            <div className="flex items-center gap-2 text-sm">
              {folderPath.map((folder, index) => (
                <div key={folder.id || "root"} className="flex items-center gap-2">
                  {index > 0 && <span className="text-gray-600">/</span>}
                  <button
                    onClick={() => handleBreadcrumbClick(index)}
                    className="text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    {folder.name}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* File List */}
          <div className="p-6">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : files.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p className="text-lg">No files found in this folder</p>
              </div>
            ) : (
              <>
                {/* Select All */}
                <div className="mb-4 pb-4 border-b border-gray-800">
                  <label className="flex items-center gap-3 cursor-pointer hover:bg-gray-800 p-3 rounded-lg transition-colors">
                    <input
                      type="checkbox"
                      checked={selectedFiles.size === files.length && files.length > 0}
                      onChange={toggleSelectAll}
                      className="w-5 h-5 text-blue-600 border-gray-600 rounded focus:ring-blue-500 bg-gray-700"
                    />
                    <span className="font-semibold text-white">
                      Select All ({files.length} items)
                    </span>
                  </label>
                </div>

                {/* File List */}
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {files.map((file) => (
                    <div
                      key={file.id}
                      className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
                        selectedFiles.has(file.id)
                          ? "bg-blue-900/30 border border-blue-700"
                          : "hover:bg-gray-800 border border-transparent"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedFiles.has(file.id)}
                        onChange={() => toggleFileSelection(file.id)}
                        className="w-5 h-5 text-blue-600 border-gray-600 rounded focus:ring-blue-500 bg-gray-700"
                      />
                      <span className="text-2xl">{getFileIcon(file.mimeType)}</span>
                      <div className="flex-1 min-w-0">
                        {file.mimeType === "application/vnd.google-apps.folder" ? (
                          <button
                            onClick={() => handleFolderClick(file)}
                            className="text-blue-400 hover:text-blue-300 font-medium text-left truncate block w-full"
                          >
                            {file.name}
                          </button>
                        ) : (
                          <span className="text-white font-medium truncate block">
                            {file.name}
                          </span>
                        )}
                        <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                          <span>{file.mimeType.split(".").pop()}</span>
                          {file.modifiedTime && (
                            <span>
                              Modified: {new Date(file.modifiedTime).toLocaleDateString()}
                            </span>
                          )}
                          {file.size && <span>{(parseInt(file.size) / 1024).toFixed(0)} KB</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Action Buttons */}
          <div className="p-6 border-t border-gray-800 bg-gray-900/50">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-400">
                {selectedFiles.size} file{selectedFiles.size !== 1 ? "s" : ""} selected
              </div>
              <button
                onClick={handleProcessFiles}
                disabled={selectedFiles.size === 0 || loading}
                className={`px-8 py-3 rounded-lg font-semibold transition-all ${
                  selectedFiles.size === 0 || loading
                    ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }`}
              >
                {loading ? "Processing..." : "Process Selected Files"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
