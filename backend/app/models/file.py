"""File model."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class File(Base):
    """File model."""

    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_drive_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    mime_type = Column(String(100))
    size_bytes = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processing_status = Column(String(50), default="pending", index=True)
    text_content = Column(Text)
    embedding = Column(Vector(384))

    __table_args__ = (
        Index("ix_files_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
