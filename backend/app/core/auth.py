"""Authentication dependencies and utilities."""
from typing import Optional
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Extract user ID from JWT token.

    This validates the JWT signature and extracts the user ID (sub claim).
    Does NOT include the Google access token in the JWT.
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.NEXTAUTH_SECRET,
            algorithms=["HS256"],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def get_google_access_token(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
) -> str:
    """
    Retrieve Google access token for the authenticated user.

    This looks up the user in the database and returns their Google access token.
    Raises 401 if user not found, token not available, or token expired.
    """
    user = session.query(User).filter(User.google_id == user_id).first()

    if not user or not user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in again.",
        )

    if user.google_token_expires_at and user.google_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication expired. Please sign in again.",
        )

    return user.google_access_token


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
) -> User:
    """
    Get the full User object for the authenticated user.
    """
    user = session.query(User).filter(User.google_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in again.",
        )

    return user
