"""Entity model for named entity recognition."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class Entity(Base):
    """Named entity extracted from documents."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50))  # person, organization, technology, etc.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="entities")
    documents = relationship("DocumentEntity", back_populates="entity", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_entities_user_name", "user_id", "name"),)
