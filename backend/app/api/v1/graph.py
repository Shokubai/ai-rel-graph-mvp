"""Graph API endpoints for knowledge graph visualization - PostgreSQL version."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.db.session import get_async_session
from app.repositories import (
    DocumentRepository,
    TagRepository,
    EntityRepository,
    SimilarityRepository,
)
from app.workers.tasks import generate_knowledge_graph_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph")


async def get_user_uuid(google_user_id: str, session: AsyncSession) -> UUID:
    """
    Convert Google user ID to User UUID by looking up in database.

    Args:
        google_user_id: Google user ID from JWT token
        session: Database session

    Returns:
        User UUID

    Raises:
        HTTPException: If user not found
    """
    from sqlalchemy import select
    from app.db.models.user import User

    user_result = await session.execute(
        select(User).filter(User.google_user_id == google_user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        logger.error(f"User not found with google_user_id: {google_user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    return user.id


class GraphDataResponse(BaseModel):
    """Graph data for visualization."""

    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class DocumentDetailsResponse(BaseModel):
    """Detailed document information."""

    id: str
    title: str
    url: str
    summary: str
    tags: Dict[str, List[str]]  # {"high_level": [...], "low_level": [...]}
    entities: List[str]
    author: str
    modified: str
    preview: str


class SearchResponse(BaseModel):
    """Search results."""

    query: str
    results: List[Dict[str, Any]]
    total: int


class TagHierarchyResponse(BaseModel):
    """Tag hierarchy structure."""

    hierarchy_enabled: bool
    high_level_tags: Dict[str, Any]
    total_high_level: int
    total_low_level: int


class GenerateGraphRequest(BaseModel):
    """Request to generate knowledge graph from processed documents."""

    documents_file: str = Field(..., description="Path to extracted documents JSON file")
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    max_tags_per_doc: int = Field(default=5, ge=1, le=20)
    max_entities_per_doc: int = Field(default=10, ge=1, le=30)
    use_top_k_similarity: bool = Field(default=True)
    top_k_neighbors: int = Field(default=2, ge=1, le=10)
    min_similarity: float = Field(default=0.3, ge=0.0, le=1.0)
    enable_hierarchy: bool = Field(default=True)
    hierarchy_split_threshold: int = Field(default=10, ge=5, le=50)
    hierarchy_cross_cutting_threshold: int = Field(default=5, ge=2, le=20)


class GenerateGraphResponse(BaseModel):
    """Response when graph generation starts."""

    task_id: str
    message: str
    status: str


@router.post("/generate", response_model=GenerateGraphResponse)
async def generate_graph(
    request: GenerateGraphRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Start knowledge graph generation from extracted documents.

    This creates a Celery task that will:
    1. Load extracted documents from JSON
    2. Generate OpenAI embeddings
    3. Extract LLM-based tags, summaries, and entities
    4. Calculate similarity matrix
    5. Save everything to PostgreSQL database

    The frontend polls /graph/status/{task_id} to check progress.
    """
    logger.info(f"User {user_id} requested graph generation from {request.documents_file}")

    # Start async task
    task = generate_knowledge_graph_task.apply_async(
        kwargs={
            "user_id": user_id,
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


@router.get("/documents")
async def list_documents(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
    enabled_only: bool = Query(default=False),
):
    """
    List all documents for the current user.

    Returns document metadata for the document manager UI.
    """
    try:
        user_uuid = await get_user_uuid(user_id, session)
        doc_repo = DocumentRepository(session)

        documents = await doc_repo.list_by_user(
            user_uuid, enabled_only=enabled_only, load_relations=True
        )

        results = []
        for doc in documents:
            # Build hierarchical tag structure
            high_level_tags = []
            low_level_tags = []

            for doc_tag in doc.tags:
                tag = doc_tag.tag
                if doc_tag.tag_level == "high":
                    high_level_tags.append(tag.name)
                elif doc_tag.tag_level == "low":
                    low_level_tags.append(tag.name)

            results.append({
                "id": doc.id,
                "title": doc.title,
                "url": doc.url or "",
                "summary": doc.summary or "",
                "tags": {
                    "high_level": sorted(high_level_tags),
                    "low_level": sorted(low_level_tags),
                },
                "author": doc.author or "Unknown",
                "modified": doc.modified_at.isoformat() if doc.modified_at else "",
                "is_enabled": doc.is_enabled,
            })

        logger.info(f"Listed {len(results)} documents for user {user_id}")

        return {"documents": results, "total": len(results)}

    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/delete-all")
async def delete_all_documents(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Delete all documents for the current user.

    This is a destructive operation that removes all documents,
    their tags, entities, and similarity relationships.
    """
    try:
        user_uuid = await get_user_uuid(user_id, session)
        doc_repo = DocumentRepository(session)

        # Get count before deletion
        documents = await doc_repo.list_by_user(user_uuid, enabled_only=False)
        count = len(documents)

        # Delete all documents (cascade will handle related records)
        await doc_repo.delete_all_for_user(user_uuid)
        await session.commit()

        logger.info(f"Deleted {count} documents for user {user_id}")

        return {"message": f"Deleted {count} documents", "count": count}

    except Exception as e:
        logger.error(f"Failed to delete all documents: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data", response_model=GraphDataResponse)
async def get_graph_data(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
    min_similarity: float = Query(default=0.7, ge=0.0, le=1.0),
    enabled_only: bool = Query(default=True),
):
    """
    Get the current graph data for visualization from PostgreSQL.

    Returns complete graph structure with nodes (documents) and edges (similarities).
    """
    try:
        # Convert Google user ID to UUID
        user_uuid = await get_user_uuid(user_id, session)

        # Initialize repositories
        doc_repo = DocumentRepository(session)
        similarity_repo = SimilarityRepository(session)

        # Get all documents for user
        documents = await doc_repo.list_by_user(
            user_uuid, enabled_only=enabled_only, load_relations=True
        )

        logger.info(
            f"Retrieved {len(documents)} documents for user {user_id} (enabled_only={enabled_only})"
        )

        # Build nodes
        nodes = []
        for doc in documents:
            # Build hierarchical tag structure
            high_level_tags = []
            low_level_tags = []

            for doc_tag in doc.tags:
                tag = doc_tag.tag
                if doc_tag.tag_level == "high":
                    high_level_tags.append(tag.name)
                elif doc_tag.tag_level == "low":
                    low_level_tags.append(tag.name)

            # Extract entity names
            entity_names = [doc_entity.entity.name for doc_entity in doc.entities]

            nodes.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "url": doc.url or "",
                    "summary": doc.summary or "",
                    "tags": {
                        "high_level": sorted(high_level_tags),
                        "low_level": sorted(low_level_tags),
                    },
                    "entities": entity_names,
                    "author": doc.author or "Unknown",
                    "modified": (
                        doc.modified_at.isoformat() if doc.modified_at else ""
                    ),
                    "preview": doc.summary or (doc.text_content or "")[:200] + "...",
                }
            )

        # Get all similarity edges for user
        similarities = await similarity_repo.get_all_for_user(
            user_uuid, min_score=min_similarity
        )

        logger.info(
            f"Retrieved {len(similarities)} similarity edges (min_similarity={min_similarity})"
        )

        # Build edges
        edges = []
        for sim in similarities:
            edges.append(
                {
                    "source": sim.source_document_id,
                    "target": sim.target_document_id,
                    "similarity": sim.similarity_score,
                    "type": "similar",
                }
            )

        # Build metadata
        metadata = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "min_similarity": min_similarity,
            "generated_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Serving graph: {len(nodes)} nodes, {len(edges)} edges to user {user_id}"
        )

        return GraphDataResponse(nodes=nodes, edges=edges, metadata=metadata)

    except Exception as e:
        logger.error(f"Failed to get graph data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load graph data: {str(e)}")


@router.get("/documents/{doc_id}", response_model=DocumentDetailsResponse)
async def get_document_details(
    doc_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get detailed information for a specific document.

    Returns document metadata, tags, entities, and preview.
    """
    try:
        user_uuid = await get_user_uuid(user_id, session)
        doc_repo = DocumentRepository(session)

        # Get document with relations
        document = await doc_repo.get_by_id(doc_id, user_uuid, load_relations=True)

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document not found: {doc_id}"
            )

        # Build hierarchical tag structure
        high_level_tags = []
        low_level_tags = []

        for doc_tag in document.tags:
            tag = doc_tag.tag
            if doc_tag.tag_level == "high":
                high_level_tags.append(tag.name)
            elif doc_tag.tag_level == "low":
                low_level_tags.append(tag.name)

        # Extract entity names
        entity_names = [doc_entity.entity.name for doc_entity in document.entities]

        return DocumentDetailsResponse(
            id=document.id,
            title=document.title,
            url=document.url or "",
            summary=document.summary or "",
            tags={"high_level": sorted(high_level_tags), "low_level": sorted(low_level_tags)},
            entities=entity_names,
            author=document.author or "Unknown",
            modified=document.modified_at.isoformat() if document.modified_at else "",
            preview=document.summary or (document.text_content or "")[:200] + "...",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=2),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
    enabled_only: bool = Query(default=True),
):
    """
    Search documents by title, summary, or content.

    Also searches in tags and entities.
    """
    try:
        user_uuid = await get_user_uuid(user_id, session)
        doc_repo = DocumentRepository(session)

        # Search by text
        documents = await doc_repo.search_by_text(q, user_uuid, enabled_only)

        # Build results
        results = []
        for doc in documents:
            # Build hierarchical tag structure
            high_level_tags = []
            low_level_tags = []

            for doc_tag in doc.tags:
                tag = doc_tag.tag
                if doc_tag.tag_level == "high":
                    high_level_tags.append(tag.name)
                elif doc_tag.tag_level == "low":
                    low_level_tags.append(tag.name)

            # Extract entity names
            entity_names = [doc_entity.entity.name for doc_entity in doc.entities]

            results.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "url": doc.url or "",
                    "summary": doc.summary or "",
                    "tags": {
                        "high_level": sorted(high_level_tags),
                        "low_level": sorted(low_level_tags),
                    },
                    "entities": entity_names,
                    "author": doc.author or "Unknown",
                    "modified": doc.modified_at.isoformat() if doc.modified_at else "",
                    "preview": doc.summary or (doc.text_content or "")[:200] + "...",
                }
            )

        logger.info(f"Search '{q}' found {len(results)} results for user {user_id}")

        return SearchResponse(query=q, results=results, total=len(results))

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
    enabled_only: bool = Query(default=True),
):
    """
    Semantic search using embeddings and vector similarity.

    Finds documents similar to the query text.
    """
    try:
        from openai import OpenAI
        from app.core.config import settings

        user_uuid = await get_user_uuid(user_id, session)
        doc_repo = DocumentRepository(session)

        # Generate embedding for query
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(model="text-embedding-3-small", input=q)

        query_embedding = response.data[0].embedding

        # Search similar documents
        results = await doc_repo.search_similar(
            embedding=query_embedding,
            user_id=user_uuid,
            limit=limit,
            enabled_only=enabled_only,
            min_similarity=0.0,  # Return all results sorted by similarity
        )

        # Build response
        search_results = []
        for doc, similarity in results:
            search_results.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "summary": doc.summary or "",
                    "similarity": round(similarity, 4),
                    "url": doc.url or "",
                }
            )

        logger.info(
            f"Semantic search '{q}' found {len(search_results)} results for user {user_id}"
        )

        return {"query": q, "results": search_results, "total": len(search_results)}

    except Exception as e:
        logger.error(f"Semantic search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tag-hierarchy", response_model=TagHierarchyResponse)
