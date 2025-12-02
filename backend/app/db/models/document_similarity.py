"""Document similarity edges."""
from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, UniqueConstraint

from app.db.base import Base


class DocumentSimilarity(Base):
    """Similarity edges between documents."""

    __tablename__ = "document_similarities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, nullable=False)

    __table_args__ = (
        # Prevent duplicate edges with UNIQUE constraint (replaces CHECK constraint)
        # Removed CHECK constraint due to collation differences between Python and PostgreSQL
        UniqueConstraint("source_document_id", "target_document_id", name="uq_document_similarities_pair"),
        Index("idx_similarities_source", "source_document_id"),
        Index("idx_similarities_target", "target_document_id"),
    )
