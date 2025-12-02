"""Tag model with hierarchical structure and orphan tracking."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

# Cross-cutting tags association table
tag_cross_cutting = Table(
    "tag_cross_cutting",
    Base.metadata,
    Column("parent_tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
    Column("child_tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)


class Tag(Base):
    """Hierarchical tag with orphan tracking for auto re-split."""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    tag_type = Column(String(20), nullable=False)  # 'high_level' or 'low_level'
    parent_id = Column(Integer, ForeignKey("tags.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Orphan tracking: documents assigned to high-level but no low-level child
    orphaned_doc_count = Column(Integer, default=0, nullable=False)

    # Relationships
    user = relationship("User", back_populates="tags")
    parent = relationship("Tag", remote_side=[id], backref="children")
    cross_cutting_children = relationship(
        "Tag",
        secondary=tag_cross_cutting,
        primaryjoin=id == tag_cross_cutting.c.parent_tag_id,
        secondaryjoin=id == tag_cross_cutting.c.child_tag_id,
        backref="cross_cutting_parents",
    )
    documents = relationship("DocumentTag", back_populates="tag", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_tags_user_name", "user_id", "name"),)
