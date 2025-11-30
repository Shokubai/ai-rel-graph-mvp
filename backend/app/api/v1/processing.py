"""
File Processing API Endpoints

This module provides endpoints to trigger and monitor file processing tasks.
"""

import logging
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.workers.tasks import process_drive_files_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/processing", tags=["processing"])


class ProcessFilesRequest(BaseModel):
    """Request to process Google Drive files."""

    folder_id: Optional[str] = None
    """Optional folder ID to process. If None, processes entire Drive."""


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
        }
    )

    folder_msg = f"folder {request.folder_id}" if request.folder_id else "entire Drive"

    return ProcessFilesResponse(
        task_id=task.id,
        message=f"Started processing files from {folder_msg}",
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
