"""Relationship model."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class FileRelationship(Base):
    """File relationship model."""

    __tablename__ = "file_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    target_file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, index=True)
    relationship_type = Column(String(50), default="semantic_similarity")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_file_relationships_source_target", "source_file_id", "target_file_id"),
        UniqueConstraint("source_file_id", "target_file_id", name="uq_file_relationship_pair"),
        CheckConstraint("source_file_id != target_file_id", name="ck_no_self_relationship"),
        CheckConstraint("similarity_score >= 0.0 AND similarity_score <= 1.0", name="ck_similarity_score_range"),
    )
