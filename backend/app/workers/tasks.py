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
from app.db.models.user import User
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


async def cleanup_duplicate_tags_for_user(session, user_uuid) -> Dict[str, Any]:
    """
    Clean up duplicate tags that exist at both high-level and low-level for a user.

    This function:
    1. Finds tags with the same name (case-insensitive) at different levels
    2. Promotes low-level document associations to high-level
    3. Deletes redundant low-level tags

    Args:
        session: Async database session
        user_uuid: User UUID

    Returns:
        Dictionary with cleanup results
    """
    from sqlalchemy import select
    from app.db.models.tag import Tag
    from app.db.models.document_tag import DocumentTag

    # Get all tags for this user
    tags_result = await session.execute(
        select(Tag).filter(Tag.user_id == user_uuid)
    )
    all_tags = tags_result.scalars().all()

    # Group tags by lowercase name
    tag_groups = {}
    for tag in all_tags:
        key = tag.name.lower().strip()
        if key not in tag_groups:
            tag_groups[key] = {"high_level": [], "low_level": []}
        tag_groups[key][tag.tag_type].append(tag)

    # Find groups with both high and low level tags
    cleaned_tags = []
    promoted_count = 0
    deleted_count = 0

    for tag_name, levels in tag_groups.items():
        if levels["high_level"] and levels["low_level"]:
            # Use the first high-level tag as the canonical one
            canonical_tag = levels["high_level"][0]
            cleaned_tags.append(canonical_tag.name)

            logger.info(
                f"Consolidating duplicate tag '{tag_name}': "
                f"{len(levels['high_level'])} high-level, {len(levels['low_level'])} low-level"
            )

            # For each low-level tag with the same name
            for low_tag in levels["low_level"]:
                # Get all document associations for this low-level tag
                doc_tags_result = await session.execute(
                    select(DocumentTag).filter(DocumentTag.tag_id == low_tag.id)
                )
                doc_tags = doc_tags_result.scalars().all()

                for doc_tag in doc_tags:
                    # Check if this document already has a high-level association with canonical tag
                    existing_result = await session.execute(
                        select(DocumentTag).filter(
                            DocumentTag.document_id == doc_tag.document_id,
                            DocumentTag.tag_id == canonical_tag.id,
                            DocumentTag.tag_level == "high"
                        )
                    )
                    existing = existing_result.scalar_one_or_none()

                    if existing:
                        # Document already has high-level association, just delete the low-level one
                        await session.delete(doc_tag)
                    else:
                        # Promote: update the association to point to canonical tag at high level
                        doc_tag.tag_id = canonical_tag.id
                        doc_tag.tag_level = "high"
                        promoted_count += 1

                # Delete the redundant low-level tag
                await session.delete(low_tag)
                deleted_count += 1

    if cleaned_tags:
        await session.commit()

    return {
        "cleaned_tags": cleaned_tags,
        "promoted_associations": promoted_count,
        "deleted_tags": deleted_count,
    }


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
        user = self.session.query(User).filter(User.google_user_id == user_id).first()

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

        # Step 5: Get user UUID for database checks
        user_uuid = user.id

        # Step 6: Process each file
        processed_documents = []
        failed_files = []
        skipped_files = []

        for idx, file_metadata in enumerate(processable_files, 1):
            file_id = file_metadata["id"]
            file_name = file_metadata["name"]
            mime_type = file_metadata["mimeType"]

            # Check if file is already processed in database
            from app.db.models.document import Document
            existing_doc = self.session.query(Document).filter(
                Document.id == file_id,
                Document.user_id == user_uuid
            ).first()

            if existing_doc:
                logger.info(f"Skipping {idx}/{total_files}: {file_name} (already processed)")
                skipped_files.append({
                    "id": file_id,
                    "name": file_name,
                    "reason": "already_processed"
                })
                continue

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

        message_parts = [f"Successfully processed {len(processed_documents)} files"]
        if skipped_files:
            message_parts.append(f"skipped {len(skipped_files)} already-processed files")
        if failed_files:
            message_parts.append(f"{len(failed_files)} failed")

        return {
            "status": "completed",
            "message": ", ".join(message_parts),
            "documents_file": str(output_file),
            "total_documents": len(processed_documents),
            "skipped_files": skipped_files,
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
    user_id: str,
    documents_file: str,
    output_dir: str = "processed_files",
    similarity_threshold: float = 0.75,
    max_tags_per_doc: int = 5,
    max_entities_per_doc: int = 10,
    use_top_k_similarity: bool = True,
    top_k_neighbors: int = 2,
    min_similarity: float = 0.3,
    enable_hierarchy: bool = True,
    hierarchy_split_threshold: int = 8,  # Hardcoded as requested
    hierarchy_cross_cutting_threshold: int = 5,
) -> Dict[str, Any]:
    """
    Generate knowledge graph from extracted documents and save to PostgreSQL.

    This task:
    1. Loads extracted documents from JSON file
    2. Generates OpenAI embeddings
    3. Extracts LLM-based tags, summaries, and entities
    4. Calculates similarity matrix
    5. Builds tag hierarchy (if enabled)
    6. Saves everything to PostgreSQL database

    Args:
        user_id: User ID for multi-tenant isolation
        documents_file: Path to extracted documents JSON
        output_dir: Directory to save graph output (kept for compatibility)
        similarity_threshold: Minimum similarity to create edge (0.0-1.0)
        max_tags_per_doc: Maximum number of tags per document
        max_entities_per_doc: Maximum number of entities per document
        use_top_k_similarity: If True, use top-K neighbors approach (default: True)
        top_k_neighbors: Number of top similar documents per document (default: 2)
        min_similarity: Minimum similarity to create edge in top-K mode (default: 0.3)
        enable_hierarchy: If True, build hierarchical tag structure (default: True)
        hierarchy_split_threshold: Min documents per tag to consider splitting (default: 8)
        hierarchy_cross_cutting_threshold: Min docs with tag combo for cross-cutting (default: 5)

    Returns:
        Dictionary with graph statistics
    """
    logger.info(f"Generating knowledge graph from {documents_file} for user {user_id}")

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

        # Step 4: Save to PostgreSQL database
        self.update_state(
            state="PROCESSING",
            meta={
                "current": len(extracted_docs),
                "total": len(extracted_docs),
                "status": "Saving to database...",
            },
        )

        # Import async dependencies
        import asyncio
        from uuid import UUID
        from app.db.session import AsyncSessionLocal
        from app.db.models.user import User
        from app.db.models.document import Document
        from app.db.models.tag import Tag
        from app.db.models.entity import Entity
        from app.db.models.document_tag import DocumentTag
        from app.db.models.document_entity import DocumentEntity
        from app.db.models.document_similarity import DocumentSimilarity

        async def save_to_database():
            """Save graph data to PostgreSQL."""
            # Look up User by google_user_id to get the actual UUID
            from sqlalchemy import select as sa_select

            async with AsyncSessionLocal() as session:
                # Get user UUID from google_user_id
                user_result = await session.execute(
                    sa_select(User).filter(User.google_user_id == user_id)
                )
                user = user_result.scalar_one_or_none()

                if not user:
                    raise ValueError(f"User not found with google_user_id: {user_id}")

                user_uuid = user.id
                logger.info(f"Found user UUID {user_uuid} for google_user_id {user_id}")

                # Continue with saving...
                # Create documents
                for node in graph_data["nodes"]:
                    # Find embedding from original extracted_docs
                    orig_doc = next((d for d in extracted_docs if d["id"] == node["id"]), None)

                    doc = Document(
                        id=node["id"],
                        user_id=user_uuid,
                        title=node["title"],
                        url=node.get("url", ""),
                        author=node.get("author", "Unknown"),
                        modified_at=None,  # TODO: Parse from node["modified"]
                        text_content=orig_doc.get("text_content", "") if orig_doc else "",
                        summary=node.get("summary", ""),
                        word_count=orig_doc.get("metadata", {}).get("word_count", 0) if orig_doc else 0,
                        embedding=None,  # Will be set by embedding service
                        is_enabled=True,
                    )
                    session.add(doc)

                await session.flush()

                # Create tags and associations
                # Track tag name -> (Tag object, original_level) to prevent duplicates
                tag_cache = {}  # name (lowercase) -> (Tag, tag_type)
                high_level_tag_names = set()  # Track high-level tags for deduplication

                for node in graph_data["nodes"]:
                    tags_data = node.get("tags", {})
                    high_level_tags = tags_data.get("high_level", []) if isinstance(tags_data, dict) else []
                    low_level_tags = tags_data.get("low_level", []) if isinstance(tags_data, dict) else []

                    # Create high-level tags
                    for tag_name in high_level_tags:
                        tag_key = tag_name.lower().strip()
                        high_level_tag_names.add(tag_key)

                        if tag_key not in tag_cache:
                            tag = Tag(
                                user_id=user_uuid,
                                name=tag_name,
                                tag_type="high_level",
                            )
                            session.add(tag)
                            await session.flush()
                            await session.refresh(tag)
                            tag_cache[tag_key] = (tag, "high_level")

                        # Create association
                        doc_tag = DocumentTag(
                            document_id=node["id"],
                            tag_id=tag_cache[tag_key][0].id,
                            tag_level="high",
                        )
                        session.add(doc_tag)

                    # Create low-level tags (skip if same name exists as high-level)
                    for tag_name in low_level_tags:
                        tag_key = tag_name.lower().strip()

                        # Skip if this tag name already exists as high-level
                        # The document is already associated via the high-level tag
                        if tag_key in high_level_tag_names:
                            logger.warning(
                                f"Skipping low-level tag '{tag_name}' for doc {node['id']} - "
                                f"already exists as high-level tag"
                            )
                            continue

                        if tag_key not in tag_cache:
                            tag = Tag(
                                user_id=user_uuid,
                                name=tag_name,
                                tag_type="low_level",
                            )
                            session.add(tag)
                            await session.flush()
                            await session.refresh(tag)
                            tag_cache[tag_key] = (tag, "low_level")

                        # Create association
                        doc_tag = DocumentTag(
                            document_id=node["id"],
                            tag_id=tag_cache[tag_key][0].id,
                            tag_level="low",
                        )
                        session.add(doc_tag)

                await session.flush()

                # Create entities and associations
                entity_cache = {}  # name -> Entity object

                for node in graph_data["nodes"]:
                    entities = node.get("entities", [])

                    for entity_name in entities:
                        if entity_name not in entity_cache:
                            entity = Entity(
                                user_id=user_uuid,
                                name=entity_name,
                                entity_type="UNKNOWN",  # TODO: Extract type from LLM
                            )
                            session.add(entity)
                            await session.flush()
                            await session.refresh(entity)
                            entity_cache[entity_name] = entity

                        # Create association
                        doc_entity = DocumentEntity(
                            document_id=node["id"],
                            entity_id=entity_cache[entity_name].id,
                        )
                        session.add(doc_entity)

                await session.flush()

                # Create similarity edges
                for edge in graph_data["edges"]:
                    source = edge["source"]
                    target = edge["target"]
                    score = edge["similarity"]

                    # Skip self-loops (shouldn't happen, but be defensive)
                    if source == target:
                        logger.warning(f"Skipping self-loop edge: {source} -> {target}")
                        continue

                    # Canonical ordering (ensure source < target for database constraint)
                    if source > target:
                        source, target = target, source

                    # Double-check constraint will be satisfied
                    if source >= target:
                        logger.error(f"Constraint violation would occur: {source} >= {target}")
                        continue

                    similarity = DocumentSimilarity(
                        source_document_id=source,
                        target_document_id=target,
                        similarity_score=score,
                    )
                    session.add(similarity)

                await session.commit()

                logger.info(f"Saved {len(graph_data['nodes'])} documents to PostgreSQL")

                # Run tag cleanup to consolidate any duplicate tags at different levels
                cleanup_result = await cleanup_duplicate_tags_for_user(session, user_uuid)
                if cleanup_result["cleaned_tags"]:
                    logger.info(
                        f"Tag cleanup: consolidated {len(cleanup_result['cleaned_tags'])} duplicate tags, "
                        f"promoted {cleanup_result['promoted_associations']} associations"
                    )

                return {
                    "nodes": len(graph_data["nodes"]),
                    "edges": len(graph_data["edges"]),
                    "tags": len(tag_cache),
                    "entities": len(entity_cache),
                }

        # Run async save
        result = asyncio.run(save_to_database())

        return {
            "status": "completed",
            "message": f"Generated knowledge graph with {result['nodes']} nodes and {result['edges']} edges",
            "nodes": result["nodes"],
            "edges": result["edges"],
            "tags": result["tags"],
            "entities": result["entities"],
        }

    except Exception as e:
        logger.error(f"Graph generation failed: {str(e)}")

        # Retry for transient OpenAI errors
        if "rate_limit" in str(e).lower() or "timeout" in str(e).lower():
            raise self.retry(exc=e, countdown=min(60 * (2**self.request.retries), 600))

        raise
