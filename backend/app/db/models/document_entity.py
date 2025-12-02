"""Document-Entity association model."""
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentEntity(Base):
    """Association between documents and entities."""

    __tablename__ = "document_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    confidence = Column(Float)  # NER confidence score

    # Relationships
    document = relationship("Document", back_populates="entities")
    entity = relationship("Entity", back_populates="documents")
