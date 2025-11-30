"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface GraphNode {
  id: string;
  title: string;
  url: string;
  summary: string;
  tags: string[];
  entities: string[];
  author: string;
  modified: string;
  preview: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  similarity: number;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: {
    total_nodes: number;
    total_edges: number;
    generated_at: string;
  };
}

export interface GenerateGraphRequest {
  documents_file: string;
  similarity_threshold?: number;
  max_tags_per_doc?: number;
  max_entities_per_doc?: number;
  use_top_k_similarity?: boolean;
  top_k_neighbors?: number;
  min_similarity?: number;
}

export interface GraphGenerationStatus {
  task_id: string;
  state: "PENDING" | "PROCESSING" | "SUCCESS" | "FAILURE";
  current?: number;
  total?: number;
  status?: string;
  result?: {
    graph_file: string;
    stats: {
      total_nodes: number;
      total_edges: number;
    };
  };
  error?: string;
}

/**
 * Hook to fetch graph data for visualization
 */
export function useGraphData() {
  return useQuery<GraphData>({
    queryKey: ["graph-data"],
    queryFn: async () => {
      const { data } = await axios.get(`${API_BASE}/api/v1/graph/data`);
      return data;
    },
    retry: false,
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
}

/**
 * Hook to generate knowledge graph from processed documents
 */
export function useGenerateGraph() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: GenerateGraphRequest) => {
      const { data } = await axios.post(
        `${API_BASE}/api/v1/graph/generate`,
        request
      );
      return data;
    },
    onSuccess: () => {
      // Invalidate graph data to refetch when generation completes
      queryClient.invalidateQueries({ queryKey: ["graph-data"] });
    },
  });
}

/**
 * Hook to check graph generation status
 */
export function useGraphGenerationStatus(taskId?: string) {
  return useQuery<GraphGenerationStatus>({
    queryKey: ["graph-generation-status", taskId],
    queryFn: async () => {
      if (!taskId) throw new Error("No task ID provided");
      const { data } = await axios.get(
        `${API_BASE}/api/v1/graph/status/${taskId}`
      );
      return data;
    },
    enabled: !!taskId,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      // Stop polling when task is complete or failed
      if (state === "SUCCESS" || state === "FAILURE") {
        return false;
      }
      // Poll every 2 seconds while processing
      return 2000;
    },
  });
}

/**
 * Hook to search documents in the graph
 */
export function useSearchGraph(query: string) {
  return useQuery({
    queryKey: ["graph-search", query],
    queryFn: async () => {
      const { data } = await axios.get(`${API_BASE}/api/v1/graph/search`, {
        params: { q: query },
      });
      return data;
    },
    enabled: query.length >= 2,
  });
}

/**
 * Hook to get document details
 */
export function useDocumentDetails(docId?: string) {
  return useQuery({
    queryKey: ["document-details", docId],
    queryFn: async () => {
      if (!docId) throw new Error("No document ID provided");
      const { data } = await axios.get(
        `${API_BASE}/api/v1/graph/documents/${docId}`
      );
      return data;
    },
    enabled: !!docId,
  });
}
