"""Tag repository with hierarchy and orphan tracking."""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tag import Tag
from app.repositories.base_repository import BaseRepository


class TagRepository(BaseRepository[Tag]):
    """Repository for Tag model with hierarchy management."""

    def __init__(self, session: AsyncSession):
        """Initialize tag repository.

        Args:
            session: Async database session
        """
        super().__init__(Tag, session)

    async def get_by_name(self, name: str, user_id: UUID) -> Optional[Tag]:
        """Get tag by name for a user.

        Args:
            name: Tag name
            user_id: User UUID

        Returns:
            Tag instance or None if not found
        """
        result = await self.session.execute(
            select(Tag).filter(and_(Tag.name == name, Tag.user_id == user_id))
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, tag_type: Optional[str] = None
    ) -> List[Tag]:
        """List tags for user, optionally filtered by type.

        Args:
            user_id: User UUID
            tag_type: Optional filter by 'high_level' or 'low_level'

        Returns:
            List of Tag instances
        """
        query = select(Tag).filter(Tag.user_id == user_id)

        if tag_type:
            query = query.filter(Tag.tag_type == tag_type)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def increment_orphan_count(self, tag_id: int) -> Optional[Tag]:
        """Increment orphaned document count for auto-split tracking.

        Args:
            tag_id: Tag ID

        Returns:
            Updated Tag instance or None if not found
        """
        tag = await self.get_by_id(tag_id)
        if tag:
            tag.orphaned_doc_count += 1
            await self.session.flush()
            await self.session.refresh(tag)
        return tag

    async def decrement_orphan_count(self, tag_id: int) -> Optional[Tag]:
        """Decrement orphaned document count.

        Args:
            tag_id: Tag ID

        Returns:
            Updated Tag instance or None if not found
        """
        tag = await self.get_by_id(tag_id)
        if tag:
            tag.orphaned_doc_count = max(0, tag.orphaned_doc_count - 1)
            await self.session.flush()
            await self.session.refresh(tag)
        return tag

    async def reset_orphan_count(self, tag_id: int, count: int = 0) -> Optional[Tag]:
        """Set orphan count to a specific value.

        Args:
            tag_id: Tag ID
            count: New orphan count

        Returns:
            Updated Tag instance or None if not found
        """
        tag = await self.get_by_id(tag_id)
        if tag:
            tag.orphaned_doc_count = count
            await self.session.flush()
            await self.session.refresh(tag)
        return tag

    async def get_children(self, parent_tag_id: int) -> List[Tag]:
        """Get all child tags of a parent.

        Args:
            parent_tag_id: Parent tag ID

        Returns:
            List of child Tag instances
        """
        result = await self.session.execute(
            select(Tag).filter(Tag.parent_id == parent_tag_id)
        )
        return list(result.scalars().all())

    async def get_hierarchy(self, user_id: UUID) -> Dict[str, Any]:
        """Get full tag hierarchy for user.

        Returns structured hierarchy showing high-level tags and their children.

        Args:
            user_id: User UUID

        Returns:
            Dictionary with structure:
            {
                "high_level": {
                    "Engineering": {
                        "id": 1,
                        "orphaned_doc_count": 3,
                        "children": [
                            {"id": 4, "name": "Backend Development"},
                            {"id": 5, "name": "Frontend Development"}
                        ]
                    }
                }
            }
        """
        # Get all tags
        tags = await self.list_by_user(user_id)

        hierarchy = {"high_level": {}}

        # Build high-level mapping
        for tag in tags:
            if tag.tag_type == "high_level":
                children = await self.get_children(tag.id)
                hierarchy["high_level"][tag.name] = {
                    "id": tag.id,
                    "orphaned_doc_count": tag.orphaned_doc_count,
                    "children": [
                        {"id": child.id, "name": child.name} for child in children
                    ],
                }

        return hierarchy

    async def get_or_create(
        self,
        name: str,
        tag_type: str,
        user_id: UUID,
        parent_id: Optional[int] = None,
    ) -> Tag:
        """Get existing tag or create new one.

        Args:
            name: Tag name
            tag_type: 'high_level' or 'low_level'
            user_id: User UUID
            parent_id: Optional parent tag ID for hierarchy

        Returns:
            Tag instance (existing or newly created)
        """
        tag = await self.get_by_name(name, user_id)

        if not tag:
            tag = Tag(
                name=name, tag_type=tag_type, user_id=user_id, parent_id=parent_id
            )
            await self.create(tag)

        return tag

    async def get_tags_above_threshold(
        self, user_id: UUID, threshold: int = 8
    ) -> List[Tag]:
        """Get tags with orphan count >= threshold (candidates for auto-split).

        Args:
            user_id: User UUID
            threshold: Minimum orphan count (default 8)

        Returns:
            List of Tag instances ready for splitting
        """
        result = await self.session.execute(
            select(Tag).filter(
                and_(
                    Tag.user_id == user_id,
                    Tag.tag_type == "high_level",
                    Tag.orphaned_doc_count >= threshold,
                )
            )
        )
        return list(result.scalars().all())
