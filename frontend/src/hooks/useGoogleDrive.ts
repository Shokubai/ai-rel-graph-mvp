"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import axios, { AxiosError } from "axios";
import type {
  DriveFileListResponse,
  DriveFileMetadata,
} from "@/types/google-drive";

const GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3";

/**
 * Fetches data from Google Drive API
 */
async function fetchFromDrive<T>(
  endpoint: string,
  accessToken: string
): Promise<T> {
  try {
    const response = await axios.get<T>(
      `${GOOGLE_DRIVE_API_BASE}${endpoint}`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      }
    );
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      throw new Error(
        `Google Drive API error: ${error.response?.statusText || error.message}`
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
      if (!session?.accessToken) {
        throw new Error("No access token available");
      }

      const query = folderId
        ? `'${folderId}' in parents and trashed=false`
        : "trashed=false";

      // Fetch all pages of results
      const allFiles: DriveFileListResponse["files"] = [];
      let pageToken: string | undefined = undefined;

      do {
        const params = new URLSearchParams({
          q: query,
          fields:
            "files(id,name,mimeType,modifiedTime,size,webViewLink,thumbnailLink,parents),nextPageToken",
          pageSize: "100",
        });

        if (pageToken) {
          params.set("pageToken", pageToken);
        }

        const response = await fetchFromDrive<DriveFileListResponse>(
          `/files?${params}`,
          session.accessToken
        );

        allFiles.push(...response.files);
        pageToken = response.nextPageToken;
      } while (pageToken);

      return { files: allFiles };
    },
    enabled: enabled && !!session?.accessToken,
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
      if (!session?.accessToken || !fileId) {
        throw new Error("Missing access token or file ID");
      }

      const params = new URLSearchParams({
        fields:
          "id,name,mimeType,description,starred,trashed,createdTime,modifiedTime,size,owners",
      });

      return fetchFromDrive<DriveFileMetadata>(
        `/files/${fileId}?${params}`,
        session.accessToken
      );
    },
    enabled: !!session?.accessToken && !!fileId,
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
      if (!session?.accessToken) {
        throw new Error("No access token available");
      }

      const endpoint = mimeType
        ? `/files/${fileId}/export?mimeType=${encodeURIComponent(mimeType)}`
        : `/files/${fileId}?alt=media`;

      try {
        const response = await axios.get<Blob>(
          `${GOOGLE_DRIVE_API_BASE}${endpoint}`,
          {
            headers: {
              Authorization: `Bearer ${session.accessToken}`,
            },
            responseType: "blob",
          }
        );

        return response.data;
      } catch (error) {
        if (error instanceof AxiosError) {
          throw new Error(
            `Failed to export file: ${error.response?.statusText || error.message}`
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
      if (!session?.accessToken || !searchQuery) {
        throw new Error("Missing access token or search query");
      }

      const query = `name contains '${searchQuery}' and trashed=false`;
      const params = new URLSearchParams({
        q: query,
        fields: "files(id,name,mimeType,modifiedTime,size,webViewLink)",
        pageSize: "50",
      });

      return fetchFromDrive<DriveFileListResponse>(
        `/files?${params}`,
        session.accessToken
      );
    },
    enabled: !!session?.accessToken && !!searchQuery && searchQuery.length > 0,
  });
}
