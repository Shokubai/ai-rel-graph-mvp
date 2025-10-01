"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import files

api_router: APIRouter = APIRouter()
api_router.include_router(files.router, tags=["files"])
