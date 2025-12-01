"""Graph API endpoints for knowledge graph visualization."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.workers.tasks import generate_knowledge_graph_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph")


class GenerateGraphRequest(BaseModel):
    """Request to generate knowledge graph."""

    documents_file: str = Field(
        ..., description="Path to extracted documents JSON file"
    )
    similarity_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score to create edge (only used if use_top_k_similarity=False)",
    )
    max_tags_per_doc: int = Field(
        default=5, ge=1, le=20, description="Maximum tags per document"
    )
    max_entities_per_doc: int = Field(
        default=10, ge=1, le=30, description="Maximum entities per document"
    )
    use_top_k_similarity: bool = Field(
        default=True,
        description="If True, use top-K neighbors approach instead of fixed threshold (recommended for denser graphs)",
    )
    top_k_neighbors: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Number of top similar documents per document (only used if use_top_k_similarity=True)",
    )
    min_similarity: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity to create edge in top-K mode (default: 0.3)",
    )
    enable_hierarchy: bool = Field(
        default=True,
        description="If True, build hierarchical tag structure with high/low level tags (default: True)",
    )
    hierarchy_split_threshold: int = Field(
        default=10,
        ge=5,
        le=50,
        description="Minimum documents per tag to consider splitting into sub-tags (default: 10)",
    )
    hierarchy_cross_cutting_threshold: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Minimum documents with tag combination to create cross-cutting tag (default: 5)",
    )


class GenerateGraphResponse(BaseModel):
    """Response when graph generation starts."""

    task_id: str
    message: str
    status: str


class GraphDataResponse(BaseModel):
    """Graph data for visualization."""

    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class GraphNode(BaseModel):
    """Single graph node (document)."""

    id: str
    title: str
    url: str
    summary: str
    tags: List[str]
    entities: List[str]
    author: str
    modified: str
    preview: str


class DocumentDetailsResponse(BaseModel):
    """Detailed document information."""

    id: str
    title: str
    url: str
    summary: str
    tags: List[str]
    entities: List[str]
    author: str
    modified: str
    preview: str


@router.post("/generate", response_model=GenerateGraphResponse)
async def generate_graph(
    request: GenerateGraphRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Start knowledge graph generation from extracted documents.

    This creates a Celery task that:
    1. Loads extracted documents from JSON
    2. Generates OpenAI embeddings
    3. Calculates similarity matrix
    4. Extracts LLM-based tags, summaries, and entities
    5. Builds graph structure
    6. Saves graph_data.json
    """
    logger.info(f"User {user_id} requested graph generation from {request.documents_file}")

    # Verify file exists
    docs_path = Path(request.documents_file)
    if not docs_path.exists():
        raise HTTPException(status_code=404, detail=f"Documents file not found: {request.documents_file}")

    # Start async task
    task = generate_knowledge_graph_task.apply_async(
        kwargs={
            "documents_file": request.documents_file,
            "similarity_threshold": request.similarity_threshold,
            "max_tags_per_doc": request.max_tags_per_doc,
            "max_entities_per_doc": request.max_entities_per_doc,
            "use_top_k_similarity": request.use_top_k_similarity,
            "top_k_neighbors": request.top_k_neighbors,
            "min_similarity": request.min_similarity,
            "enable_hierarchy": request.enable_hierarchy,
            "hierarchy_split_threshold": request.hierarchy_split_threshold,
            "hierarchy_cross_cutting_threshold": request.hierarchy_cross_cutting_threshold,
        }
    )

    return GenerateGraphResponse(
        task_id=task.id,
        message="Graph generation started",
        status="started",
    )


@router.get("/status/{task_id}")
async def get_graph_generation_status(task_id: str):
    """
    Check status of graph generation task.

    Returns:
        - PENDING: Task waiting to start
        - PROCESSING: Task in progress
        - SUCCESS: Task completed successfully
        - FAILURE: Task failed
    """
    task_result = AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {
            "task_id": task_id,
            "state": "PENDING",
            "status": "Waiting to start...",
        }

    elif task_result.state == "PROCESSING":
        # Get progress info
        info = task_result.info or {}
        return {
            "task_id": task_id,
            "state": "PROCESSING",
            "current": info.get("current", 0),
            "total": info.get("total", 0),
            "status": info.get("status", "Processing..."),
        }

    elif task_result.state == "SUCCESS":
        result = task_result.result
        return {
            "task_id": task_id,
            "state": "SUCCESS",
            "result": result,
        }

    elif task_result.state == "FAILURE":
        return {
            "task_id": task_id,
            "state": "FAILURE",
            "error": str(task_result.info),
        }

    else:
        return {
            "task_id": task_id,
            "state": task_result.state,
            "status": "Unknown state",
        }


