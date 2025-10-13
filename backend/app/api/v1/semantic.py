"""Tag-based processing endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.file import File
from app.models.job import ProcessingJob
from app.workers.tasks import (
    process_files_with_tags,
    extract_tags_task,
    create_tag_relationships,
    cluster_documents,
)


router: APIRouter = APIRouter()


# Request/Response Models
class ProcessFilesRequest(BaseModel):
    """Request model for processing files."""
    file_ids: List[str] = Field(..., description="List of file IDs to process")
    min_shared_tags: int = Field(2, ge=1, description="Minimum number of shared tags to create a relationship")
    create_job: bool = Field(True, description="Whether to create a processing job for tracking")


class ProcessFilesResponse(BaseModel):
    """Response model for file processing."""
    task_id: str
    job_id: Optional[str] = None
    message: str


class TagExtractionRequest(BaseModel):
    """Request model for extracting tags."""
    file_ids: List[str] = Field(..., description="List of file IDs")
    min_tag_frequency: int = Field(2, ge=1, description="Minimum word frequency for tag extraction")
    max_tags_per_doc: int = Field(10, ge=1, le=50, description="Maximum tags per document")


class RelationshipRequest(BaseModel):
    """Request model for creating relationships."""
    file_ids: List[str] = Field(..., description="List of file IDs")
    min_shared_tags: int = Field(2, ge=1, description="Minimum number of shared tags")


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
    Process files through full tag-based pipeline.

    This endpoint:
    1. Extracts tags from document text
    2. Creates relationships based on shared tags
    3. Performs community detection clustering
    4. Names clusters based on common tags

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
    task = process_files_with_tags.delay(
        file_ids=request.file_ids,
        job_id=job_id,
        min_shared_tags=request.min_shared_tags,
    )

    return ProcessFilesResponse(
        task_id=task.id,
        job_id=job_id,
        message=f"Processing {len(files)} files with tag extraction. Track progress with task_id or job_id.",
    )


@router.post("/tags", response_model=TaskResponse)
async def extract_tags(
    request: TagExtractionRequest,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """
    Extract tags from files.

    This is Step 1 of the tag-based pipeline. Files must have text_content.
    Tags are extracted using NLP-based keyword extraction and categorization.
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
    task = extract_tags_task.delay(
        file_ids=request.file_ids,
        min_tag_frequency=request.min_tag_frequency,
        max_tags_per_doc=request.max_tags_per_doc,
    )

    return TaskResponse(
        task_id=task.id,
        message=f"Extracting tags from {len(files)} files.",
    )


@router.post("/relationships", response_model=TaskResponse)
async def create_relationships(
    request: RelationshipRequest,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """
    Create tag-based relationships between files.

    This is Step 2 of the tag-based pipeline. Files must have tags.
    Relationships are created when files share a minimum number of tags.
    """
    from app.models.file_tag import FileTag

    # Validate files exist and have tags
    files_with_tags = db.query(File).join(FileTag).filter(
        File.id.in_(request.file_ids)
    ).distinct().all()

    if not files_with_tags:
        raise HTTPException(
            status_code=404,
            detail="No files found with tags. Extract tags first."
        )

    if len(files_with_tags) != len(request.file_ids):
        missing = len(request.file_ids) - len(files_with_tags)
        raise HTTPException(
            status_code=400,
            detail=f"{missing} files missing tags. Extract tags first."
        )

    # Start async task
    task = create_tag_relationships.delay(
        file_ids=request.file_ids,
        min_shared_tags=request.min_shared_tags,
    )

    return TaskResponse(
        task_id=task.id,
        message=f"Creating tag-based relationships for {len(files_with_tags)} files.",
    )


@router.post("/cluster", response_model=TaskResponse)
async def cluster_files(
    request: ClusterRequest,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """
    Create clusters from existing relationships using community detection.

    This is Step 3 of the tag-based pipeline. Files must have relationships.
    Clusters are named based on the most common tags within each community.
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
        message=f"Clustering {len(files)} files using community detection on tag relationships.",
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
