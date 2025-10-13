"""Celery tasks for tag-based processing."""
from typing import List, Dict, Optional
import uuid
from datetime import datetime

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.file import File
from app.models.job import ProcessingJob
from app.services.semantic import SemanticProcessingService


@celery_app.task(name="app.workers.tasks.test_task")
def test_task(x: int, y: int) -> int:
    """Test task for verification."""
    return x + y


@celery_app.task(
    name="app.workers.tasks.process_files_with_tags",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_files_with_tags(
    self,
    file_ids: List[str],
    job_id: Optional[str] = None,
    min_shared_tags: int = 2,
) -> Dict:
    """
    Process files through tag-based pipeline: tag extraction, relationships, clustering.

    Args:
        file_ids: List of file IDs to process
        job_id: Optional processing job ID for tracking
        min_shared_tags: Minimum number of shared tags for creating relationships

    Returns:
        Dictionary with processing results and statistics
    """
    db = SessionLocal()
    service = SemanticProcessingService(min_shared_tags=min_shared_tags)

    try:
        # Update job status if provided
        if job_id:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if job:
                job.status = "processing"
                db.commit()

        # Fetch files
        files = db.query(File).filter(File.id.in_(file_ids)).all()

        if not files:
            raise ValueError("No files found with provided IDs")

        # Run tag-based processing
        results = service.process_documents(
            session=db,
            files=files,
            min_shared=min_shared_tags,
            show_progress=False,
        )

        # Prepare response
        response = {
            "status": "completed",
            "num_files": len(files),
            "num_relationships": len(results["relationships"]),
            "num_clusters": len(results["clusters"]),
            "cluster_sizes": [len(cluster_files) for _, cluster_files in results["clusters"]],
        }

        # Update job if provided
        if job_id:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.processed_files = len(files)
                job.progress_percentage = 100
                db.commit()

        return response

    except Exception as e:
        # Update job on failure
        if job_id:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()

        # Retry task
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.extract_tags_task",
    bind=True,
    max_retries=3,
)
def extract_tags_task(
    self,
    file_ids: List[str],
    min_tag_frequency: int = 2,
    max_tags_per_doc: int = 10,
) -> Dict:
    """
    Extract tags from files.

    Args:
        file_ids: List of file IDs to process
        min_tag_frequency: Minimum word frequency for tag extraction
        max_tags_per_doc: Maximum number of tags per document

    Returns:
        Dictionary with number of processed files and tags
    """
    db = SessionLocal()
    service = SemanticProcessingService(
        min_tag_frequency=min_tag_frequency,
        max_tags_per_doc=max_tags_per_doc,
    )

    try:
        # Fetch files
        files = db.query(File).filter(File.id.in_(file_ids)).all()

        if not files:
            raise ValueError("No files found with provided IDs")

        # Extract and store tags
        file_tags_map = service.extract_and_store_tags(
            session=db,
            files=files,
            show_progress=False,
        )

        # Count total tags
        total_tags = sum(len(tags) for tags in file_tags_map.values())

        return {
            "status": "completed",
            "num_files": len(files),
            "total_tags": total_tags,
            "avg_tags_per_file": total_tags / len(files) if files else 0,
        }

    except Exception as e:
        db.rollback()
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.create_tag_relationships",
    bind=True,
    max_retries=3,
)
def create_tag_relationships(
    self,
    file_ids: List[str],
    min_shared_tags: int = 2,
) -> Dict:
    """
    Create tag-based relationships between files.

    Args:
        file_ids: List of file IDs to process
        min_shared_tags: Minimum number of shared tags

    Returns:
        Dictionary with number of relationships created
    """
    db = SessionLocal()
    service = SemanticProcessingService(min_shared_tags=min_shared_tags)

    try:
        # Fetch files with tags
        from app.models.file_tag import FileTag

        files_with_tags = db.query(File).join(FileTag).filter(
            File.id.in_(file_ids)
        ).distinct().all()

        if not files_with_tags:
            raise ValueError("No files found with tags")

        # Create relationships
        relationships, adjacency = service.create_relationships_with_graph(
            session=db,
            files=files_with_tags,
            min_shared=min_shared_tags,
        )

        return {
            "status": "completed",
            "num_files": len(files_with_tags),
            "num_relationships": len(relationships),
            "avg_degree": sum(len(neighbors) for neighbors in adjacency.values()) / len(adjacency) if adjacency else 0,
        }

    except Exception as e:
        db.rollback()
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.cluster_documents",
    bind=True,
    max_retries=3,
)
def cluster_documents(
    self,
    file_ids: List[str],
) -> Dict:
    """
    Create clusters from existing relationships using community detection.

    Args:
        file_ids: List of file IDs to cluster

    Returns:
        Dictionary with clustering results
    """
    db = SessionLocal()
    service = SemanticProcessingService()

    try:
        from app.models.relationship import FileRelationship

        # Fetch files
        files = db.query(File).filter(File.id.in_(file_ids)).all()

        if not files:
            raise ValueError("No files found with provided IDs")

        # Build adjacency graph from existing relationships
        file_id_to_idx = {str(f.id): i for i, f in enumerate(files)}
        adjacency = {i: set() for i in range(len(files))}

        # Query relationships
        relationships = db.query(FileRelationship).filter(
            (FileRelationship.source_file_id.in_(file_ids)) |
            (FileRelationship.target_file_id.in_(file_ids))
        ).all()

        for rel in relationships:
            src_idx = file_id_to_idx.get(str(rel.source_file_id))
            tgt_idx = file_id_to_idx.get(str(rel.target_file_id))
            if src_idx is not None and tgt_idx is not None:
                adjacency[src_idx].add(tgt_idx)
                adjacency[tgt_idx].add(src_idx)

        # Create clusters
        clusters_with_files = service.create_clusters_from_communities(
            session=db,
            files=files,
            adjacency=adjacency,
        )

        return {
            "status": "completed",
            "num_files": len(files),
            "num_clusters": len(clusters_with_files),
            "cluster_sizes": [len(cluster_files) for _, cluster_files in clusters_with_files],
        }

    except Exception as e:
        db.rollback()
        raise self.retry(exc=e)

    finally:
        db.close()


