"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Navbar } from "@/components/Navbar";
import { GraphView } from "@/components/GraphView";
import { FileExplorer } from "@/components/FileExplorer";
import { ProcessingStatus } from "@/components/ProcessingStatus";
import { GraphNode, GraphEdge } from "@/hooks/useGraph";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, unknown>;
}

type AppState = "explorer" | "processing" | "graph" | "empty";

export default function Home() {
  const { data: session, status } = useSession();
  const [appState, setAppState] = useState<AppState>("empty");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [processingTaskId, setProcessingTaskId] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated" && session && appState === "empty") {
      // Only transition to explorer on initial authentication
      // Don't reset state on session updates (e.g., when window refocuses)
      setAppState("explorer");
    } else if (status === "unauthenticated") {
      setAppState("empty");
    }
  }, [status, session, appState]);

  const handleUpdateFiles = () => {
    // Show file explorer to select new files
    setAppState("explorer");
  };

  const handleProcessingStart = (taskId: string) => {
    setProcessingTaskId(taskId);
    setAppState("processing");
  };

  const handleProcessingComplete = () => {
    setAppState("graph");
    setProcessingTaskId(null);
  };

  const handleGraphDataUpload = (uploadedData: GraphData) => {
    setGraphData(uploadedData);
    setAppState("graph");
  };

  const handleBackToExplorer = () => {
    setAppState("explorer");
    setProcessingTaskId(null);
  };

  return (
    <div className="h-screen bg-gray-900 flex flex-col overflow-hidden">
      {/* Navbar */}
      <Navbar onUpdateClick={handleUpdateFiles} />

      {/* Main content - different views based on state */}
      <main className="flex-1 overflow-hidden">
        {appState === "empty" && (
          <div className="w-full h-full flex items-center justify-center bg-gray-900">
            <div className="text-center max-w-md px-6">
              <div className="text-6xl mb-6">🔒</div>
              <h1 className="text-3xl font-bold text-white mb-4">Sign In to Get Started</h1>
              <p className="text-gray-400 text-lg">
                Sign in with your Google account to create a knowledge graph from your Google Drive
                files
              </p>
            </div>
          </div>
        )}

        {appState === "explorer" && (
          <FileExplorer
            onProcessingStart={handleProcessingStart}
            onGraphDataUpload={handleGraphDataUpload}
          />
        )}

        {appState === "processing" && processingTaskId && (
          <ProcessingStatus
            fileProcessingTaskId={processingTaskId}
            onComplete={handleProcessingComplete}
            onBack={handleBackToExplorer}
          />
        )}

        {appState === "graph" && <GraphView uploadedData={graphData} />}
      </main>
    </div>
  );
}
