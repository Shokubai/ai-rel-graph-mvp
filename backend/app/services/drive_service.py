"""
Google Drive Service

This module handles interactions with the Google Drive API.
Downloads files, exports Google Docs, and retrieves metadata.

Usage:
    drive_service = DriveService(access_token)
    files = drive_service.list_files_in_folder(folder_id)
    content = drive_service.download_file(file_id, mime_type)
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class DriveService:
    """
    Service for interacting with Google Drive API.

    This class provides methods to list files, download content,
    and retrieve metadata from Google Drive.
    """

    DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

    def __init__(self, access_token: str):
        """
        Initialize the Drive service with an access token.

        Args:
            access_token: Google OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def list_files_in_folder(
        self,
        folder_id: Optional[str] = None,
        page_size: int = 100,
        include_trashed: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List all files in a Google Drive folder (or entire Drive if folder_id is None).

        Args:
            folder_id: Google Drive folder ID (None = all accessible files)
            page_size: Number of files to fetch per page (max 1000)
            include_trashed: Whether to include trashed files

        Returns:
            List of file metadata dictionaries
        """
        all_files = []
        page_token = None

        # Build query
        if folder_id:
            query = f"'{folder_id}' in parents"
        else:
            query = ""

        if not include_trashed:
            trash_filter = "trashed=false"
            query = f"{query} and {trash_filter}" if query else trash_filter

        logger.info(f"Listing files with query: {query}")

        while True:
            params = {
                "q": query,
                "fields": (
                    "nextPageToken, "
                    "files(id, name, mimeType, modifiedTime, size, "
                    "webViewLink, thumbnailLink, parents, owners)"
                ),
                "pageSize": str(page_size),
            }

            if page_token:
                params["pageToken"] = page_token

            try:
                with httpx.Client() as client:
                    response = client.get(
                        f"{self.DRIVE_API_BASE}/files",
                        headers=self.headers,
                        params=params,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                files = data.get("files", [])
                all_files.extend(files)

                logger.info(f"Retrieved {len(files)} files (total so far: {len(all_files)})")

                # Check if there are more pages
                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            except httpx.HTTPError as e:
                logger.error(f"Error listing files: {str(e)}")
                raise

        logger.info(f"Total files retrieved: {len(all_files)}")
        return all_files

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """
        Get detailed metadata for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dictionary
        """
        params = {
            "fields": (
                "id, name, mimeType, description, starred, trashed, "
                "createdTime, modifiedTime, size, owners, webViewLink"
            )
        }

        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.DRIVE_API_BASE}/files/{file_id}",
                    headers=self.headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting metadata for file {file_id}: {str(e)}")
            raise

    def download_file(self, file_id: str, mime_type: str) -> bytes:
        """
        Download file content from Google Drive.

        For Google Docs, Sheets, and Slides, this exports them to a compatible format.
        For other files, downloads the raw content.

        Args:
            file_id: Google Drive file ID
            mime_type: MIME type of the file

        Returns:
            File content as bytes
        """
        logger.info(f"Downloading file {file_id} (type: {mime_type})")

        try:
            # Google Docs need to be exported, not downloaded
            if mime_type == "application/vnd.google-apps.document":
                return self._export_google_doc(file_id, export_mime_type="text/plain")

            elif mime_type == "application/vnd.google-apps.spreadsheet":
                return self._export_google_doc(
                    file_id,
                    export_mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            elif mime_type == "application/vnd.google-apps.presentation":
                return self._export_google_doc(file_id, export_mime_type="text/plain")

            # Regular files - direct download
            else:
                return self._download_raw_file(file_id)

        except httpx.HTTPError as e:
            logger.error(f"Error downloading file {file_id}: {str(e)}")
            raise

    def _export_google_doc(self, file_id: str, export_mime_type: str) -> bytes:
        """
        Export a Google Workspace file (Doc, Sheet, Slide) to a specific format.

        Args:
            file_id: Google Drive file ID
            export_mime_type: Desired export format MIME type

        Returns:
            Exported file content as bytes
        """
        params = {"mimeType": export_mime_type}

        with httpx.Client() as client:
            response = client.get(
                f"{self.DRIVE_API_BASE}/files/{file_id}/export",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params=params,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.content

    def _download_raw_file(self, file_id: str) -> bytes:
        """
        Download a regular file from Google Drive.

        Args:
            file_id: Google Drive file ID

        Returns:
            File content as bytes
        """
        params = {"alt": "media"}

        with httpx.Client() as client:
            response = client.get(
                f"{self.DRIVE_API_BASE}/files/{file_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params=params,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.content

    def is_processable_file(self, mime_type: str) -> bool:
        """
        Check if a file type can be processed for text extraction.

        Args:
            mime_type: MIME type of the file

        Returns:
            True if the file can be processed, False otherwise
        """
        processable_types = [
            # Google Workspace files
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.spreadsheet",
            "application/vnd.google-apps.presentation",
            # Microsoft Office files
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/msword",
            "application/vnd.ms-excel",
            # PDFs and text
            "application/pdf",
            "text/plain",
        ]

        return mime_type in processable_types
