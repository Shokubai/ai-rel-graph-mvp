"use client";

import { useState } from "react";
import { DriveFileBrowser } from "@/components/DriveFileBrowser";
import { GraphView } from "@/components/GraphView";
import { GraphNode, GraphEdge } from "@/hooks/useGraph";

interface UploadedGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, unknown>;
}

export default function Home() {
  const [view, setView] = useState<"files" | "graph">("files");
  const [uploadedGraphData, setUploadedGraphData] = useState<UploadedGraphData | null>(null);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with navigation */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">
              AI Knowledge Graph
            </h1>
            <nav className="flex gap-2">
              <button
                onClick={() => setView("files")}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  view === "files"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                Files
              </button>
              <button
                onClick={() => setView("graph")}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  view === "graph"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                Graph View
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main>
        {view === "files" && (
          <div className="max-w-6xl mx-auto p-8 space-y-6">
            {/* File Upload Section */}
            <div className="border rounded-lg shadow-lg bg-white p-6">
              <h2 className="text-xl font-bold mb-4">Upload Graph Data</h2>
              <p className="text-gray-600 mb-4">
                Upload a graph_data.json file to visualize your knowledge graph
              </p>
              <input
                type="file"
                accept=".json"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                      try {
                        const data = JSON.parse(event.target?.result as string);
                        setUploadedGraphData(data);
                        setView("graph");
                      } catch (error) {
                        console.error("Failed to parse JSON:", error);
                        alert("Invalid JSON file. Please upload a valid graph_data.json file.");
                      }
                    };
                    reader.readAsText(file);
                  }
                }}
                className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none"
              />
            </div>

            {/* Google Drive Browser */}
            <div className="border rounded-lg shadow-lg bg-white">
              <DriveFileBrowser onGraphGenerated={() => setView("graph")} />
            </div>
          </div>
        )}

        {view === "graph" && <GraphView uploadedData={uploadedGraphData} />}
      </main>
    </div>
  );
}
