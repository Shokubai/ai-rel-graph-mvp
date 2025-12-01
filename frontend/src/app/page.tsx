"use client";

import { useState } from "react";
import { Navbar } from "@/components/Navbar";
import { GraphView } from "@/components/GraphView";
import { GraphNode, GraphEdge } from "@/hooks/useGraph";

interface UploadedGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, unknown>;
}

export default function Home() {
  const [uploadedGraphData, setUploadedGraphData] = useState<UploadedGraphData | null>(null);

  const handleUpdateFiles = async () => {
    // TODO: Implement API call to check for new files in Google Drive
    console.log("Checking for new files...");
    // This will trigger a backend API call to sync Google Drive files
    alert("Checking for new files from Google Drive...");
  };

  return (
    <div className="h-screen bg-gray-900 flex flex-col overflow-hidden">
      {/* Navbar */}
      <Navbar onUpdateClick={handleUpdateFiles} />

      {/* Main content - Graph View */}
      <main className="flex-1 overflow-hidden">
        <GraphView uploadedData={uploadedGraphData} />
      </main>
    </div>
  );
}
