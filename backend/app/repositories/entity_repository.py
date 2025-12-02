"""Entity repository."""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entity import Entity
from app.repositories.base_repository import BaseRepository


class EntityRepository(BaseRepository[Entity]):
    """Repository for Entity model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize entity repository.

        Args:
            session: Async database session
        """
        super().__init__(Entity, session)

    async def get_by_name(self, name: str, user_id: UUID) -> Optional[Entity]:
        """Get entity by name for a user.

        Args:
            name: Entity name
            user_id: User UUID

        Returns:
            Entity instance or None if not found
        """
        result = await self.session.execute(
            select(Entity).filter(and_(Entity.name == name, Entity.user_id == user_id))
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, entity_type: Optional[str] = None
    ) -> List[Entity]:
        """List entities for user, optionally filtered by type.

        Args:
            user_id: User UUID
            entity_type: Optional filter by entity type (e.g., 'PERSON', 'ORG')

        Returns:
            List of Entity instances
        """
        query = select(Entity).filter(Entity.user_id == user_id)

        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_or_create(
        self, name: str, entity_type: str, user_id: UUID
    ) -> Entity:
        """Get existing entity or create new one.

        Args:
            name: Entity name
            entity_type: Entity type (e.g., 'PERSON', 'ORG', 'PRODUCT')
            user_id: User UUID

        Returns:
            Entity instance (existing or newly created)
        """
        entity = await self.get_by_name(name, user_id)

        if not entity:
            entity = Entity(name=name, entity_type=entity_type, user_id=user_id)
            await self.create(entity)

        return entity

    async def bulk_get_or_create(
        self, entities: List[dict], user_id: UUID
    ) -> List[Entity]:
        """Bulk get or create entities.

        Args:
            entities: List of dicts with 'name' and 'entity_type'
            user_id: User UUID

        Returns:
            List of Entity instances
        """
        result_entities = []

        for entity_data in entities:
            entity = await self.get_or_create(
                name=entity_data["name"],
                entity_type=entity_data["entity_type"],
                user_id=user_id,
            )
            result_entities.append(entity)

        return result_entities
