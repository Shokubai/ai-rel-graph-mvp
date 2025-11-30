"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import * as d3 from "d3";
import { useGraphData, GraphNode as GraphNodeType, GraphEdge as GraphEdgeType } from "@/hooks/useGraph";

interface GraphNode extends d3.SimulationNodeDatum {
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

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  similarity: number;
  type: string;
}

interface GraphViewProps {
  uploadedData?: {
    nodes: GraphNodeType[];
    edges: GraphEdgeType[];
    metadata?: Record<string, unknown>;
  } | null;
}

export function GraphView({ uploadedData }: GraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { data: graphDataResponse, isLoading, error } = useGraphData();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Extract graph data from API response or uploaded data with useMemo
  const graphData = useMemo(() => {
    // Prefer uploaded data if available
    if (uploadedData) {
      return {
        nodes: uploadedData.nodes as GraphNode[],
        edges: uploadedData.edges,
      };
    }

    // Otherwise use API data
    if (!graphDataResponse) return null;
    return {
      nodes: graphDataResponse.nodes as GraphNode[],
      edges: graphDataResponse.edges,
    };
  }, [uploadedData, graphDataResponse]);

  // Initialize D3 force graph
  useEffect(() => {
    if (!graphData || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous render

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Create zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 10])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Main group for zoom/pan
    const g = svg.append("g");

    // Extract unique tags for color scale
    const allTags = Array.from(
      new Set(graphData.nodes.flatMap((node) => node.tags))
    );
    const colorScale = d3.scaleOrdinal(d3.schemeCategory10).domain(allTags);

    // Helper: Get primary color for a node based on its most common tag
    const getNodeColor = (node: GraphNode): string => {
      if (node.tags.length === 0) return "#999";
      // Use the first tag as primary color
      return colorScale(node.tags[0]) as string;
    };

    // Calculate node size based on number of connections and entities
    const getNodeSize = (node: GraphNode): number => {
      const connectionCount = graphData.edges.filter(
        (e) => {
          const sourceId = typeof e.source === "string" ? e.source : (e.source as GraphNode).id;
          const targetId = typeof e.target === "string" ? e.target : (e.target as GraphNode).id;
          return sourceId === node.id || targetId === node.id;
        }
      ).length;
      const entityCount = node.entities.length;
      // Base size + scale by connections and entities
      return 5 + Math.sqrt(connectionCount * 2 + entityCount);
    };

    // Create force simulation
    const simulation = d3
      .forceSimulation<GraphNode>(graphData.nodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, GraphEdge>(graphData.edges)
          .id((d) => d.id)
          .distance((d) => {
            // Closer nodes for higher similarity
            return 100 / (d.similarity || 0.5);
          })
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius((d) => getNodeSize(d as GraphNode) + 5));

    // Create edges
    const link = g
      .append("g")
      .selectAll("line")
      .data(graphData.edges)
      .join("line")
      .attr("stroke", "#999")
      .attr("stroke-opacity", (d) => d.similarity * 0.6)
      .attr("stroke-width", (d) => Math.sqrt(d.similarity) * 2);

    // Create nodes
    const node = g
      .append("g")
      .selectAll("circle")
      .data(graphData.nodes)
      .join("circle")
      .attr("r", (d) => getNodeSize(d))
      .attr("fill", (d) => getNodeColor(d))
      .attr("stroke", "#fff")
      .attr("stroke-width", 2)
      .style("cursor", "pointer");

    // Add drag behavior
    const dragBehavior = d3
      .drag<SVGCircleElement, GraphNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    node.call(dragBehavior as never);

    // Add labels
    const labels = g
      .append("g")
      .selectAll("text")
      .data(graphData.nodes)
      .join("text")
      .text((d) => d.title)
      .attr("font-size", 10)
      .attr("dx", (d) => getNodeSize(d) + 5)
      .attr("dy", 4)
      .style("pointer-events", "none")
      .style("user-select", "none");

    // Hover effects
    node
      .on("mouseenter", function (_event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("r", getNodeSize(d) * 1.5)
          .attr("stroke-width", 3);

        // Highlight connected edges
        link
          .transition()
          .duration(200)
          .attr("stroke-opacity", (e) => {
            const sourceId = typeof e.source === "string" ? e.source : (e.source as GraphNode).id;
            const targetId = typeof e.target === "string" ? e.target : (e.target as GraphNode).id;
            const isConnected = sourceId === d.id || targetId === d.id;
            return isConnected ? 1 : 0.1;
          })
          .attr("stroke-width", (e) => {
            const sourceId = typeof e.source === "string" ? e.source : (e.source as GraphNode).id;
            const targetId = typeof e.target === "string" ? e.target : (e.target as GraphNode).id;
            const isConnected = sourceId === d.id || targetId === d.id;
            return isConnected ? Math.sqrt(e.similarity) * 4 : Math.sqrt(e.similarity) * 2;
          });

        // Highlight connected nodes
        node
          .transition()
          .duration(200)
          .attr("opacity", (n) => {
            const isConnected = graphData.edges.some(
              (e) => {
                const sourceId = typeof e.source === "string" ? e.source : (e.source as GraphNode).id;
                const targetId = typeof e.target === "string" ? e.target : (e.target as GraphNode).id;
                return (
                  (sourceId === d.id && targetId === n.id) ||
                  (targetId === d.id && sourceId === n.id)
                );
              }
            );
            return n.id === d.id || isConnected ? 1 : 0.3;
          });
      })
      .on("mouseleave", function (_event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("r", getNodeSize(d))
          .attr("stroke-width", 2);

        link
          .transition()
          .duration(200)
          .attr("stroke-opacity", (e) => e.similarity * 0.6)
          .attr("stroke-width", (e) => Math.sqrt(e.similarity) * 2);

        node.transition().duration(200).attr("opacity", 1);
      })
      .on("click", (_event, d) => {
        setSelectedNode(d);
      });

    // Update positions on simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d) =>
          typeof d.source === "string" ? 0 : (d.source as GraphNode).x || 0
        )
        .attr("y1", (d) =>
          typeof d.source === "string" ? 0 : (d.source as GraphNode).y || 0
        )
        .attr("x2", (d) =>
          typeof d.target === "string" ? 0 : (d.target as GraphNode).x || 0
        )
        .attr("y2", (d) =>
          typeof d.target === "string" ? 0 : (d.target as GraphNode).y || 0
        );

      node.attr("cx", (d) => d.x || 0).attr("cy", (d) => d.y || 0);

      labels.attr("x", (d) => d.x || 0).attr("y", (d) => d.y || 0);
    });

    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [graphData]);

  // Show loading state (only if no uploaded data)
  if (!uploadedData && isLoading) {
    return (
      <div className="relative w-full h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white text-xl">Loading graph data...</div>
      </div>
    );
  }

  // Show error state (only if no uploaded data)
  if (!uploadedData && error) {
    return (
      <div className="relative w-full h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-red-400 text-xl">
          Error loading graph: {error.message}
        </div>
      </div>
    );
  }

  // Show empty state
  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="relative w-full h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white text-center">
          <div className="text-xl mb-2">No graph data available</div>
          <div className="text-gray-400">
            Process some files and generate a graph to visualize
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-screen bg-gray-900">
      <svg ref={svgRef} className="w-full h-full" />

      {/* Node detail panel */}
      {selectedNode && (
        <div className="absolute top-4 right-4 w-80 bg-white rounded-lg shadow-lg p-4 max-h-[80vh] overflow-y-auto">
          <div className="flex justify-between items-start mb-2">
            <h2 className="text-lg font-bold">{selectedNode.title}</h2>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-500 hover:text-gray-700"
            >
              ✕
            </button>
          </div>

          <div className="space-y-3 text-sm">
            <div>
              <h3 className="font-semibold text-gray-700">Summary</h3>
              <p className="text-gray-600">{selectedNode.summary}</p>
            </div>

            <div>
              <h3 className="font-semibold text-gray-700">Tags</h3>
              <div className="flex flex-wrap gap-1 mt-1">
                {selectedNode.tags.map((tag, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-700">Entities</h3>
              <div className="flex flex-wrap gap-1 mt-1">
                {selectedNode.entities.map((entity, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs"
                  >
                    {entity}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-700">Author</h3>
              <p className="text-gray-600">{selectedNode.author}</p>
            </div>

            <div>
              <h3 className="font-semibold text-gray-700">Last Modified</h3>
              <p className="text-gray-600">
                {new Date(selectedNode.modified).toLocaleDateString()}
              </p>
            </div>

            <a
              href={selectedNode.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center bg-blue-500 text-white py-2 rounded hover:bg-blue-600 transition-colors"
            >
              Open Document
            </a>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-white/90 rounded-lg shadow-lg p-3">
        <h3 className="text-sm font-semibold mb-2">Controls</h3>
        <ul className="text-xs space-y-1 text-gray-700">
          <li>• Drag nodes to reposition</li>
          <li>• Scroll to zoom</li>
          <li>• Click & drag canvas to pan</li>
          <li>• Hover over nodes to highlight connections</li>
          <li>• Click nodes for details</li>
        </ul>
      </div>
    </div>
  );
}
