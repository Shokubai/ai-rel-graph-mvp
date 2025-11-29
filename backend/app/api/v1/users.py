"""User management endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


class UserTokenUpdate(BaseModel):
    """Request model for updating user tokens."""

    google_id: str
    email: EmailStr
    name: Optional[str] = None
    google_access_token: str
    google_refresh_token: Optional[str] = None
    google_token_expires_at: Optional[datetime] = None


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    name: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


def verify_internal_request(x_internal_key: Optional[str] = Header(None)) -> bool:
    """Verify request is from internal frontend service."""
    from app.core.config import settings
    if not x_internal_key or x_internal_key != settings.NEXTAUTH_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden"
        )
    return True


@router.post("/sync", response_model=UserResponse)
def sync_user_tokens(
    user_data: UserTokenUpdate,
    session: Session = Depends(get_db),
    _: bool = Depends(verify_internal_request),
):
    """
    Create or update user with Google OAuth tokens.

    This endpoint is called by NextAuth during the authentication flow
    to store Google access tokens server-side.
    """
    # Find existing user or create new one
    user = session.query(User).filter(User.google_id == user_data.google_id).first()

    if user:
        # Update existing user
        user.email = user_data.email
        user.name = user_data.name
        user.google_access_token = user_data.google_access_token
        user.google_refresh_token = user_data.google_refresh_token or user.google_refresh_token
        user.google_token_expires_at = user_data.google_token_expires_at
        user.last_login_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
    else:
        # Create new user
        user = User(
            google_id=user_data.google_id,
            email=user_data.email,
            name=user_data.name,
            google_access_token=user_data.google_access_token,
            google_refresh_token=user_data.google_refresh_token,
            google_token_expires_at=user_data.google_token_expires_at,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)

    session.commit()
    session.refresh(user)

    return user


