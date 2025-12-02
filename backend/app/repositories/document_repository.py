"""Document repository with vector similarity search."""
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.document import Document
from app.db.models.document_tag import DocumentTag
from app.db.models.document_entity import DocumentEntity
from app.repositories.base_repository import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document model with vector similarity search."""

    def __init__(self, session: AsyncSession):
        """Initialize document repository.

        Args:
            session: Async database session
        """
        super().__init__(Document, session)

    async def get_by_id(
        self, doc_id: str, user_id: UUID, load_relations: bool = False
    ) -> Optional[Document]:
        """Get document by ID with user_id check for multi-tenancy.

        Args:
            doc_id: Document ID (Google Drive file ID)
            user_id: User UUID for multi-tenant isolation
            load_relations: If True, eagerly load tags and entities

        Returns:
            Document instance or None if not found
        """
        query = select(Document).filter(
            and_(Document.id == doc_id, Document.user_id == user_id)
        )

        if load_relations:
            # Chain selectinload to load nested relationships
            from app.db.models.tag import Tag
            from app.db.models.entity import Entity

            query = query.options(
                selectinload(Document.tags).selectinload(DocumentTag.tag),
                selectinload(Document.entities).selectinload(DocumentEntity.entity)
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, enabled_only: bool = True, load_relations: bool = False
    ) -> List[Document]:
        """List all documents for a user.

        Args:
            user_id: User UUID
            enabled_only: If True, only return enabled documents
            load_relations: If True, eagerly load tags and entities

        Returns:
            List of Document instances
        """
        query = select(Document).filter(Document.user_id == user_id)

        if enabled_only:
            query = query.filter(Document.is_enabled == True)

        if load_relations:
            # Chain selectinload to load nested relationships
            from app.db.models.tag import Tag
            from app.db.models.entity import Entity

            query = query.options(
                selectinload(Document.tags).selectinload(DocumentTag.tag),
                selectinload(Document.entities).selectinload(DocumentEntity.entity)
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_similar(
        self,
        embedding: List[float],
        user_id: UUID,
        limit: int = 10,
        enabled_only: bool = True,
        min_similarity: float = 0.0,
    ) -> List[Tuple[Document, float]]:
        """Search for similar documents using pgvector cosine similarity.

        Args:
            embedding: Query embedding vector (1536 dims)
            user_id: User UUID for multi-tenant isolation
            limit: Maximum number of results
            enabled_only: If True, only search enabled documents
            min_similarity: Minimum similarity score (0.0-1.0)

        Returns:
            List of (Document, similarity_score) tuples, sorted by similarity descending
        """
        # Convert distance to similarity: similarity = 1 - distance
        query = (
            select(
                Document,
                (1 - Document.embedding.cosine_distance(embedding)).label("similarity"),
            )
            .filter(Document.user_id == user_id)
        )

        if enabled_only:
            query = query.filter(Document.is_enabled == True)

        # Filter by minimum similarity
        if min_similarity > 0:
            query = query.filter(
                (1 - Document.embedding.cosine_distance(embedding)) >= min_similarity
            )

        query = query.order_by(func.desc("similarity")).limit(limit)

        result = await self.session.execute(query)
        rows = result.all()

        return [(row.Document, row.similarity) for row in rows]

    async def toggle_enabled(
        self, doc_id: str, user_id: UUID, enabled: bool
    ) -> Optional[Document]:
        """Enable or disable document visibility in graph.

        Args:
            doc_id: Document ID
            user_id: User UUID
            enabled: True to enable, False to disable

        Returns:
            Updated Document instance or None if not found
        """
        doc = await self.get_by_id(doc_id, user_id)
        if doc:
            doc.is_enabled = enabled
            await self.session.flush()
            await self.session.refresh(doc)
        return doc

    async def bulk_create(self, documents: List[Document]) -> List[Document]:
        """Bulk insert documents.

        Args:
            documents: List of Document instances

        Returns:
            List of created documents with IDs
        """
        self.session.add_all(documents)
        await self.session.flush()
        return documents

    async def get_by_tag(
        self, tag_id: int, user_id: UUID, enabled_only: bool = True
    ) -> List[Document]:
        """Get documents that have a specific tag.

        Args:
            tag_id: Tag ID
            user_id: User UUID
            enabled_only: If True, only return enabled documents

        Returns:
            List of Document instances
        """
        query = (
            select(Document)
            .join(DocumentTag, Document.id == DocumentTag.document_id)
            .filter(
                and_(
                    DocumentTag.tag_id == tag_id,
                    Document.user_id == user_id,
                )
            )
        )

        if enabled_only:
            query = query.filter(Document.is_enabled == True)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_orphaned_for_tag(
        self, tag_id: int, user_id: UUID
    ) -> List[Document]:
        """Get documents that have a high-level tag but no low-level child.
        Used for auto-split functionality.

        Args:
            tag_id: High-level tag ID
            user_id: User UUID

        Returns:
            List of orphaned Document instances
        """
        from app.db.models.tag import Tag

        # Get all child tag IDs
        child_tags_subq = (
            select(Tag.id).filter(Tag.parent_id == tag_id).scalar_subquery()
        )

        # Documents with high-level tag
        high_level_docs_subq = (
            select(DocumentTag.document_id)
            .filter(
                and_(
                    DocumentTag.tag_id == tag_id, DocumentTag.tag_level == "high"
                )
            )
            .scalar_subquery()
        )

        # Documents with any low-level child tag
        low_level_docs_subq = (
            select(DocumentTag.document_id)
            .filter(
                and_(
                    DocumentTag.tag_id.in_(select(child_tags_subq)),
                    DocumentTag.tag_level == "low",
                )
            )
            .scalar_subquery()
        )

        # Get orphans (in high-level but NOT in low-level)
        query = select(Document).filter(
            and_(
                Document.id.in_(select(high_level_docs_subq)),
                ~Document.id.in_(select(low_level_docs_subq)),
                Document.user_id == user_id,
            )
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_by_text(
        self, query: str, user_id: UUID, enabled_only: bool = True
    ) -> List[Document]:
        """Search documents by text (title, summary, text_content).

        Args:
            query: Search query string
            user_id: User UUID
            enabled_only: If True, only search enabled documents

        Returns:
            List of matching Document instances
        """
        query_lower = f"%{query.lower()}%"

        stmt = select(Document).filter(
            and_(
                Document.user_id == user_id,
                or_(
                    func.lower(Document.title).like(query_lower),
                    func.lower(Document.summary).like(query_lower),
                    func.lower(Document.text_content).like(query_lower),
                ),
            )
        )

        if enabled_only:
            stmt = stmt.filter(Document.is_enabled == True)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_id(self, doc_id: str, user_id: UUID) -> bool:
        """Delete document by ID.

        Args:
            doc_id: Document ID
            user_id: User UUID

        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(Document).filter(
                and_(Document.id == doc_id, Document.user_id == user_id)
            )
        )
        await self.session.flush()
        return result.rowcount > 0
