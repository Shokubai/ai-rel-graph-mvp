"""Similarity edge repository for document relationships."""
from typing import List, Tuple
from uuid import UUID
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document_similarity import DocumentSimilarity
from app.db.models.document import Document
from app.repositories.base_repository import BaseRepository


class SimilarityRepository(BaseRepository[DocumentSimilarity]):
    """Repository for DocumentSimilarity model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize similarity repository.

        Args:
            session: Async database session
        """
        super().__init__(DocumentSimilarity, session)

    async def get_similar_documents(
        self, doc_id: str, user_id: UUID, min_score: float = 0.7
    ) -> List[Tuple[Document, float]]:
        """Get similar documents for a given document.

        Args:
            doc_id: Source document ID
            user_id: User UUID for multi-tenant isolation
            min_score: Minimum similarity score (0.0-1.0)

        Returns:
            List of (Document, similarity_score) tuples
        """
        # Query where doc is either source or target
        query = (
            select(DocumentSimilarity, Document)
            .join(
                Document,
                or_(
                    and_(
                        DocumentSimilarity.source_document_id == doc_id,
                        DocumentSimilarity.target_document_id == Document.id,
                    ),
                    and_(
                        DocumentSimilarity.target_document_id == doc_id,
                        DocumentSimilarity.source_document_id == Document.id,
                    ),
                ),
            )
            .filter(
                and_(
                    Document.user_id == user_id,
                    DocumentSimilarity.similarity_score >= min_score,
                )
            )
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [(row.Document, row.DocumentSimilarity.similarity_score) for row in rows]

    async def create_similarity(
        self, source_id: str, target_id: str, score: float
    ) -> DocumentSimilarity:
        """Create similarity edge (ensures source < target for canonical ordering).

        Args:
            source_id: Source document ID
            target_id: Target document ID
            score: Similarity score (0.0-1.0)

        Returns:
            Created DocumentSimilarity instance
        """
        # Canonical ordering to prevent duplicates
        if source_id > target_id:
            source_id, target_id = target_id, source_id

        similarity = DocumentSimilarity(
            source_document_id=source_id,
            target_document_id=target_id,
            similarity_score=score,
        )

        await self.create(similarity)
        return similarity

    async def bulk_create_similarities(
        self, similarities: List[Tuple[str, str, float]]
    ) -> None:
        """Bulk insert similarity edges.

        Args:
            similarities: List of (source_id, target_id, score) tuples
        """
        objects = []

        for source_id, target_id, score in similarities:
            # Canonical ordering
            if source_id > target_id:
                source_id, target_id = target_id, source_id

            objects.append(
                DocumentSimilarity(
                    source_document_id=source_id,
                    target_document_id=target_id,
                    similarity_score=score,
                )
            )

        self.session.add_all(objects)
        await self.session.flush()

    async def delete_for_document(self, doc_id: str) -> int:
        """Delete all similarities involving a document.

        Args:
            doc_id: Document ID

        Returns:
            Number of deleted rows
        """
        result = await self.session.execute(
            delete(DocumentSimilarity).filter(
                or_(
                    DocumentSimilarity.source_document_id == doc_id,
                    DocumentSimilarity.target_document_id == doc_id,
                )
            )
        )
        await self.session.flush()
        return result.rowcount

    async def get_all_for_user(
        self, user_id: UUID, min_score: float = 0.7
    ) -> List[DocumentSimilarity]:
        """Get all similarity edges for a user's documents.

        Args:
            user_id: User UUID
            min_score: Minimum similarity score

        Returns:
            List of DocumentSimilarity instances
        """
        # Join with documents to filter by user_id
        query = (
            select(DocumentSimilarity)
            .join(
                Document,
                or_(
                    DocumentSimilarity.source_document_id == Document.id,
                    DocumentSimilarity.target_document_id == Document.id,
                ),
            )
            .filter(
                and_(
                    Document.user_id == user_id,
                    DocumentSimilarity.similarity_score >= min_score,
                )
            )
            .distinct()
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())
