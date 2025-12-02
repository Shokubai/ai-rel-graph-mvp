"""Authentication dependencies and utilities."""
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.db.models.user import User

logger = logging.getLogger(__name__)
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
        logger.info(f"[AUTH] Attempting to decode JWT token (first 20 chars): {token[:20]}...")
        logger.info(f"[AUTH] Using NEXTAUTH_SECRET: {settings.NEXTAUTH_SECRET[:10]}..." if settings.NEXTAUTH_SECRET else "[AUTH] NEXTAUTH_SECRET is None!")

        payload = jwt.decode(
            token,
            settings.NEXTAUTH_SECRET,
            algorithms=["HS256"],
        )
        logger.info(f"[AUTH] Successfully decoded JWT. Payload: {payload}")

        user_id: str = payload.get("sub")
        if user_id is None:
            logger.error("[AUTH] JWT payload missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

        logger.info(f"[AUTH] Extracted user_id: {user_id}")
        return user_id
    except JWTError as e:
        logger.error(f"[AUTH] JWT validation failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
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
    logger.info(f"[AUTH] get_google_access_token called for user_id={user_id}")
    logger.info(f"[AUTH] User model columns: {[c.name for c in User.__table__.columns]}")
    user = session.query(User).filter(User.google_user_id == user_id).first()
    logger.info(f"[AUTH] User query result: {'Found' if user else 'Not found'}")

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
    logger.info(f"[AUTH] get_current_user called for user_id={user_id}")
    logger.info(f"[AUTH] User model columns: {[c.name for c in User.__table__.columns]}")
    user = session.query(User).filter(User.google_user_id == user_id).first()
    logger.info(f"[AUTH] User query result: {'Found' if user else 'Not found'}")

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in again.",
        )

    return user
