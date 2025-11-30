"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import drive, graph, processing, users

api_router: APIRouter = APIRouter()
api_router.include_router(drive.router, tags=["drive"])
api_router.include_router(processing.router, tags=["processing"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(users.router, tags=["users"])