# Keep old task names for backwards compatibility (deprecated)
@celery_app.task(
    name="app.workers.tasks.process_files_semantically",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_files_semantically(
    self,
    file_ids: List[str],
    job_id: Optional[str] = None,
    similarity_threshold: float = 0.5,
) -> Dict:
    """
    DEPRECATED: Use process_files_with_tags instead.

    Maintained for backwards compatibility with existing code.
    Converts embedding-based parameters to tag-based equivalents.
    """
    # Convert similarity threshold to min_shared_tags
    # 0.5 similarity ~= 2 shared tags
    # 0.3 similarity ~= 1 shared tag
    # 0.7 similarity ~= 3 shared tags
    min_shared_tags = max(1, int(similarity_threshold * 4))

    return process_files_with_tags(
        file_ids=file_ids,
        job_id=job_id,
        min_shared_tags=min_shared_tags,
    )


@celery_app.task(
    name="app.workers.tasks.generate_embeddings",
    bind=True,
    max_retries=3,
)
def generate_embeddings(
    self,
    file_ids: List[str],
    model_name: str = "all-MiniLM-L6-v2",
) -> Dict:
    """
    DEPRECATED: Use extract_tags_task instead.

    Maintained for backwards compatibility.
    """
    return extract_tags_task(
        file_ids=file_ids,
        min_tag_frequency=2,
        max_tags_per_doc=10,
    )


@celery_app.task(
    name="app.workers.tasks.create_semantic_relationships",
    bind=True,
    max_retries=3,
)
def create_semantic_relationships(
    self,
    file_ids: List[str],
    similarity_threshold: float = 0.5,
) -> Dict:
    """
    DEPRECATED: Use create_tag_relationships instead.

    Maintained for backwards compatibility.
    """
    min_shared_tags = max(1, int(similarity_threshold * 4))

    return create_tag_relationships(
        file_ids=file_ids,
        min_shared_tags=min_shared_tags,
    )
