"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import * as d3 from "d3";
import { useGraphData, GraphNode as GraphNodeType, GraphEdge as GraphEdgeType } from "@/hooks/useGraph";

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  title: string;
  url: string;
  summary: string;
  tags: {
    high_level: string[];
    low_level: string[];
  };
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

  // Search and filter states
  const [searchPanelOpen, setSearchPanelOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
  const [selectedEntities, setSelectedEntities] = useState<Set<string>>(new Set());

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

  // Get unique tags and entities from graph data
  const { allTags, allHighLevelTags, allLowLevelTags, allEntities } = useMemo(() => {
    if (!graphData) return { allTags: [], allHighLevelTags: [], allLowLevelTags: [], allEntities: [] };

    const highLevelTags = Array.from(
      new Set(graphData.nodes.flatMap((node) => node.tags.high_level))
    ).sort();

    const lowLevelTags = Array.from(
      new Set(graphData.nodes.flatMap((node) => node.tags.low_level))
    ).sort();

    // Combine all tags for unified filtering
    const allTags = Array.from(
      new Set([...highLevelTags, ...lowLevelTags])
    ).sort();

    const entities = Array.from(
      new Set(graphData.nodes.flatMap((node) => node.entities))
    ).sort();

    return { allTags, allHighLevelTags: highLevelTags, allLowLevelTags: lowLevelTags, allEntities: entities };
  }, [graphData]);

  // Filter nodes based on search query and selected filters
  const shouldHighlightNode = useMemo(() => {
    return (node: GraphNode): boolean => {
      // If no filters active, highlight all
      if (
        !searchQuery &&
        selectedTags.size === 0 &&
        selectedEntities.size === 0
      ) {
        return true;
      }

      // Search query match (case-insensitive)
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesTitle = node.title.toLowerCase().includes(query);
        const matchesSummary = node.summary?.toLowerCase().includes(query);
        if (!matchesTitle && !matchesSummary) return false;
      }

      // Tag filter match (node must have at least one selected tag from either high or low level)
      if (selectedTags.size > 0) {
        const hasSelectedTag =
          node.tags.high_level.some((tag) => selectedTags.has(tag)) ||
          node.tags.low_level.some((tag) => selectedTags.has(tag));
        if (!hasSelectedTag) return false;
      }

      // Entity filter match (node must have at least one selected entity)
      if (selectedEntities.size > 0) {
        const hasSelectedEntity = node.entities.some((entity) =>
          selectedEntities.has(entity)
        );
        if (!hasSelectedEntity) return false;
      }

      return true;
    };
  }, [searchQuery, selectedTags, selectedEntities]);

  // Helper functions for tag/entity selection
  const toggleTag = (tag: string) => {
    setSelectedTags((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(tag)) {
        newSet.delete(tag);
      } else {
        newSet.add(tag);
      }
      return newSet;
    });
  };

  const toggleEntity = (entity: string) => {
    setSelectedEntities((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(entity)) {
        newSet.delete(entity);
      } else {
        newSet.add(entity);
      }
      return newSet;
    });
  };

  const clearAllFilters = () => {
    setSearchQuery("");
    setSelectedTags(new Set());
    setSelectedEntities(new Set());
  };

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

    // Extract unique high-level tags for color scale
    const allHighLevelTags = Array.from(
      new Set(graphData.nodes.flatMap((node) => node.tags.high_level))
    );
    const colorScale = d3.scaleOrdinal(d3.schemeCategory10).domain(allHighLevelTags);

    // Helper: Get primary color for a node based on its most common high-level tag
    const getNodeColor = (node: GraphNode): string => {
      if (node.tags.high_level.length === 0) return "#999";
      // Use the first high-level tag as primary color
      return colorScale(node.tags.high_level[0]) as string;
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
            // Closer nodes for higher similarity - reduced distance for denser graph
            return 50 / (d.similarity || 0.5);
          })
      )
      .force("charge", d3.forceManyBody().strength(-150)) // Reduced repulsion for denser packing
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius((d) => getNodeSize(d as GraphNode) + 2)); // Less padding between nodes

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
      .attr("opacity", (d) => (shouldHighlightNode(d) ? 1 : 0.2))
      .attr("stroke", (d) => (shouldHighlightNode(d) ? "#fff" : "none"))
      .attr("stroke-width", (d) => (shouldHighlightNode(d) ? 2 : 0))
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
      .attr("fill", "white")
      .attr("opacity", (d) => (shouldHighlightNode(d) ? 1 : 0.2))
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
          .attr("r", getNodeSize(d) * 1.5);

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
          .attr("r", getNodeSize(d));

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
  }, [graphData, shouldHighlightNode]);

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

      {/* Search panel toggle button */}
      <button
        onClick={() => setSearchPanelOpen(!searchPanelOpen)}
        className={`fixed top-4 bg-blue-600 text-white p-3 rounded-lg shadow-lg hover:bg-blue-700 transition-all duration-300 z-30 ${
          searchPanelOpen ? "right-[25rem]" : "right-4"
        }`}
        title="Toggle search panel"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </button>

      {/* Search and filter panel */}
      <div
        className={`fixed top-0 right-0 h-full bg-white shadow-2xl transition-transform duration-300 ease-in-out z-20 ${
          searchPanelOpen ? "translate-x-0" : "translate-x-full"
        } w-96 overflow-y-auto`}
      >
        <div className="p-6">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">Search & Filter</h2>
            <button
              onClick={() => setSearchPanelOpen(false)}
              className="text-gray-500 hover:text-gray-700 text-2xl"
            >
              ✕
            </button>
          </div>

          {/* Search by name */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Search by Name
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter document title..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="mt-2 text-sm text-blue-600 hover:text-blue-800"
              >
                Clear search
              </button>
            )}
          </div>

          {/* Filter by tags */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-semibold text-gray-700">
                Filter by Tags
              </label>
              {selectedTags.size > 0 && (
                <button
                  onClick={() => setSelectedTags(new Set())}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Clear all
                </button>
              )}
            </div>

            {/* High-level tags */}
            {allHighLevelTags.length > 0 && (
              <div className="mb-3">
                <h4 className="text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wide">
                  High-Level Tags
                </h4>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {allHighLevelTags.map((tag) => (
                    <label
                      key={`high-${tag}`}
                      className="flex items-center space-x-2 cursor-pointer hover:bg-blue-50 p-2 rounded"
                    >
                      <input
                        type="checkbox"
                        checked={selectedTags.has(tag)}
                        onChange={() => toggleTag(tag)}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 font-medium">{tag}</span>
                      <span className="text-xs text-gray-400 ml-auto">
                        ({graphData.nodes.filter((n) => n.tags.high_level.includes(tag)).length})
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Low-level tags */}
            {allLowLevelTags.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wide">
                  Low-Level Tags
                </h4>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {allLowLevelTags.map((tag) => (
                    <label
                      key={`low-${tag}`}
                      className="flex items-center space-x-2 cursor-pointer hover:bg-green-50 p-2 rounded"
                    >
                      <input
                        type="checkbox"
                        checked={selectedTags.has(tag)}
                        onChange={() => toggleTag(tag)}
                        className="w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500"
                      />
                      <span className="text-sm text-gray-700">{tag}</span>
                      <span className="text-xs text-gray-400 ml-auto">
                        ({graphData.nodes.filter((n) => n.tags.low_level.includes(tag)).length})
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {allTags.length === 0 && (
              <p className="text-sm text-gray-500 italic">No tags available</p>
            )}
          </div>

          {/* Filter by entities */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-semibold text-gray-700">
                Filter by Entities
              </label>
              {selectedEntities.size > 0 && (
                <button
                  onClick={() => setSelectedEntities(new Set())}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {allEntities.map((entity) => (
                <label
                  key={entity}
                  className="flex items-center space-x-2 cursor-pointer hover:bg-gray-50 p-2 rounded"
                >
                  <input
                    type="checkbox"
                    checked={selectedEntities.has(entity)}
                    onChange={() => toggleEntity(entity)}
                    className="w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500"
                  />
                  <span className="text-sm text-gray-700">{entity}</span>
                  <span className="text-xs text-gray-400 ml-auto">
                    ({graphData.nodes.filter((n) => n.entities.includes(entity)).length})
                  </span>
                </label>
              ))}
              {allEntities.length === 0 && (
                <p className="text-sm text-gray-500 italic">No entities available</p>
              )}
            </div>
          </div>

          {/* Active filters summary */}
          {(searchQuery || selectedTags.size > 0 || selectedEntities.size > 0) && (
            <div className="mb-6 p-4 bg-blue-50 rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-semibold text-gray-700">Active Filters</h3>
                <button
                  onClick={clearAllFilters}
                  className="text-xs text-red-600 hover:text-red-800"
                >
                  Clear all filters
                </button>
              </div>
              <div className="space-y-1 text-xs text-gray-600">
                {searchQuery && (
                  <div>Search: &quot;{searchQuery}&quot;</div>
                )}
                {selectedTags.size > 0 && (
                  <div>Tags: {selectedTags.size} selected</div>
                )}
                {selectedEntities.size > 0 && (
                  <div>Entities: {selectedEntities.size} selected</div>
                )}
                <div className="mt-2 font-semibold text-gray-700">
                  Showing{" "}
                  {graphData.nodes.filter(shouldHighlightNode).length} /{" "}
                  {graphData.nodes.length} nodes
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <div
          className={`absolute top-4 w-80 bg-white rounded-lg shadow-lg p-4 max-h-[80vh] overflow-y-auto transition-all duration-300 z-10 ${
            searchPanelOpen ? "left-4" : "right-4"
          }`}
        >
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

            {/* High-Level Tags */}
            {selectedNode.tags.high_level.length > 0 && (
              <div>
                <h3 className="font-semibold text-gray-700">High-Level Tags</h3>
                <div className="flex flex-wrap gap-1 mt-1">
                  {selectedNode.tags.high_level.map((tag, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        toggleTag(tag);
                        setSearchPanelOpen(true);
                      }}
                      className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200 transition-colors cursor-pointer font-medium"
                      title="Click to filter by this high-level tag"
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Low-Level Tags */}
            {selectedNode.tags.low_level.length > 0 && (
              <div>
                <h3 className="font-semibold text-gray-700">Low-Level Tags</h3>
                <div className="flex flex-wrap gap-1 mt-1">
                  {selectedNode.tags.low_level.map((tag, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        toggleTag(tag);
                        setSearchPanelOpen(true);
                      }}
                      className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs hover:bg-green-200 transition-colors cursor-pointer"
                      title="Click to filter by this low-level tag"
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <h3 className="font-semibold text-gray-700">Entities</h3>
              <div className="flex flex-wrap gap-1 mt-1">
                {selectedNode.entities.map((entity, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      toggleEntity(entity);
                      setSearchPanelOpen(true);
                    }}
                    className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs hover:bg-green-200 transition-colors cursor-pointer"
                    title="Click to filter by this entity"
                  >
                    {entity}
                  </button>
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
      <div className="absolute bottom-4 left-4 bg-white/90 rounded-lg shadow-lg p-3 max-w-xs">
        <h3 className="text-sm font-semibold mb-2">Controls</h3>
        <ul className="text-xs space-y-1 text-gray-700">
          <li>• Drag nodes to reposition</li>
          <li>• Scroll to zoom</li>
          <li>• Click & drag canvas to pan</li>
          <li>• Hover over nodes to highlight connections</li>
          <li>• Click nodes for details</li>
          <li>• Click search icon (top right) to filter graph</li>
          <li>• Click tags/entities in detail panel to add filters</li>
        </ul>
      </div>
    </div>
  );
}
