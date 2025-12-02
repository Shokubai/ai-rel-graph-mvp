"""Processing job tracking for Celery tasks."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ProcessingJob(Base):
    """Track Celery processing jobs."""

    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    celery_task_id = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), nullable=False)  # PENDING, PROCESSING, SUCCESS, FAILURE
    document_id = Column(String(255))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
