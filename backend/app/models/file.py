"""File model."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

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

    # Relationships
    tag_associations = relationship(
        "FileTag",
        back_populates="file",
        cascade="all, delete-orphan",
    )
