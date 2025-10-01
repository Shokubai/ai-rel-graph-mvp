"""Relationship model."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class FileRelationship(Base):
    """File relationship model."""

    __tablename__ = "file_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    target_file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    similarity_score = Column(Float)
    relationship_type = Column(String(50), default="semantic_similarity")
    created_at = Column(DateTime, default=datetime.utcnow)
