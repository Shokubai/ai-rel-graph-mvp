"""Semantic processing endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.file import File
from app.models.job import ProcessingJob
from app.workers.tasks import (
    process_files_semantically,
    generate_embeddings,
    create_semantic_relationships,
    cluster_documents,
)


router: APIRouter = APIRouter()


# Request/Response Models
class ProcessFilesRequest(BaseModel):
    """Request model for processing files."""
    file_ids: List[str] = Field(..., description="List of file IDs to process")
    similarity_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Similarity threshold")
    create_job: bool = Field(True, description="Whether to create a processing job for tracking")


class ProcessFilesResponse(BaseModel):
    """Response model for file processing."""
    task_id: str
    job_id: Optional[str] = None
    message: str


class EmbeddingRequest(BaseModel):
    """Request model for generating embeddings."""
    file_ids: List[str] = Field(..., description="List of file IDs")
    model_name: str = Field("all-MiniLM-L6-v2", description="Sentence transformer model")


class RelationshipRequest(BaseModel):
    """Request model for creating relationships."""
    file_ids: List[str] = Field(..., description="List of file IDs")
    similarity_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Similarity threshold")


class ClusterRequest(BaseModel):
    """Request model for clustering."""
    file_ids: List[str] = Field(..., description="List of file IDs to cluster")


class TaskResponse(BaseModel):
    """Response model for async tasks."""
    task_id: str
    message: str


# Endpoints
@router.post("/process", response_model=ProcessFilesResponse)
async def process_files(
    request: ProcessFilesRequest,
    db: Session = Depends(get_db),
) -> ProcessFilesResponse:
    """
    Process files through full semantic pipeline.

    This endpoint:
    1. Generates embeddings for files
    2. Creates semantic relationships
    3. Performs community detection clustering
    4. Names clusters based on content

    The process runs asynchronously via Celery.
    """
    # Validate files exist
    files = db.query(File).filter(File.id.in_(request.file_ids)).all()

    if not files:
        raise HTTPException(status_code=404, detail="No files found with provided IDs")

    if len(files) != len(request.file_ids):
        raise HTTPException(
            status_code=400,
            detail=f"Only {len(files)} of {len(request.file_ids)} files found"
        )

    # Create processing job if requested
    job_id = None
    if request.create_job:
        job = ProcessingJob(
            folder_id="api_request",
            status="queued",
            total_files=len(files),
            processed_files=0,
            progress_percentage=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = str(job.id)

    # Start async task
    task = process_files_semantically.delay(
        file_ids=request.file_ids,
        job_id=job_id,
        similarity_threshold=request.similarity_threshold,
    )

    return ProcessFilesResponse(
        task_id=task.id,
        job_id=job_id,
        message=f"Processing {len(files)} files. Track progress with task_id or job_id.",
    )


@router.post("/embeddings", response_model=TaskResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """
    Generate embeddings for files.

    This is Step 1 of the semantic pipeline. Files must have text_content.
    """
    # Validate files exist and have content
    files = db.query(File).filter(File.id.in_(request.file_ids)).all()

    if not files:
        raise HTTPException(status_code=404, detail="No files found with provided IDs")

    files_without_content = [f for f in files if not f.text_content]
    if files_without_content:
        raise HTTPException(
            status_code=400,
            detail=f"{len(files_without_content)} files have no text_content"
        )

    # Start async task
    task = generate_embeddings.delay(
        file_ids=request.file_ids,
        model_name=request.model_name,
    )

    return TaskResponse(
        task_id=task.id,
        message=f"Generating embeddings for {len(files)} files.",
    )


@router.post("/relationships", response_model=TaskResponse)
async def create_relationships(
    request: RelationshipRequest,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """
    Create semantic relationships between files.

    This is Step 2 of the semantic pipeline. Files must have embeddings.
    """
    # Validate files exist and have embeddings
    files = db.query(File).filter(
        File.id.in_(request.file_ids),
        File.embedding.isnot(None)
    ).all()

    if not files:
        raise HTTPException(
            status_code=404,
            detail="No files found with embeddings. Generate embeddings first."
        )

    if len(files) != len(request.file_ids):
        missing = len(request.file_ids) - len(files)
        raise HTTPException(
            status_code=400,
            detail=f"{missing} files missing embeddings. Generate embeddings first."
        )

    # Start async task
    task = create_semantic_relationships.delay(
        file_ids=request.file_ids,
        similarity_threshold=request.similarity_threshold,
    )

    return TaskResponse(
        task_id=task.id,
        message=f"Creating semantic relationships for {len(files)} files.",
    )


@router.post("/cluster", response_model=TaskResponse)
async def cluster_files(
    request: ClusterRequest,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """
    Create clusters from existing relationships using community detection.

    This is Step 3 of the semantic pipeline. Files must have relationships.
    """
    from app.models.relationship import FileRelationship

    # Validate files exist
    files = db.query(File).filter(File.id.in_(request.file_ids)).all()

    if not files:
        raise HTTPException(status_code=404, detail="No files found with provided IDs")

    # Check if relationships exist
    relationships = db.query(FileRelationship).filter(
        (FileRelationship.source_file_id.in_(request.file_ids)) |
        (FileRelationship.target_file_id.in_(request.file_ids))
    ).limit(1).all()

    if not relationships:
        raise HTTPException(
            status_code=400,
            detail="No relationships found. Create relationships first."
        )

    # Start async task
    task = cluster_documents.delay(file_ids=request.file_ids)

    return TaskResponse(
        task_id=task.id,
        message=f"Clustering {len(files)} files using community detection.",
    )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str) -> dict:
    """
    Get status of an async task.

    Returns task state and result if completed.
    """
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app

    task = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "state": task.state,
        "ready": task.ready(),
    }

    if task.ready():
        if task.successful():
            response["result"] = task.result
        else:
            response["error"] = str(task.info)

    return response
