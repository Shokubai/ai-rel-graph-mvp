"""User repository for authentication and user management."""
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize user repository.

        Args:
            session: Async database session
        """
        super().__init__(User, session)

    async def get_by_google_user_id(self, google_user_id: str) -> Optional[User]:
        """Get user by Google OAuth ID.

        Args:
            google_user_id: Google OAuth user ID

        Returns:
            User instance or None if not found
        """
        result = await self.session.execute(
            select(User).filter(User.google_user_id == google_user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address.

        Args:
            email: User email address

        Returns:
            User instance or None if not found
        """
        result = await self.session.execute(
            select(User).filter(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        google_user_id: str,
        email: str,
        name: str,
        google_access_token: str,
        google_refresh_token: str,
        google_token_expires_at: datetime,
    ) -> User:
        """Create new user or update existing user tokens.

        Args:
            google_user_id: Google OAuth user ID
            email: User email
            name: User display name
            google_access_token: Google OAuth access token
            google_refresh_token: Google OAuth refresh token
            google_token_expires_at: Token expiration datetime

        Returns:
            User instance (created or updated)
        """
        user = await self.get_by_google_user_id(google_user_id)

        if user:
            # Update existing user
            user.email = email
            user.name = name
            user.google_access_token = google_access_token
            user.google_refresh_token = google_refresh_token
            user.google_token_expires_at = google_token_expires_at
            user.last_login_at = datetime.now(timezone.utc)
            user.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
            await self.session.refresh(user)
        else:
            # Create new user
            user = User(
                google_user_id=google_user_id,
                email=email,
                name=name,
                google_access_token=google_access_token,
                google_refresh_token=google_refresh_token,
                google_token_expires_at=google_token_expires_at,
                last_login_at=datetime.now(timezone.utc),
            )
            await self.create(user)

        return user
