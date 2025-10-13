"""Celery tasks."""
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
    Process files through semantic pipeline: embeddings, relationships, clustering.

    Args:
        file_ids: List of file IDs to process
        job_id: Optional processing job ID for tracking
        similarity_threshold: Minimum similarity for creating relationships

    Returns:
        Dictionary with processing results and statistics
    """
    db = SessionLocal()
    service = SemanticProcessingService(similarity_threshold=similarity_threshold)

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

        # Run semantic processing
        results = service.process_documents(
            session=db,
            files=files,
            threshold=similarity_threshold,
            batch_size=16,
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
    Generate embeddings for files.

    Args:
        file_ids: List of file IDs to process
        model_name: Sentence transformer model name

    Returns:
        Dictionary with number of processed files
    """
    db = SessionLocal()
    service = SemanticProcessingService(model_name=model_name)

    try:
        # Fetch files
        files = db.query(File).filter(File.id.in_(file_ids)).all()

        if not files:
            raise ValueError("No files found with provided IDs")

        # Generate embeddings
        texts = [f.text_content for f in files]
        embeddings = service.generate_embeddings(texts, show_progress=False)

        # Update files with embeddings
        for file, embedding in zip(files, embeddings):
            file.embedding = embedding.tolist()
            file.processing_status = "completed"

        db.commit()

        return {
            "status": "completed",
            "num_files": len(files),
        }

    except Exception as e:
        db.rollback()
        raise self.retry(exc=e)

    finally:
        db.close()


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
    Create semantic relationships between files based on embeddings.

    Args:
        file_ids: List of file IDs to process
        similarity_threshold: Minimum similarity for creating relationships

    Returns:
        Dictionary with number of relationships created
    """
    db = SessionLocal()
    service = SemanticProcessingService(similarity_threshold=similarity_threshold)

    try:
        # Fetch files with embeddings
        files = db.query(File).filter(
            File.id.in_(file_ids),
            File.embedding.isnot(None)
        ).all()

        if not files:
            raise ValueError("No files found with embeddings")

        # Extract embeddings
        import numpy as np
        embeddings = np.array([f.embedding for f in files])

        # Create relationships
        relationships, adjacency = service.create_relationships_with_graph(
            session=db,
            files=files,
            embeddings=embeddings,
            threshold=similarity_threshold,
        )

        return {
            "status": "completed",
            "num_files": len(files),
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