async def get_tag_hierarchy(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get the tag hierarchy structure.

    Returns high-level tags, their children, and orphan counts.
    """
    try:
        user_uuid = await get_user_uuid(user_id, session)
        tag_repo = TagRepository(session)

        # Get full hierarchy
        hierarchy = await tag_repo.get_hierarchy(user_uuid)

        high_level_tags = hierarchy.get("high_level", {})
        total_low_level = sum(
            len(tag_data.get("children", [])) for tag_data in high_level_tags.values()
        )

        logger.info(
            f"Retrieved tag hierarchy for user {user_id}: "
            f"{len(high_level_tags)} high-level tags, {total_low_level} low-level tags"
        )

        return TagHierarchyResponse(
            hierarchy_enabled=True,
            high_level_tags=high_level_tags,
            total_high_level=len(high_level_tags),
            total_low_level=total_low_level,
        )

    except Exception as e:
        logger.error(f"Failed to get tag hierarchy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{doc_id}/toggle")
async def toggle_document_enabled(
    doc_id: str,
    enabled: bool = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Enable or disable a document's visibility in the graph.

    Does not delete the document, just hides it from visualization.
    """
    try:
        user_uuid = await get_user_uuid(user_id, session)
        doc_repo = DocumentRepository(session)

        document = await doc_repo.toggle_enabled(doc_id, user_uuid, enabled)

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document not found: {doc_id}"
            )

        await session.commit()

        logger.info(
            f"User {user_id} {'enabled' if enabled else 'disabled'} document {doc_id}"
        )

        return {
            "id": document.id,
            "title": document.title,
            "is_enabled": document.is_enabled,
            "message": f"Document {'enabled' if enabled else 'disabled'} successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle document: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
