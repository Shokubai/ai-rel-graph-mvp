"use client";

import React, { useState, useEffect, ReactElement, useCallback, useRef } from "react";
import { ChevronRight, ChevronDown, File, Folder, CheckSquare, Square, Save, RotateCcw, Plus, FolderOpen, Upload, Cloud } from "lucide-react";
import { useSession } from "next-auth/react";
import axios, { AxiosError } from "axios";

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

interface Document {
  id: string;
  title: string;
  mime_type: string;
  parent_folder_id: string | null;
  is_enabled: boolean;
  url: string;
  modified_at: string | null;
}

interface TreeNode {
  id: string;
  title: string;
  isFolder: boolean;
  isEnabled: boolean;
  url: string;
  children: TreeNode[];
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

interface DocumentManagerProps {
  onDocumentToggle?: () => void;
  onProcessingStart?: (taskId: string) => void;
  onClose?: () => void;
}

export default function DocumentManager({ onDocumentToggle, onProcessingStart, onClose }: DocumentManagerProps) {
  const { data: session } = useSession();

  // Tab state
  const [activeTab, setActiveTab] = useState<"manage" | "add">("manage");

  // Existing documents state
  const [documents, setDocuments] = useState<Document[]>([]);
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track pending changes (not saved yet)
  const [pendingChanges, setPendingChanges] = useState<Map<string, boolean>>(new Map());
  const [saving, setSaving] = useState(false);

  // Delete all confirmation dialog
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Google Drive browsing state
  const [driveFiles, setDriveFiles] = useState<DriveFile[]>([]);
  const [selectedDriveFiles, setSelectedDriveFiles] = useState<Set<string>>(new Set());
  const [driveLoading, setDriveLoading] = useState(false);
  const [driveError, setDriveError] = useState<string | null>(null);
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [folderPath, setFolderPath] = useState<{ id: string | null; name: string }[]>([
    { id: null, name: "My Drive" },
  ]);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [hasMoreFiles, setHasMoreFiles] = useState(false);

  // Add tab sub-mode: google_drive or local_upload
  const [addMode, setAddMode] = useState<"google_drive" | "local_upload">("google_drive");

  // Local file upload state
  const [localFiles, setLocalFiles] = useState<File[]>([]);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Supported file types for local upload
  const SUPPORTED_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/plain",
  ];
  const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt"];

  // Local file upload handlers
  const validateFile = (file: File): string | null => {
    // Check file type
    const fileExtension = "." + file.name.split(".").pop()?.toLowerCase();
    if (!SUPPORTED_TYPES.includes(file.type) && !SUPPORTED_EXTENSIONS.includes(fileExtension)) {
      return `Unsupported file type: ${file.name}. Supported types: PDF, DOCX, XLSX, TXT`;
    }
    // Check file size (10 MB max)
    const MAX_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      return `File too large: ${file.name}. Maximum size is 10 MB`;
    }
    return null;
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    const newFiles: File[] = [];
    const errors: string[] = [];

    Array.from(files).forEach((file: File) => {
      const error = validateFile(file);
      if (error) {
        errors.push(error);
      } else {
        // Check for duplicates
        if (!localFiles.some((f: File) => f.name === file.name && f.size === file.size)) {
          newFiles.push(file);
        }
      }
    });

    if (errors.length > 0) {
      setUploadError(errors.join("\n"));
    } else {
      setUploadError(null);
    }

    if (newFiles.length > 0) {
      setLocalFiles((prev: File[]) => [...prev, ...newFiles]);
    }

