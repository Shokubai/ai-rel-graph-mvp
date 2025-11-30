"""Google Drive API proxy endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
from app.core.auth import get_google_access_token

router = APIRouter(prefix="/drive", tags=["drive"])

GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"


class DriveFile(BaseModel):
    """Drive file metadata."""
    id: str
    name: str
    mimeType: str
    modifiedTime: Optional[str] = None
    size: Optional[str] = None
    webViewLink: Optional[str] = None
    thumbnailLink: Optional[str] = None
    parents: Optional[list[str]] = None


class DriveFileListResponse(BaseModel):
    """Drive file list response."""
    files: list[DriveFile]
    nextPageToken: Optional[str] = None


@router.get("/files", response_model=DriveFileListResponse)
async def list_files(
    folder_id: Optional[str] = Query(None, alias="folderId"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    page_size: int = Query(100, alias="pageSize", le=1000),
    google_token: str = Depends(get_google_access_token),
):
    """
    List files from Google Drive.

    Proxies request to Google Drive API using server-side stored access token.
    """
    query = f"'{folder_id}' in parents and trashed=false" if folder_id else "trashed=false"

    params = {
        "q": query,
        "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink,thumbnailLink,parents),nextPageToken",
        "pageSize": str(page_size),
    }

    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GOOGLE_DRIVE_API_BASE}/files",
                headers={
                    "Authorization": f"Bearer {google_token}",
                    "Content-Type": "application/json",
                },
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Failed to fetch files from Google Drive",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Google Drive API",
            )


@router.get("/files/{file_id}")
async def get_file_metadata(
    file_id: str,
    google_token: str = Depends(get_google_access_token),
):
    """
    Get metadata for a specific file.

    Proxies request to Google Drive API using server-side stored access token.
    """
    params = {
        "fields": "id,name,mimeType,description,starred,trashed,createdTime,modifiedTime,size,owners",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GOOGLE_DRIVE_API_BASE}/files/{file_id}",
                headers={
                    "Authorization": f"Bearer {google_token}",
                    "Content-Type": "application/json",
                },
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found",
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Failed to fetch file metadata",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Google Drive API",
            )


@router.get("/files/{file_id}/export")
async def export_file(
    file_id: str,
    mime_type: Optional[str] = Query(None, alias="mimeType"),
    google_token: str = Depends(get_google_access_token),
):
    """
    Export/download a Google Drive file.

    Proxies request to Google Drive API using server-side stored access token.
    Returns file as streaming response.
    """
    endpoint = f"{GOOGLE_DRIVE_API_BASE}/files/{file_id}"

    if mime_type:
        endpoint = f"{endpoint}/export"
        params = {"mimeType": mime_type}
    else:
        params = {"alt": "media"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                endpoint,
                headers={
                    "Authorization": f"Bearer {google_token}",
                },
                params=params,
                timeout=60.0,
            )
            response.raise_for_status()

            return StreamingResponse(
                iter([response.content]),
                media_type=response.headers.get("content-type", "application/octet-stream"),
                headers={
                    "Content-Disposition": response.headers.get("content-disposition", "attachment"),
                },
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found",
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Failed to export file",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Google Drive API",
            )


@router.get("/files/search")
async def search_files(
    query: str = Query(..., min_length=1),
    page_size: int = Query(50, alias="pageSize", le=1000),
    google_token: str = Depends(get_google_access_token),
):
    """
    Search Google Drive files.

    Proxies request to Google Drive API using server-side stored access token.
    """
    search_query = f"name contains '{query}' and trashed=false"

    params = {
        "q": search_query,
        "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
        "pageSize": str(page_size),
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GOOGLE_DRIVE_API_BASE}/files",
                headers={
                    "Authorization": f"Bearer {google_token}",
                    "Content-Type": "application/json",
                },
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Failed to search files",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Google Drive API",
            )
