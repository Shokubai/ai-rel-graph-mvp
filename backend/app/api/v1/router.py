"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import drive, files, semantic, users

api_router: APIRouter = APIRouter()
api_router.include_router(drive.router, tags=["drive"])
api_router.include_router(files.router, tags=["files"])
api_router.include_router(semantic.router, prefix="/semantic", tags=["semantic"])
api_router.include_router(users.router, tags=["users"])