    // Reset input so same file can be selected again
    event.target.value = "";
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);

    const files = event.dataTransfer.files;
    if (!files) return;

    const newFiles: File[] = [];
    const errors: string[] = [];

    Array.from(files).forEach((file: File) => {
      const error = validateFile(file);
      if (error) {
        errors.push(error);
      } else {
        // Check for duplicates
        if (!localFiles.some((f: File) => f.name === file.name && f.size === file.size)) {
          newFiles.push(file);
        }
      }
    });

    if (errors.length > 0) {
      setUploadError(errors.join("\n"));
    } else {
      setUploadError(null);
    }

    if (newFiles.length > 0) {
      setLocalFiles((prev: File[]) => [...prev, ...newFiles]);
    }
  };

  const removeLocalFile = (index: number) => {
    setLocalFiles((prev: File[]) => prev.filter((_: File, i: number) => i !== index));
  };

  const clearLocalFiles = () => {
    setLocalFiles([]);
    setUploadError(null);
  };

  const handleUploadFiles = async () => {
    if (localFiles.length === 0) {
      setUploadError("Please select at least one file to upload");
      return;
    }

    setUploadLoading(true);
    setUploadError(null);

    try {
      const token = await getAuthToken();
      const formData = new FormData();

      localFiles.forEach((file: File) => {
        formData.append("files", file);
      });

      const response = await axios.post(
        `${API_BASE}/api/v1/processing/upload`,
        formData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "multipart/form-data",
          },
        }
      );

      // Clear selected files after successful upload
      setLocalFiles([]);

      // Call parent handler to switch to processing view
      if (onProcessingStart) {
        onProcessingStart(response.data.task_id);
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>;
      console.error("Failed to upload files:", err);
      setUploadError(axiosError.response?.data?.detail || "Failed to upload files");
      setUploadLoading(false);
    }
  };

  const getLocalFileIcon = (fileName: string): string => {
    const ext = fileName.split(".").pop()?.toLowerCase() || "";
    switch (ext) {
      case "pdf":
        return "📕";
      case "docx":
      case "doc":
        return "📄";
      case "xlsx":
      case "xls":
        return "📊";
      case "txt":
        return "📝";
      default:
        return "📎";
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  // Google Drive file browsing functions
  const loadDriveFiles = useCallback(async (folderId: string | null, pageToken?: string | null) => {
    if (!session) return;

    setDriveLoading(true);
    setDriveError(null);

    try {
      const token = await getAuthToken();
      const params: Record<string, string> = {};
      if (folderId) {
        params.folderId = folderId;
      }
      if (pageToken) {
        params.pageToken = pageToken;
      }

      const response = await axios.get(`${API_BASE}/api/v1/drive/files`, {
        params,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      // If loading more (pageToken exists), append to existing files
      if (pageToken) {
        setDriveFiles((prev: DriveFile[]) => [...prev, ...(response.data.files || [])]);
      } else {
        setDriveFiles(response.data.files || []);
      }

      // Store next page token for pagination
      setNextPageToken(response.data.nextPageToken || null);
      setHasMoreFiles(!!response.data.nextPageToken);
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>;
      console.error("Failed to load Drive files:", err);
      setDriveError(axiosError.response?.data?.detail || "Failed to load files from Google Drive");
    } finally {
      setDriveLoading(false);
    }
  }, [session]);

  const loadMoreFiles = () => {
    if (nextPageToken && !driveLoading) {
      loadDriveFiles(currentFolder, nextPageToken);
    }
  };

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch("/api/graph/documents", {
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch documents");
      }

      const data = await response.json();
      setDocuments(data.documents);

      // Build tree structure
      const treeStructure = buildTree(data.documents);
      setTree(treeStructure);

      // Clear pending changes when data is refreshed
      setPendingChanges(new Map());
    } catch (err) {
      console.error("Error fetching documents:", err);
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch all documents when on manage tab
  useEffect(() => {
    if (activeTab === "manage") {
      fetchDocuments();
    }
  }, [activeTab, fetchDocuments]);

  // Load Google Drive files when on "add" tab
  useEffect(() => {
    if (activeTab === "add" && session) {
      loadDriveFiles(currentFolder);
    }
  }, [activeTab, session, currentFolder, loadDriveFiles]);

  // Build hierarchical tree structure
  const buildTree = (docs: Document[]): TreeNode[] => {
    const nodeMap = new Map<string, TreeNode>();
    const rootNodes: TreeNode[] = [];

    // Create nodes for all documents
    docs.forEach((doc) => {
      const isFolder = (doc.mime_type || "") === "application/vnd.google-apps.folder";
      nodeMap.set(doc.id, {
        id: doc.id,
        title: doc.title,
        isFolder,
        isEnabled: doc.is_enabled,
        url: doc.url,
        children: [],
      });
    });

    // Build parent-child relationships
    docs.forEach((doc) => {
      const node = nodeMap.get(doc.id);
      if (!node) return;

      if (doc.parent_folder_id && nodeMap.has(doc.parent_folder_id)) {
        // Add to parent's children
        const parent = nodeMap.get(doc.parent_folder_id);
        parent?.children.push(node);
      } else {
        // Root level node
        rootNodes.push(node);
      }
    });

    // Sort each level: folders first, then alphabetically
    const sortNodes = (nodes: TreeNode[]) => {
      nodes.sort((a, b) => {
        // Folders first
        if (a.isFolder && !b.isFolder) return -1;
        if (!a.isFolder && b.isFolder) return 1;
        // Alphabetically
        return a.title.localeCompare(b.title);
      });

      // Recursively sort children
      nodes.forEach((node) => {
        if (node.children.length > 0) {
          sortNodes(node.children);
        }
      });
    };

    sortNodes(rootNodes);
    return rootNodes;
  };

  // Get the current enabled status (considering pending changes)
  const getCurrentStatus = (docId: string, originalStatus: boolean): boolean => {
    if (pendingChanges.has(docId)) {
      return pendingChanges.get(docId)!;
    }
    return originalStatus;
  };

  // Toggle document in pending changes (doesn't save immediately)
  const toggleDocumentPending = (docId: string, currentStatus: boolean) => {
    const newChanges = new Map(pendingChanges);
    const targetStatus = !currentStatus;

    // If reverting to original, remove from pending changes
    const originalDoc = documents.find((d: Document) => d.id === docId);
    if (originalDoc && originalDoc.is_enabled === targetStatus) {
      newChanges.delete(docId);
    } else {
      newChanges.set(docId, targetStatus);
    }

    setPendingChanges(newChanges);
  };

  // Apply all pending changes
  const applyChanges = async () => {
    if (pendingChanges.size === 0) return;

    try {
      setSaving(true);

      // Apply each change
      const entries: [string, boolean][] = Array.from(pendingChanges.entries());
      const promises = entries.map(([docId, enabled]) =>
        fetch(`/api/graph/documents/${docId}/toggle?enabled=${enabled}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        })
      );

      await Promise.all(promises);

      // Refresh documents list
      await fetchDocuments();

      // Notify parent component to refresh graph
      if (onDocumentToggle) {
        onDocumentToggle();
      }

      // Return to graph view after successful save
      if (onClose) {
        onClose();
      }
    } catch (err) {
      console.error("Error applying changes:", err);
      alert("Failed to update document status");
    } finally {
      setSaving(false);
    }
  };

  // Discard pending changes
  const discardChanges = () => {
    setPendingChanges(new Map());
  };

  // Select all documents
  const selectAll = () => {
    const newChanges = new Map(pendingChanges);
    documents.forEach((doc: Document) => {
      if (!(doc.mime_type || "").includes("folder") && !doc.is_enabled) {
        newChanges.set(doc.id, true);
      }
    });
    setPendingChanges(newChanges);
  };

  // Deselect all documents
  const deselectAll = () => {
    const newChanges = new Map(pendingChanges);
    documents.forEach((doc: Document) => {
      if (!(doc.mime_type || "").includes("folder") && doc.is_enabled) {
        newChanges.set(doc.id, false);
      }
    });
    setPendingChanges(newChanges);
  };

  // Delete all user data
  const handleDeleteAllData = async () => {
    try {
      setDeleting(true);

      const response = await fetch("/api/graph/documents/delete-all", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to delete data");
      }

      // Close confirmation dialog
      setShowDeleteConfirm(false);

      // Refresh documents list (should be empty now)
      await fetchDocuments();

      // Notify parent component to refresh graph
      if (onDocumentToggle) {
        onDocumentToggle();
      }
    } catch (err) {
      console.error("Error deleting data:", err);
      alert("Failed to delete all data");
    } finally {
      setDeleting(false);
    }
  };

  // Toggle folder expansion
  const toggleFolder = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  };

  const handleDriveFolderClick = (file: DriveFile) => {
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

  const toggleDriveFileSelection = (fileId: string) => {
    const newSelected = new Set(selectedDriveFiles);
    if (newSelected.has(fileId)) {
      newSelected.delete(fileId);
    } else {
      newSelected.add(fileId);
    }
    setSelectedDriveFiles(newSelected);
  };

  const toggleSelectAllDriveFiles = () => {
    if (selectedDriveFiles.size === driveFiles.length) {
      setSelectedDriveFiles(new Set());
    } else {
      setSelectedDriveFiles(new Set(driveFiles.map((f: DriveFile) => f.id)));
    }
  };

  const handleProcessDriveFiles = async () => {
    if (selectedDriveFiles.size === 0) {
      setDriveError("Please select at least one file or folder to process");
      return;
    }

    setDriveLoading(true);
    setDriveError(null);

    try {
      const token = await getAuthToken();
      const response = await axios.post(
        `${API_BASE}/api/v1/processing/start`,
        {
          file_ids: Array.from(selectedDriveFiles),
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      // Call parent handler to switch to processing view
      if (onProcessingStart) {
        onProcessingStart(response.data.task_id);
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>;
      console.error("Failed to start processing:", err);
      setDriveError(axiosError.response?.data?.detail || "Failed to start file processing");
      setDriveLoading(false);
    }
  };

  const getFileIcon = (mimeType: string | undefined) => {
    const type = mimeType || "";
    if (type === "application/vnd.google-apps.folder") {
      return "📁";
    } else if (type.includes("document")) {
      return "📄";
    } else if (type.includes("spreadsheet")) {
      return "📊";
    } else if (type.includes("presentation")) {
      return "📽️";
    } else if (type.includes("pdf")) {
      return "📕";
    }
    return "📎";
  };

  // Render tree node
  const renderNode = (node: TreeNode, depth: number = 0): ReactElement => {
    const isExpanded = expandedFolders.has(node.id);
    const paddingLeft = `${depth * 24}px`;
    const currentStatus = getCurrentStatus(node.id, node.isEnabled);
    const hasChanges = pendingChanges.has(node.id);

    return (
      <div key={node.id}>
        <div
          className={`flex items-center gap-2 py-1.5 px-2 hover:bg-gray-800 rounded group ${
            hasChanges ? "bg-yellow-900/20" : ""
          }`}
          style={{ paddingLeft }}
        >
          {/* Folder toggle */}
          {node.isFolder && (
            <button
              onClick={() => toggleFolder(node.id)}
              className="p-0.5 hover:bg-gray-200 rounded"
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-gray-600" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-600" />
              )}
            </button>
          )}

          {/* Checkbox (only for files) */}
          {!node.isFolder && (
            <button
              onClick={() => toggleDocumentPending(node.id, currentStatus)}
              className="flex-shrink-0"
            >
              {currentStatus ? (
                <CheckSquare className="w-5 h-5 text-blue-600" />
              ) : (
                <Square className="w-5 h-5 text-gray-400" />
              )}
            </button>
          )}

          {/* Icon */}
          {node.isFolder ? (
            <Folder className="w-5 h-5 text-blue-500 flex-shrink-0" />
          ) : (
            <File className="w-5 h-5 text-gray-500 flex-shrink-0" />
          )}

          {/* Title */}
          <a
            href={node.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 text-sm truncate hover:underline"
            title={node.title}
          >
            {node.title}
          </a>

          {/* Status badges */}
          {!node.isFolder && (
            <div className="flex items-center gap-2">
              {hasChanges && (
                <span className="text-xs px-2 py-0.5 rounded bg-yellow-900/40 text-yellow-400">
                  Modified
                </span>
              )}
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  currentStatus
                    ? "bg-green-900/30 text-green-400"
                    : "bg-gray-800 text-gray-400"
                }`}
              >
                {currentStatus ? "In Graph" : "Hidden"}
              </span>
            </div>
          )}
        </div>

        {/* Children */}
        {node.isFolder && isExpanded && node.children.length > 0 && (
          <div>
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500">Loading documents...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
        <button
          onClick={fetchDocuments}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const totalDocs = documents.filter((d: Document) => !(d.mime_type || "").includes("folder")).length;
  const enabledDocs = documents.filter((d: Document) => !(d.mime_type || "").includes("folder") && d.is_enabled).length;

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header with Close Button */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <h1 className="text-xl font-bold text-white">Document Manager</h1>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            title="Close and return to graph"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-800">
        <div className="flex px-6">
          <button
            onClick={() => setActiveTab("manage")}
            className={`px-6 py-3 font-medium transition-colors relative ${
              activeTab === "manage"
                ? "text-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
          >
            <FolderOpen className="w-4 h-4 inline mr-2" />
            Manage Documents
            {activeTab === "manage" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"></div>
            )}
          </button>
          <button
            onClick={() => setActiveTab("add")}
            className={`px-6 py-3 font-medium transition-colors relative ${
              activeTab === "add"
                ? "text-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
          >
            <Plus className="w-4 h-4 inline mr-2" />
            Add New Files
            {activeTab === "add" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"></div>
            )}
          </button>
        </div>
      </div>

      {/* Manage Documents Tab */}
      {activeTab === "manage" && (
        <>
          <div className="border-b border-gray-800 px-6 py-4 bg-gray-950">
            <p className="text-sm text-gray-400 mt-1">
              Manage which documents appear in the graph. Changes are applied when you click &ldquo;Apply Changes&rdquo;.
            </p>

        {/* Stats */}
        <div className="flex items-center gap-4 mt-3 text-sm text-gray-400">
          <span>Total: <span className="text-white font-medium">{totalDocs}</span></span>
          <span>In Graph: <span className="text-green-400 font-medium">{enabledDocs}</span></span>
          <span>Hidden: <span className="text-gray-500 font-medium">{totalDocs - enabledDocs}</span></span>
          {pendingChanges.size > 0 && (
            <span className="text-yellow-400 font-medium">
              • {pendingChanges.size} pending change{pendingChanges.size !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={selectAll}
            className="px-3 py-1.5 text-sm bg-green-900/30 text-green-400 border border-green-700/50 rounded hover:bg-green-900/50"
          >
            Show All
          </button>
          <button
            onClick={deselectAll}
            className="px-3 py-1.5 text-sm bg-gray-800 text-gray-300 border border-gray-700 rounded hover:bg-gray-700"
          >
            Hide All
          </button>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="px-3 py-1.5 text-sm bg-red-900/30 text-red-400 border border-red-700/50 rounded hover:bg-red-900/50"
          >
            Delete All Data
          </button>

          <div className="flex-1"></div>

          {pendingChanges.size > 0 && (
            <>
              <button
                onClick={discardChanges}
                disabled={saving}
                className="px-3 py-1.5 text-sm bg-gray-800 text-gray-300 border border-gray-700 rounded hover:bg-gray-700 flex items-center gap-1 disabled:opacity-50"
              >
                <RotateCcw className="w-4 h-4" />
                Discard
              </button>
              <button
                onClick={applyChanges}
                disabled={saving}
                className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-1 disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? "Saving..." : "Apply Changes"}
              </button>
            </>
          )}
        </div>
      </div>

          <div className="flex-1 overflow-y-auto p-4">
            {tree.length === 0 ? (
              <div className="text-center text-gray-400 py-8">
                No documents found. Process some files from Google Drive to get started.
              </div>
            ) : (
              <div className="space-y-0.5">
                {tree.map((node: TreeNode) => renderNode(node))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Add New Files Tab */}
      {activeTab === "add" && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Sub-tab Navigation */}
          <div className="border-b border-gray-800 px-6 py-3 bg-gray-950">
            <div className="flex gap-2">
              <button
                onClick={() => setAddMode("google_drive")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  addMode === "google_drive"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
                }`}
              >
                <Cloud className="w-4 h-4" />
                Google Drive
              </button>
              <button
                onClick={() => setAddMode("local_upload")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  addMode === "local_upload"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
                }`}
              >
                <Upload className="w-4 h-4" />
                Local Upload
              </button>
            </div>
          </div>

          {/* Google Drive Mode */}
          {addMode === "google_drive" && (
            <>
              <div className="border-b border-gray-800 px-6 py-4 bg-gray-950">
                <p className="text-sm text-gray-400">
                  Browse your Google Drive and select files to process. Selected files will be analyzed and added to your knowledge graph.
                </p>
              </div>

              {/* Error Display */}
              {driveError && (
                <div className="mx-4 mt-4 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
                  {driveError}
                </div>
              )}

              {/* Breadcrumb Navigation */}
              <div className="px-6 py-3 border-b border-gray-800 bg-gray-950">
                <div className="flex items-center gap-2 text-sm">
                  {folderPath.map((folder: { id: string | null; name: string }, index: number) => (
                    <div key={folder.id || "root"} className="flex items-center gap-2">
                      {index > 0 && <span className="text-gray-600">/</span>}
                      <button
                        onClick={() => handleBreadcrumbClick(index)}
                        className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
                      >
                        {folder.name}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Local Upload Mode */}
          {addMode === "local_upload" && (
            <>
              <div className="border-b border-gray-800 px-6 py-4 bg-gray-950">
                <p className="text-sm text-gray-400">
                  Upload files from your computer. Supported formats: PDF, DOCX, XLSX, TXT (max 10 MB per file).
                </p>
              </div>

              {/* Error Display */}
              {uploadError && (
                <div className="mx-4 mt-4 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200 whitespace-pre-line">
                  {uploadError}
                </div>
              )}

              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={SUPPORTED_EXTENSIONS.join(",")}
                onChange={handleFileSelect}
                className="hidden"
              />

              {/* Drag & Drop Zone */}
              <div className="flex-1 overflow-y-auto p-4">
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                    isDragging
                      ? "border-blue-500 bg-blue-900/20"
                      : "border-gray-700 hover:border-gray-600 hover:bg-gray-800/50"
                  }`}
                >
                  <Upload className={`w-12 h-12 mx-auto mb-4 ${isDragging ? "text-blue-400" : "text-gray-500"}`} />
                  <p className="text-lg font-medium text-white mb-2">
                    {isDragging ? "Drop files here" : "Drag & drop files here"}
                  </p>
                  <p className="text-sm text-gray-400 mb-4">or click to browse</p>
                  <p className="text-xs text-gray-500">
                    Supported: PDF, DOCX, DOC, XLSX, XLS, TXT • Max 10 MB per file
                  </p>
                </div>

                {/* Selected Files List */}
                {localFiles.length > 0 && (
                  <div className="mt-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-semibold text-white">
                        Selected Files ({localFiles.length})
                      </h3>
                      <button
                        onClick={clearLocalFiles}
                        className="text-sm text-gray-400 hover:text-red-400 transition-colors"
                      >
                        Clear all
                      </button>
                    </div>
                    <div className="space-y-2">
                      {localFiles.map((file: File, index: number) => (
                        <div
                          key={`${file.name}-${file.size}-${index}`}
                          className="flex items-center gap-3 p-3 rounded-lg border border-gray-800 bg-gray-800/50"
                        >
                          <span className="text-2xl">{getLocalFileIcon(file.name)}</span>
                          <div className="flex-1 min-w-0">
                            <span className="text-white font-medium truncate block">
                              {file.name}
                            </span>
                            <span className="text-xs text-gray-500">
                              {formatFileSize(file.size)}
                            </span>
                          </div>
                          <button
                            onClick={(e: React.MouseEvent) => {
                              e.stopPropagation();
                              removeLocalFile(index);
                            }}
                            className="p-1 text-gray-400 hover:text-red-400 transition-colors"
                            title="Remove file"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Upload Action Button */}
              <div className="border-t border-gray-800 px-6 py-4 bg-gray-950">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-400">
                    {localFiles.length} file{localFiles.length !== 1 ? "s" : ""} selected
                  </div>
                  <button
                    onClick={handleUploadFiles}
                    disabled={localFiles.length === 0 || uploadLoading}
                    className={`px-6 py-2.5 rounded-lg font-semibold transition-all flex items-center gap-2 ${
                      localFiles.length === 0 || uploadLoading
                        ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                        : "bg-blue-600 text-white hover:bg-blue-700"
                    }`}
                  >
                    <Upload className="w-4 h-4" />
                    {uploadLoading ? "Uploading..." : "Upload & Process Files"}
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Google Drive File List (only shown in google_drive mode) */}
          {addMode === "google_drive" && (
            <>
              {/* File List */}
              <div className="flex-1 overflow-y-auto p-4">
                {driveLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : driveFiles.length === 0 ? (
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
                          checked={selectedDriveFiles.size === driveFiles.length && driveFiles.length > 0}
                          onChange={toggleSelectAllDriveFiles}
                          className="w-5 h-5 text-blue-600 border-gray-600 bg-gray-700 rounded focus:ring-blue-500"
                        />
                        <span className="font-semibold text-white">
                          Select All ({driveFiles.length} items)
                        </span>
                      </label>
                    </div>

                    {/* File List */}
                    <div className="space-y-2">
                      {driveFiles.map((file: DriveFile) => (
                        <div
                          key={file.id}
                          className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                            selectedDriveFiles.has(file.id)
                              ? "bg-blue-900/30 border-blue-700"
                              : "hover:bg-gray-800 border-gray-800"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedDriveFiles.has(file.id)}
                            onChange={() => toggleDriveFileSelection(file.id)}
                            className="w-5 h-5 text-blue-600 border-gray-600 bg-gray-700 rounded focus:ring-blue-500"
                          />
                          <span className="text-2xl">{getFileIcon(file.mimeType)}</span>
                          <div className="flex-1 min-w-0">
                            {file.mimeType === "application/vnd.google-apps.folder" ? (
                              <button
                                onClick={() => handleDriveFolderClick(file)}
                                className="text-blue-400 hover:text-blue-300 font-medium text-left truncate block w-full transition-colors"
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

                    {/* Load More Button */}
                    {hasMoreFiles && (
                      <div className="mt-4 text-center">
                        <button
                          onClick={loadMoreFiles}
                          disabled={driveLoading}
                          className="px-6 py-3 bg-gray-800 text-gray-300 border border-gray-700 rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {driveLoading ? (
                            <>
                              <div className="inline-block w-4 h-4 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin mr-2"></div>
                              Loading more...
                            </>
                          ) : (
                            `Load More Files (${driveFiles.length} loaded)`
                          )}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Action Buttons */}
              <div className="border-t border-gray-800 px-6 py-4 bg-gray-950">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-400">
                    {selectedDriveFiles.size} file{selectedDriveFiles.size !== 1 ? "s" : ""} selected
                  </div>
                  <button
                    onClick={handleProcessDriveFiles}
                    disabled={selectedDriveFiles.size === 0 || driveLoading}
                    className={`px-6 py-2.5 rounded-lg font-semibold transition-all flex items-center gap-2 ${
                      selectedDriveFiles.size === 0 || driveLoading
                        ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                        : "bg-blue-600 text-white hover:bg-blue-700"
                    }`}
                  >
                    <Plus className="w-4 h-4" />
                    {driveLoading ? "Processing..." : "Process Selected Files"}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Delete All Confirmation Dialog */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setShowDeleteConfirm(false)}>
          <div className="bg-gray-900 border border-red-700 rounded-lg p-6 max-w-md w-full mx-4" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
            <h3 className="text-xl font-bold text-red-400 mb-4">Delete All Data</h3>
            <p className="text-gray-300 mb-6">
              Are you sure you want to delete all your documents, tags, entities, and relationships from the database?
              <span className="text-red-400 font-semibold block mt-2">This action cannot be undone!</span>
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
                className="px-4 py-2 bg-gray-800 text-gray-300 border border-gray-700 rounded hover:bg-gray-700 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAllData}
                disabled={deleting}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 flex items-center gap-2"
              >
                {deleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Deleting...
                  </>
                ) : (
                  "Delete All Data"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
