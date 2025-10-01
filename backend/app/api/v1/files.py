"""File endpoints."""
from typing import List

from fastapi import APIRouter

router: APIRouter = APIRouter()


@router.get("/files")
async def get_files() -> List[dict]:
    """Get all files."""
    return []
