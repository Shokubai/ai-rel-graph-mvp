"""
Celery Tasks for Asynchronous Processing

This module contains background tasks for processing Google Drive files.
Tasks are executed by Celery workers and tracked in the database.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery import Task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.user import User
from app.services.drive_service import DriveService
from app.services.graph_builder import GraphBuilder
from app.services.text_extraction import TextExtractor

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    Base task that provides database session management.

    Each task gets a fresh database session that's automatically
    closed when the task completes (success or failure).
    """

    _session: Optional[Session] = None

    @property
    def session(self) -> Session:
        """Get or create a database session for this task."""
        if self._session is None:
            self._session = SessionLocal()
        return self._session

    def after_return(
        self, status: str, retval: Any, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        """Clean up database session after task completes."""
        if self._session is not None:
            self._session.close()
            self._session = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="process_drive_files",
    max_retries=3,
    default_retry_delay=60,
)
def process_drive_files_task(
    self: DatabaseTask,
    user_id: str,
    folder_id: Optional[str] = None,
    file_ids: Optional[list[str]] = None,
    output_dir: str = "processed_files",
) -> Dict[str, Any]:
    """
    Process Google Drive files for a specific user.

    This task:
    1. Fetches the user's Google access token from database
    2. Lists all processable files in Drive (or specific folder/file IDs)
    3. Downloads and extracts text from each file
    4. Saves results to JSON

    Args:
        user_id: Google ID of the user
        folder_id: Optional Google Drive folder ID (None = entire Drive)
        file_ids: Optional list of specific file IDs to process (takes precedence over folder_id)
        output_dir: Directory to save output files

    Returns:
        Dictionary with processing results and statistics
    """
    logger.info(f"Starting file processing for user {user_id}")

    try:
        # Step 1: Get user's access token from database
        user = self.session.query(User).filter(User.google_id == user_id).first()

        if not user:
            raise ValueError(f"User not found: {user_id}")

        if not user.google_access_token:
            raise ValueError(f"No access token for user: {user_id}")

        access_token = user.google_access_token
        logger.info(f"Retrieved access token for user: {user.email}")

        # Step 2: Initialize services
        drive_service = DriveService(access_token)
        text_extractor = TextExtractor()

        # Step 3: Get files (either by IDs or by listing folder)
        if file_ids:
            logger.info(f"Fetching {len(file_ids)} specific files from Google Drive...")
            all_files = []
            for file_id in file_ids:
                try:
                    file_metadata = drive_service.get_file_metadata(file_id)
                    all_files.append(file_metadata)
                except Exception as e:
                    logger.warning(f"Failed to get metadata for file {file_id}: {e}")
        else:
            logger.info("Fetching file list from Google Drive...")
            all_files = drive_service.list_files_in_folder(folder_id)

        # Step 4: Filter processable files
        processable_files = [
            f for f in all_files if drive_service.is_processable_file(f.get("mimeType", ""))
        ]

        total_files = len(processable_files)
        logger.info(f"Found {total_files} processable files")

        if total_files == 0:
            return {
                "status": "completed",
                "message": "No processable files found",
                "stats": {
                    "total_files": 0,
                    "processed": 0,
                    "failed": 0,
                },
            }

        # Step 5: Process each file
        processed_documents = []
        failed_files = []

        for idx, file_metadata in enumerate(processable_files, 1):
            file_id = file_metadata["id"]
            file_name = file_metadata["name"]
            mime_type = file_metadata["mimeType"]

            # Update task progress
            self.update_state(
                state="PROCESSING",
                meta={
                    "current": idx,
                    "total": total_files,
                    "current_file": file_name,
                    "status": f"Processing {idx}/{total_files}",
                },
            )

            logger.info(f"Processing {idx}/{total_files}: {file_name}")

            try:
                # Download file
                file_content = drive_service.download_file(file_id, mime_type)

                # Extract text
                raw_text = text_extractor.extract_text(file_content, mime_type, file_name)

                # Clean text
                cleaned_text = text_extractor.clean_text(raw_text)

                # Get word count
                word_count = text_extractor.get_word_count(cleaned_text)

                # Build document object
                document = {
                    "id": file_id,
                    "title": file_name,
                    "url": file_metadata.get("webViewLink", ""),
                    "mimeType": mime_type,
                    "text_content": cleaned_text,
                    "metadata": {
                        "author": file_metadata.get("owners", [{}])[0].get(
                            "emailAddress", "Unknown"
                        ),
                        "modified_at": file_metadata.get("modifiedTime", ""),
                        "size_bytes": file_metadata.get("size"),
                        "word_count": word_count,
                        "processed_at": datetime.now().isoformat(),
                        "processed_by_user": user.email,
                    },
                }

                processed_documents.append(document)
                logger.info(f"  ✓ Extracted {word_count} words")

            except Exception as e:
                logger.error(f"  ✗ Failed to process {file_name}: {str(e)}")
                failed_files.append({"file": file_name, "error": str(e)})
                continue

        # Step 6: Save results to JSON
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / f"extracted_documents_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_documents, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved results to {output_file}")

        # Step 7: Return summary
        total_words = sum(doc["metadata"]["word_count"] for doc in processed_documents)

        return {
            "status": "completed",
            "message": f"Successfully processed {len(processed_documents)} files",
            "documents_file": str(output_file),
            "total_documents": len(processed_documents),
            "failed_files": failed_files,
        }

    except Exception as e:
        logger.error(f"Task failed: {str(e)}")

        # Retry with exponential backoff for transient errors
        if "Rate limit" in str(e) or "Quota" in str(e):
            raise self.retry(exc=e, countdown=min(60 * (2**self.request.retries), 600))

        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="generate_knowledge_graph",
    max_retries=3,
    default_retry_delay=60,
)
def generate_knowledge_graph_task(
    self: DatabaseTask,
    documents_file: str,
    output_dir: str = "processed_files",
    similarity_threshold: float = 0.75,
    max_tags_per_doc: int = 5,
    max_entities_per_doc: int = 10,
    use_top_k_similarity: bool = True,
    top_k_neighbors: int = 2,
    min_similarity: float = 0.3,
    enable_hierarchy: bool = True,
    hierarchy_split_threshold: int = 10,
    hierarchy_cross_cutting_threshold: int = 5,
) -> Dict[str, Any]:
    """
    Generate knowledge graph from extracted documents.

    This task:
    1. Loads extracted documents from JSON file
    2. Generates OpenAI embeddings
    3. Calculates similarity matrix
    4. Extracts LLM-based tags, summaries, and entities
    5. Builds tag hierarchy (if enabled)
    6. Builds graph structure (nodes + edges)
    7. Saves graph_data.json

    Args:
        documents_file: Path to extracted documents JSON
        output_dir: Directory to save graph output
        similarity_threshold: Minimum similarity to create edge (0.0-1.0) - only used if use_top_k_similarity=False
        max_tags_per_doc: Maximum number of tags per document
        max_entities_per_doc: Maximum number of entities per document
        use_top_k_similarity: If True, use top-K neighbors approach (default: True)
        top_k_neighbors: Number of top similar documents per document (default: 2)
        min_similarity: Minimum similarity to create edge in top-K mode (default: 0.3)
        enable_hierarchy: If True, build hierarchical tag structure (default: True)
        hierarchy_split_threshold: Min documents per tag to consider splitting (default: 10)
        hierarchy_cross_cutting_threshold: Min docs with tag combo for cross-cutting (default: 5)

    Returns:
        Dictionary with graph statistics
    """
    logger.info(f"Generating knowledge graph from {documents_file}")

    try:
        # Step 1: Load extracted documents
        documents_path = Path(documents_file)
        if not documents_path.exists():
            raise FileNotFoundError(f"Documents file not found: {documents_file}")

        with open(documents_path, "r", encoding="utf-8") as f:
            extracted_docs = json.load(f)

        logger.info(f"Loaded {len(extracted_docs)} documents")

        # Update progress
        self.update_state(
            state="PROCESSING",
            meta={
                "current": 0,
                "total": len(extracted_docs),
                "status": "Loading documents...",
            },
        )

        # Step 2: Transform to graph builder format
        graph_documents = []
        for doc in extracted_docs:
            graph_documents.append(
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "url": doc.get("url", ""),
                    "text": doc.get("text_content", ""),
                    "author": doc.get("metadata", {}).get("author", "Unknown"),
                    "modified": doc.get("metadata", {}).get("modified_at", ""),
                }
            )

        # Step 3: Build graph
        self.update_state(
            state="PROCESSING",
            meta={
                "current": len(extracted_docs) // 4,
                "total": len(extracted_docs),
                "status": "Generating embeddings...",
            },
        )

        graph_builder = GraphBuilder(
            similarity_threshold=similarity_threshold,
            max_tags_per_doc=max_tags_per_doc,
            max_entities_per_doc=max_entities_per_doc,
            use_top_k_similarity=use_top_k_similarity,
            top_k_neighbors=top_k_neighbors,
            min_similarity=min_similarity,
            enable_hierarchy=enable_hierarchy,
            hierarchy_split_threshold=hierarchy_split_threshold,
            hierarchy_cross_cutting_threshold=hierarchy_cross_cutting_threshold,
        )

        graph_data = graph_builder.build_graph_from_documents(graph_documents)

        # Step 4: Save graph data
        self.update_state(
            state="PROCESSING",
            meta={
                "current": len(extracted_docs),
                "total": len(extracted_docs),
                "status": "Saving graph data...",
            },
        )

        output_path = Path(output_dir) / "graph_data.json"
        graph_builder.save_graph_to_file(graph_data, output_path)

        logger.info(f"Saved graph data to {output_path}")

        # Step 5: Return summary
        # Calculate average tags (handle both flat and hierarchical structure)
        total_tags = 0
        for node in graph_data["nodes"]:
            tags = node.get("tags", [])
            if isinstance(tags, dict):
                # Hierarchical structure - count low-level tags
                total_tags += len(tags.get("low_level", []))
            else:
                # Flat structure
                total_tags += len(tags)

        avg_tags = total_tags / len(graph_data["nodes"]) if graph_data["nodes"] else 0

        return {
            "status": "completed",
            "message": f"Generated knowledge graph with {len(graph_data['nodes'])} nodes and {len(graph_data['edges'])} edges",
            "graph_file": str(output_path),
            "nodes": len(graph_data["nodes"]),
            "edges": len(graph_data["edges"]),
        }

    except Exception as e:
        logger.error(f"Graph generation failed: {str(e)}")

        # Retry for transient OpenAI errors
        if "rate_limit" in str(e).lower() or "timeout" in str(e).lower():
            raise self.retry(exc=e, countdown=min(60 * (2**self.request.retries), 600))

        raise
