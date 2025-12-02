"""Document similarity edges."""
from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Index, Integer, String

from app.db.base import Base


class DocumentSimilarity(Base):
    """Similarity edges between documents."""

    __tablename__ = "document_similarities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, nullable=False)

    __table_args__ = (
        # Prevent duplicate edges (store only source < target)
        CheckConstraint("source_document_id < target_document_id", name="check_source_lt_target"),
        Index("idx_similarities_source", "source_document_id"),
        Index("idx_similarities_target", "target_document_id"),
    )
