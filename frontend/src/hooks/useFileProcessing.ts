"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

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
 * Request to start file processing
 */
export interface ProcessFilesRequest {
  folder_id?: string;
}

/**
 * Response when processing starts
 */
export interface ProcessFilesResponse {
  task_id: string;
  message: string;
  status: string;
}

/**
 * Task status response
 */
export interface TaskStatusResponse {
  task_id: string;
  state: string; // PENDING, PROCESSING, SUCCESS, FAILURE
  current?: number;
  total?: number;
  current_file?: string;
  status?: string;
  result?: {
    status: string;
    message: string;
    output_file: string;
    stats: {
      total_files: number;
      processed: number;
      failed: number;
      total_words: number;
      average_words: number;
    };
    failed_files: Array<{ id: string; name: string; error: string }>;
  };
  error?: string;
}

/**
 * Hook to start file processing
 */
export function useStartProcessing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: ProcessFilesRequest) => {
      const token = await getAuthToken();

      const response = await axios.post<ProcessFilesResponse>(
        `${API_BASE}/api/v1/processing/start`,
        request,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );

      return response.data;
    },
    onSuccess: () => {
      // Invalidate any cached data
      queryClient.invalidateQueries({ queryKey: ["processing-status"] });
    },
  });
}

/**
 * Hook to check processing status
 */
export function useProcessingStatus(taskId?: string) {
  return useQuery({
    queryKey: ["processing-status", taskId],
    queryFn: async () => {
      if (!taskId) {
        throw new Error("No task ID provided");
      }

      const token = await getAuthToken();

      const response = await axios.get<TaskStatusResponse>(
        `${API_BASE}/api/v1/processing/status/${taskId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      return response.data;
    },
    enabled: !!taskId,
    refetchInterval: (query) => {
      // Keep polling while task is running
      if (
        query.state.data?.state === "PENDING" ||
        query.state.data?.state === "PROCESSING"
      ) {
        return 2000; // Poll every 2 seconds
      }
      return false; // Stop polling when done
    },
  });
}

/**
 * Hook to cancel processing
 */
export function useCancelProcessing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (taskId: string) => {
      const token = await getAuthToken();

      const response = await axios.delete(
        `${API_BASE}/api/v1/processing/cancel/${taskId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["processing-status"] });
    },
  });
}
