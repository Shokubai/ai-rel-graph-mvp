"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import axios, { AxiosError } from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ProcessingStage = "file_processing" | "graph_generation" | "complete";

interface FileProcessingStatus {
  task_id: string;
  state: string;
  current?: number;
  total?: number;
  current_file?: string;
  status?: string;
  result?: {
    documents_file?: string;
    total_documents?: number;
    failed_files?: Array<{ file: string; error: string }>;
  };
  error?: string;
}

interface GraphGenerationStatus {
  task_id: string;
  state: string;
  current?: number;
  total?: number;
  status?: string;
  result?: {
    graph_file?: string;
    nodes?: number;
    edges?: number;
  };
  error?: string;
}

interface ProcessingStatusProps {
  fileProcessingTaskId: string | null;
  onComplete: () => void;
  onBack: () => void;
}

export function ProcessingStatus({
  fileProcessingTaskId,
  onComplete,
  onBack,
}: ProcessingStatusProps) {
  const { data: session } = useSession();
  const [stage, setStage] = useState<ProcessingStage>("file_processing");
  const [fileStatus, setFileStatus] = useState<FileProcessingStatus | null>(null);
  const [graphStatus, setGraphStatus] = useState<GraphGenerationStatus | null>(null);
  const [graphTaskId, setGraphTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startGraphGeneration = useCallback(async (documentsFile?: string) => {
    if (!documentsFile) {
      setError("No documents file found from processing");
      return;
    }

    if (!session) return;

    try {
      setStage("graph_generation");
      const response = await axios.post(
        `${API_BASE}/api/v1/graph/generate`,
        {
          documents_file: documentsFile,
          use_top_k_similarity: true,
          top_k_neighbors: 3,
          min_similarity: 0.3,
          enable_hierarchy: true,
        },
        {
          headers: {
            Authorization: `Bearer ${(session as { accessToken?: string })?.accessToken}`,
          },
        }
      );

      setGraphTaskId(response.data.task_id);
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>;
      console.error("Failed to start graph generation:", err);
      setError(axiosError.response?.data?.detail || "Failed to start graph generation");
    }
  }, [session]);

  // Poll file processing status
  useEffect(() => {
    if (!fileProcessingTaskId || stage !== "file_processing" || !session) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(
          `${API_BASE}/api/v1/processing/status/${fileProcessingTaskId}`,
          {
            headers: {
              Authorization: `Bearer ${(session as { accessToken?: string })?.accessToken}`,
            },
          }
        );

        setFileStatus(response.data);

        // If processing completed successfully, start graph generation
        if (response.data.state === "SUCCESS") {
          clearInterval(pollInterval);
          await startGraphGeneration(response.data.result?.documents_file);
        } else if (response.data.state === "FAILURE") {
          clearInterval(pollInterval);
          setError(response.data.error || "File processing failed");
        }
      } catch (err) {
        console.error("Failed to fetch processing status:", err);
        setError("Failed to fetch processing status");
        clearInterval(pollInterval);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [fileProcessingTaskId, stage, session, startGraphGeneration]);

  // Poll graph generation status
  useEffect(() => {
    if (!graphTaskId || stage !== "graph_generation" || !session) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(
          `${API_BASE}/api/v1/graph/status/${graphTaskId}`,
          {
            headers: {
              Authorization: `Bearer ${(session as { accessToken?: string })?.accessToken}`,
            },
          }
        );

        setGraphStatus(response.data);

        // If graph generation completed successfully
        if (response.data.state === "SUCCESS") {
          clearInterval(pollInterval);
          setStage("complete");
          setTimeout(() => {
            onComplete();
          }, 2000); // Show success message for 2 seconds
        } else if (response.data.state === "FAILURE") {
          clearInterval(pollInterval);
          setError(response.data.error || "Graph generation failed");
        }
      } catch (err) {
        console.error("Failed to fetch graph generation status:", err);
        setError("Failed to fetch graph generation status");
        clearInterval(pollInterval);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [graphTaskId, stage, session, onComplete]);

  const getProgressPercentage = () => {
    if (stage === "file_processing" && fileStatus) {
      if (fileStatus.total && fileStatus.current) {
        return Math.round((fileStatus.current / fileStatus.total) * 100);
      }
    } else if (stage === "graph_generation" && graphStatus) {
      if (graphStatus.total && graphStatus.current) {
        return Math.round((graphStatus.current / graphStatus.total) * 100);
      }
    }
    return 0;
  };

  return (
    <div className="w-full h-full bg-gray-900 p-8 overflow-auto flex items-center justify-center">
      <div className="max-w-3xl w-full">
        <div className="bg-gray-950 border border-gray-800 rounded-lg shadow-xl p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">
              {stage === "file_processing" && "Processing Files"}
              {stage === "graph_generation" && "Generating Knowledge Graph"}
              {stage === "complete" && "Complete!"}
            </h1>
            <p className="text-gray-400">
              {stage === "file_processing" &&
                "Extracting text and metadata from your selected files..."}
              {stage === "graph_generation" &&
                "Creating semantic connections and building the graph..."}
              {stage === "complete" && "Your knowledge graph is ready to explore!"}
            </p>
          </div>

          {/* Error Display */}
          {error && (
            <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg">
              <div className="flex items-start gap-3">
                <span className="text-2xl">❌</span>
                <div className="flex-1">
                  <h3 className="font-semibold text-red-200 mb-1">Error</h3>
                  <p className="text-red-300 text-sm">{error}</p>
                </div>
              </div>
              <button
                onClick={onBack}
                className="mt-4 w-full px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                Go Back
              </button>
            </div>
          )}

          {/* Progress Indicators */}
          {!error && (
            <>
              {/* Stage Indicators */}
              <div className="flex items-center justify-center gap-4 mb-8">
                {/* File Processing */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 transition-all ${
                      stage === "file_processing"
                        ? "bg-blue-600 text-white"
                        : stage === "graph_generation" || stage === "complete"
                        ? "bg-green-600 text-white"
                        : "bg-gray-700 text-gray-400"
                    }`}
                  >
                    {stage === "file_processing" ? (
                      <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : stage === "graph_generation" || stage === "complete" ? (
                      "✓"
                    ) : (
                      "1"
                    )}
                  </div>
                  <span className="text-xs text-gray-400 text-center">File Processing</span>
                </div>

                {/* Arrow */}
                <div className="text-gray-600 text-2xl mb-6">→</div>

                {/* Graph Generation */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 transition-all ${
                      stage === "graph_generation"
                        ? "bg-blue-600 text-white"
                        : stage === "complete"
                        ? "bg-green-600 text-white"
                        : "bg-gray-700 text-gray-400"
                    }`}
                  >
                    {stage === "graph_generation" ? (
                      <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : stage === "complete" ? (
                      "✓"
                    ) : (
                      "2"
                    )}
                  </div>
                  <span className="text-xs text-gray-400 text-center">Graph Generation</span>
                </div>
              </div>

              {/* Current Progress */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-300">
                    {stage === "file_processing" && fileStatus?.status}
                    {stage === "graph_generation" && graphStatus?.status}
                    {stage === "complete" && "Complete!"}
                  </span>
                  <span className="text-sm font-medium text-blue-400">
                    {getProgressPercentage()}%
                  </span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-blue-600 h-full transition-all duration-500 rounded-full"
                    style={{ width: `${getProgressPercentage()}%` }}
                  ></div>
                </div>
              </div>

              {/* Detailed Status */}
              {stage === "file_processing" && fileStatus && (
                <div className="space-y-3">
                  {fileStatus.current_file && (
                    <div className="p-4 bg-gray-900 rounded-lg border border-gray-800">
                      <div className="text-xs text-gray-500 mb-1">Currently Processing:</div>
                      <div className="text-sm text-white font-medium truncate">
                        {fileStatus.current_file}
                      </div>
                    </div>
                  )}
                  {fileStatus.current !== undefined && fileStatus.total !== undefined && (
                    <div className="text-center text-sm text-gray-400">
                      Processing file {fileStatus.current} of {fileStatus.total}
                    </div>
                  )}
                </div>
              )}

              {stage === "graph_generation" && graphStatus && (
                <div className="space-y-3">
                  <div className="p-4 bg-gray-900 rounded-lg border border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">Status:</div>
                    <div className="text-sm text-white font-medium">
                      {graphStatus.status || "Generating embeddings and building connections..."}
                    </div>
                  </div>
                </div>
              )}

              {/* Failed Files Warning */}
              {fileStatus?.result?.failed_files &&
                fileStatus.result.failed_files.length > 0 && (
                  <div className="mt-6 p-4 bg-yellow-900/30 border border-yellow-700 rounded-lg">
                    <h3 className="font-semibold text-yellow-200 mb-2 flex items-center gap-2">
                      <span>⚠️</span> Some files failed to process
                    </h3>
                    <div className="max-h-40 overflow-y-auto space-y-2">
                      {fileStatus.result.failed_files.map((fail, index) => (
                        <div key={index} className="text-xs text-yellow-300">
                          <span className="font-medium">{fail.file}:</span> {fail.error}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Success Message */}
              {stage === "complete" && (
                <div className="mt-6 p-6 bg-green-900/30 border border-green-700 rounded-lg text-center">
                  <div className="text-6xl mb-4">🎉</div>
                  <h3 className="text-xl font-semibold text-green-200 mb-2">
                    Knowledge Graph Created!
                  </h3>
                  <p className="text-green-300 text-sm">
                    {graphStatus?.result?.nodes} documents connected with{" "}
                    {graphStatus?.result?.edges} relationships
                  </p>
                  <p className="text-gray-400 text-sm mt-2">Redirecting to graph view...</p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
