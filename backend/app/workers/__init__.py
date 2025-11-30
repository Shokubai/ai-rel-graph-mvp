"""Celery workers package."""

from app.workers.tasks import process_drive_files_task

__all__ = ["process_drive_files_task"]
