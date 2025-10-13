"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import files, semantic

api_router: APIRouter = APIRouter()
api_router.include_router(files.router, tags=["files"])
api_router.include_router(semantic.router, prefix="/semantic", tags=["semantic"])
