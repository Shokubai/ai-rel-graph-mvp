"""Document model with pgvector embeddings."""
import uuid as uuid_pkg
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class Document(Base):
    """Document model with embedding vector."""

    __tablename__ = "documents"

    id = Column(String(255), primary_key=True)  # Google Drive file ID or generated UUID for local uploads
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Document source tracking
    source = Column(String(50), default="google_drive", nullable=False)  # 'google_drive' or 'local_upload'

    # Document metadata
    title = Column(String(500), nullable=False)
    url = Column(String(1000))  # None for local uploads
    mime_type = Column(String(100))
    author = Column(String(255))
    modified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Content
    text_content = Column(Text)
    summary = Column(Text)
    word_count = Column(Integer)

    # Embedding vector (1536 dimensions for OpenAI text-embedding-3-small)
    embedding = Column(Vector(1536))

    # Enable/disable for graph visibility
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="documents")
    tags = relationship("DocumentTag", back_populates="document", cascade="all, delete-orphan")
    entities = relationship("DocumentEntity", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_documents_user_enabled", "user_id", "is_enabled"),
        Index(
            "idx_documents_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
