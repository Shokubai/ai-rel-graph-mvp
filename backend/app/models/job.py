"""Processing job model."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ProcessingJob(Base):
    """Processing job model."""

    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(String(255))
    status = Column(String(50), default="queued", index=True)
    progress_percentage = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
