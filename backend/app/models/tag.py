"""Tag model for document categorization."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tag(Base):
    """Tag model for categorizing documents."""

    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), index=True)  # broad category classification
    usage_count = Column(Integer, default=0)  # track how many files use this tag
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    file_associations = relationship(
        "FileTag",
        back_populates="tag",
        cascade="all, delete-orphan",
    )
