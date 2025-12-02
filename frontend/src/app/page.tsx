"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";
import { Navbar } from "@/components/Navbar";
import { GraphView } from "@/components/GraphView";
import { ProcessingStatus } from "@/components/ProcessingStatus";
import DocumentManager from "@/components/DocumentManager";
import { useGraphData } from "@/hooks/useGraph";

type AppState = "explorer" | "processing" | "graph" | "empty" | "loading";

export default function Home() {
  const { data: session, status } = useSession();
  const queryClient = useQueryClient();
  const [appState, setAppState] = useState<AppState>("empty");
  const [processingTaskId, setProcessingTaskId] = useState<string | null>(null);
  const { data: existingGraphData, isLoading: isLoadingGraph } = useGraphData();

  useEffect(() => {
    if (status === "authenticated" && session && appState === "empty") {
      // Check if graph data exists in database
      setAppState("loading");
    } else if (status === "unauthenticated") {
      setAppState("empty");
    }
  }, [status, session, appState]);

  // Once graph data is loaded, decide which view to show
  useEffect(() => {
    if (appState === "loading" && !isLoadingGraph) {
      if (existingGraphData && existingGraphData.nodes.length > 0) {
        // Graph data exists, show graph view automatically
        setAppState("graph");
      } else {
        // No graph data, show explorer
        setAppState("explorer");
      }
    }
  }, [appState, isLoadingGraph, existingGraphData]);

  const handleUpdateFiles = () => {
    // Show file explorer to select new files
    setAppState("explorer");
  };

  const handleProcessingStart = (taskId: string) => {
    setProcessingTaskId(taskId);
    setAppState("processing");
  };

  const handleProcessingComplete = () => {
    // Invalidate graph data to force refresh with new documents
    queryClient.invalidateQueries({ queryKey: ["graph-data"] });
    setAppState("graph");
    setProcessingTaskId(null);
  };

  const handleBackToExplorer = () => {
    setAppState("explorer");
    setProcessingTaskId(null);
  };

  const handleDocumentToggle = () => {
    // Invalidate graph data to trigger refresh
    queryClient.invalidateQueries({ queryKey: ["graph-data"] });
  };

  const handleCloseDocumentManager = () => {
    setAppState("graph");
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
          <DocumentManager
            onDocumentToggle={handleDocumentToggle}
            onProcessingStart={handleProcessingStart}
            onClose={handleCloseDocumentManager}
          />
        )}

        {appState === "processing" && processingTaskId && (
          <ProcessingStatus
            fileProcessingTaskId={processingTaskId}
            onComplete={handleProcessingComplete}
            onBack={handleBackToExplorer}
          />
        )}

        {appState === "graph" && <GraphView uploadedData={null} />}
      </main>
    </div>
  );
}
