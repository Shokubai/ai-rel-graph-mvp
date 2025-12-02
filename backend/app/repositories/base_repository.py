"""Base repository with common CRUD operations."""
from typing import Generic, Type, TypeVar, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic base repository for common database operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        """Get model by primary key ID.

        Args:
            id: Primary key value

        Returns:
            Model instance or None if not found
        """
        result = await self.session.execute(
            select(self.model).filter(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> List[ModelType]:
        """Get all models.

        Returns:
            List of all model instances
        """
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, obj: ModelType) -> ModelType:
        """Create new model instance.

        Args:
            obj: Model instance to create

        Returns:
            Created model instance with ID populated
        """
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        """Delete model instance.

        Args:
            obj: Model instance to delete
        """
        await self.session.delete(obj)
        await self.session.flush()