@router.get("/data", response_model=GraphDataResponse)
async def get_graph_data(
    graph_file: Optional[str] = "processed_files/graph_data.json",
):
    """
    Get the current graph data for visualization.

    Returns complete graph structure with nodes and edges.
    """
    graph_path = Path(graph_file)

    if not graph_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Graph data not found. Please generate graph first.",
        )

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        logger.info(f"Serving graph with {len(graph_data['nodes'])} nodes and {len(graph_data['edges'])} edges")

        return GraphDataResponse(
            nodes=graph_data["nodes"],
            edges=graph_data["edges"],
            metadata=graph_data.get("metadata", {}),
        )

    except Exception as e:
        logger.error(f"Failed to load graph data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load graph data: {str(e)}")


@router.get("/documents/{doc_id}", response_model=DocumentDetailsResponse)
async def get_document_details(
    doc_id: str,
    graph_file: Optional[str] = "processed_files/graph_data.json",
):
    """
    Get detailed information for a specific document.

    Returns document metadata, tags, and preview.
    """
    graph_path = Path(graph_file)

    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Graph data not found")

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        # Find document
        document = next(
            (node for node in graph_data["nodes"] if node["id"] == doc_id),
            None,
        )

        if not document:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        return DocumentDetailsResponse(**document)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_documents(
    q: str,
    graph_file: Optional[str] = "processed_files/graph_data.json",
):
    """
    Search documents by title or preview content.

    Returns list of matching documents.
    """
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    graph_path = Path(graph_file)

    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Graph data not found")

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        # Search in titles and previews
        query_lower = q.lower()
        results = []

        for node in graph_data["nodes"]:
            # Handle both old flat tags and new hierarchical tags
            tags = node.get("tags", [])
            if isinstance(tags, dict):
                all_tags = tags.get("high_level", []) + tags.get("low_level", [])
            else:
                all_tags = tags

            if (query_lower in node["title"].lower()
                or query_lower in node.get("preview", "").lower()
                or any(query_lower in tag.lower() for tag in all_tags)):
                results.append(node)

        logger.info(f"Search '{q}' found {len(results)} results")

        return {"query": q, "results": results, "total": len(results)}

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tag-hierarchy")
async def get_tag_hierarchy(
    graph_file: Optional[str] = "processed_files/graph_data.json",
):
    """
    Get the tag hierarchy structure.

    Returns the tag hierarchy metadata showing high-level tags,
    their children, and cross-cutting tags.
    """
    graph_path = Path(graph_file)

    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Graph data not found")

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        metadata = graph_data.get("metadata", {})

        if not metadata.get("hierarchy_enabled"):
            return {
                "hierarchy_enabled": False,
                "message": "Tag hierarchy is not enabled for this graph",
            }

        tag_hierarchy = metadata.get("tag_hierarchy", {})

        if not tag_hierarchy:
            return {
                "hierarchy_enabled": True,
                "message": "No tag splits were created (all tags below threshold or LLM declined splitting)",
                "tag_hierarchy": {},
            }

        # Separate high-level and low-level tags for easier consumption
        high_level_tags = {
            tag: info for tag, info in tag_hierarchy.items()
            if info.get("type") == "high_level"
        }

        low_level_tags = {
            tag: info for tag, info in tag_hierarchy.items()
            if info.get("type") == "low_level"
        }

        cross_cutting_tags = {
            tag: info for tag, info in low_level_tags.items()
            if info.get("cross_cutting")
        }

        return {
            "hierarchy_enabled": True,
            "high_level_tags": high_level_tags,
            "low_level_tags": low_level_tags,
            "cross_cutting_tags": cross_cutting_tags,
            "total_high_level": len(high_level_tags),
            "total_low_level": len(low_level_tags),
            "total_cross_cutting": len(cross_cutting_tags),
        }

    except Exception as e:
        logger.error(f"Failed to get tag hierarchy: {e}")
        raise HTTPException(status_code=500, detail=str(e))
