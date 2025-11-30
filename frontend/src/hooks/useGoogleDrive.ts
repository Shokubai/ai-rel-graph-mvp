"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import axios, { AxiosError } from "axios";
import type {
  DriveFileListResponse,
  DriveFileMetadata,
} from "@/types/google-drive";

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

/**
 * Fetches data from backend Drive proxy
 */
async function fetchFromDrive<T>(endpoint: string): Promise<T> {
  try {
    const token = await getAuthToken();
    const response = await axios.get<T>(`${API_BASE}/api/v1/drive${endpoint}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      throw new Error(
        `Drive API error: ${error.response?.statusText || error.message}`,
      );
    }
    throw error;
  }
}

/**
 * Hook to list files from a Google Drive folder
 */
export function useListDriveFiles(folderId?: string, enabled = true) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["drive-files", folderId],
    queryFn: async () => {
      if (!session?.user) {
        throw new Error("Not authenticated");
      }

      // Fetch all pages of results
      const allFiles: DriveFileListResponse["files"] = [];
      let pageToken: string | undefined = undefined;

      do {
        const params = new URLSearchParams({
          pageSize: "100",
        });

        if (folderId) {
          params.set("folderId", folderId);
        }

        if (pageToken) {
          params.set("pageToken", pageToken);
        }

        const response = await fetchFromDrive<DriveFileListResponse>(
          `/files?${params}`,
        );

        allFiles.push(...response.files);
        pageToken = response.nextPageToken;
      } while (pageToken);

      return { files: allFiles };
    },
    enabled: enabled && !!session?.user,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get metadata for a specific file
 */
export function useDriveFileMetadata(fileId?: string) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["drive-file-metadata", fileId],
    queryFn: async () => {
      if (!session?.user || !fileId) {
        throw new Error("Missing authentication or file ID");
      }

      return fetchFromDrive<DriveFileMetadata>(`/files/${fileId}`);
    },
    enabled: !!session?.user && !!fileId,
  });
}

/**
 * Hook to export/download a Google Drive file
 */
export function useExportDriveFile() {
  const { data: session } = useSession();

  return useMutation({
    mutationFn: async ({
      fileId,
      mimeType,
    }: {
      fileId: string;
      mimeType?: string;
    }) => {
      if (!session?.user) {
        throw new Error("Not authenticated");
      }

      const token = await getAuthToken();
      const params = new URLSearchParams();

      if (mimeType) {
        params.set("mimeType", mimeType);
      }

      const endpoint = `/files/${fileId}/export${params.toString() ? `?${params}` : ""}`;

      try {
        const response = await axios.get<Blob>(
          `${API_BASE}/api/v1/drive${endpoint}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
            responseType: "blob",
          },
        );

        return response.data;
      } catch (error) {
        if (error instanceof AxiosError) {
          throw new Error(
            `Failed to export file: ${error.response?.statusText || error.message}`,
          );
        }
        throw error;
      }
    },
  });
}

/**
 * Hook to search Google Drive files
 */
export function useSearchDriveFiles(searchQuery?: string) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["drive-search", searchQuery],
    queryFn: async () => {
      if (!session?.user || !searchQuery) {
        throw new Error("Missing authentication or search query");
      }

      const params = new URLSearchParams({
        query: searchQuery,
        pageSize: "50",
      });

      return fetchFromDrive<DriveFileListResponse>(`/files/search?${params}`);
    },
    enabled: !!session?.user && !!searchQuery && searchQuery.length > 0,
  });
}
