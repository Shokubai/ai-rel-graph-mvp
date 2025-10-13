"""FileTag association model."""
from sqlalchemy import Column, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class FileTag(Base):
    """Many-to-many association between files and tags."""

    __tablename__ = "file_tags"

    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relevance_score = Column(Float, default=1.0)  # how relevant this tag is to the document

    # Relationships
    file = relationship("File", back_populates="tag_associations")
    tag = relationship("Tag", back_populates="file_associations")
