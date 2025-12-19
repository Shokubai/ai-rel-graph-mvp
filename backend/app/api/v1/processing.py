"""
File Processing API Endpoints

This module provides endpoints to trigger and monitor file processing tasks.
"""

import base64
import logging
import uuid
from typing import List, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.workers.tasks import process_drive_files_task, process_uploaded_files_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/processing", tags=["processing"])


class ProcessFilesRequest(BaseModel):
    """Request to process Google Drive files."""

    folder_id: Optional[str] = None
    """Optional folder ID to process. If None, processes entire Drive."""

    file_ids: Optional[list[str]] = None
    """Optional list of specific file IDs to process. Takes precedence over folder_id."""


class ProcessFilesResponse(BaseModel):
    """Response when processing is initiated."""

    task_id: str
    """Celery task ID for tracking"""

    message: str
    """Human-readable message"""

    status: str = "started"
    """Initial status"""


class TaskStatusResponse(BaseModel):
    """Response for task status checks."""

    task_id: str
    """Celery task ID"""

    state: str
    """Task state: PENDING, PROCESSING, SUCCESS, FAILURE"""

    current: Optional[int] = None
    """Current file being processed"""

    total: Optional[int] = None
    """Total files to process"""

    current_file: Optional[str] = None
    """Name of current file"""

    status: Optional[str] = None
    """Status message"""

    result: Optional[dict] = None
    """Final result (when task completes)"""

    error: Optional[str] = None
    """Error message (if task failed)"""


@router.post("/start", response_model=ProcessFilesResponse)
async def start_processing(
    request: ProcessFilesRequest,
    user_id: str = Depends(get_current_user_id),
) -> ProcessFilesResponse:
    """
    Start processing Google Drive files.

    This initiates an asynchronous task that will:
    1. List all files in the user's Drive (or specified folder)
    2. Download and extract text from each processable file
    3. Save results to JSON

    The task runs in the background. Use the `/processing/status/{task_id}`
    endpoint to check progress.

    Args:
        request: Processing request with optional folder_id
        user_id: Authenticated user ID (from JWT)

    Returns:
        Task ID and status message
    """
    logger.info(f"Starting file processing for user: {user_id}")

    # Start the Celery task
    task = process_drive_files_task.apply_async(
        kwargs={
            "user_id": user_id,
            "folder_id": request.folder_id,
            "file_ids": request.file_ids,
        }
    )

    if request.file_ids:
        message = f"Started processing {len(request.file_ids)} selected files"
    elif request.folder_id:
        message = f"Started processing files from folder {request.folder_id}"
    else:
        message = "Started processing files from entire Drive"

    return ProcessFilesResponse(
        task_id=task.id,
        message=message,
        status="started",
    )


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> TaskStatusResponse:
    """
    Check the status of a processing task.

    Returns current progress, including:
    - Which file is being processed
    - How many files have been completed
    - Final results (when task completes)
    - Error details (if task failed)

    Args:
        task_id: Celery task ID returned from /start
        user_id: Authenticated user ID (from JWT)

    Returns:
        Current task status and progress
    """
    # Get task result from Celery
    task_result = AsyncResult(task_id)

    # Build response based on task state
    response = TaskStatusResponse(
        task_id=task_id,
        state=task_result.state,
    )

    if task_result.state == "PENDING":
        # Task hasn't started yet
        response.status = "Waiting to start..."

    elif task_result.state == "PROCESSING":
        # Task is running - get progress info
        info = task_result.info or {}
        response.current = info.get("current")
        response.total = info.get("total")
        response.current_file = info.get("current_file")
        response.status = info.get("status", "Processing...")

    elif task_result.state == "SUCCESS":
        # Task completed successfully
        response.result = task_result.result
        response.status = "Completed successfully"

    elif task_result.state == "FAILURE":
        # Task failed
        response.error = str(task_result.info)
        response.status = "Failed"

    else:
        # Unknown state
        response.status = f"Unknown state: {task_result.state}"

    return response


@router.delete("/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Cancel a running processing task.

    Args:
        task_id: Celery task ID to cancel
        user_id: Authenticated user ID (from JWT)

    Returns:
        Cancellation confirmation
    """
    task_result = AsyncResult(task_id)

    # Revoke the task
    task_result.revoke(terminate=True)

    logger.info(f"Task {task_id} cancelled by user {user_id}")

    return {
        "task_id": task_id,
        "message": "Task cancellation requested",
        "status": "cancelled",
    }


# Supported MIME types for local file uploads
SUPPORTED_UPLOAD_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
    "text/plain": "txt",
}

# Maximum file size (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class UploadFilesResponse(BaseModel):
    """Response when file upload processing is initiated."""

    task_id: str
    """Celery task ID for tracking"""

    message: str
    """Human-readable message"""

    files_received: int
    """Number of files received"""

    status: str = "started"
    """Initial status"""


@router.post("/upload", response_model=UploadFilesResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
) -> UploadFilesResponse:
    """
    Upload and process local files.

    This initiates an asynchronous task that will:
    1. Extract text from each uploaded file
    2. Generate embeddings and tags
    3. Save documents to the database

    Supported file types: PDF, DOCX, XLSX, TXT

    Args:
        files: List of files to upload
        user_id: Authenticated user ID (from JWT)

    Returns:
        Task ID and status message
    """
    logger.info(f"Received {len(files)} files for upload from user: {user_id}")

    # Validate and prepare files
    files_data = []
    for file in files:
        # Check file size
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{file.filename}' exceeds maximum size of 10 MB",
            )

        # Check MIME type
        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in SUPPORTED_UPLOAD_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{mime_type}' is not supported. Supported types: PDF, DOCX, XLSX, TXT",
            )

        # Generate unique ID for local file
        file_id = f"local_{uuid.uuid4().hex[:16]}"

        # Encode content as base64 for JSON serialization
        content_b64 = base64.b64encode(content).decode("utf-8")

        files_data.append({
            "id": file_id,
            "filename": file.filename,
            "mime_type": mime_type,
            "content_b64": content_b64,
            "size": len(content),
        })

        logger.info(f"  Prepared file: {file.filename} ({mime_type}, {len(content)} bytes)")

    # Start the Celery task
    task = process_uploaded_files_task.apply_async(
        kwargs={
            "user_id": user_id,
            "files_data": files_data,
        }
    )

    return UploadFilesResponse(
        task_id=task.id,
        message=f"Started processing {len(files_data)} uploaded files",
        files_received=len(files_data),
        status="started",
    )
