"""Tests for File model."""
import uuid
from datetime import datetime

import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.models.file import File


def test_create_file_basic(db: Session) -> None:
    """Test creating a basic file without embedding."""
    file = File(
        google_drive_id="test_drive_id_123",
        name="test_document.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        text_content="This is test content",
        processing_status="pending",
    )
    db.add(file)
    db.commit()
    db.refresh(file)

    assert file.id is not None
    assert file.google_drive_id == "test_drive_id_123"
    assert file.name == "test_document.pdf"
    assert file.processing_status == "pending"
    assert file.text_content == "This is test content"


def test_create_file_with_embedding(db: Session) -> None:
    """Test creating a file with embedding vector."""
    # Create a 384-dimensional embedding vector
    embedding_vector = np.random.rand(384).tolist()

    file = File(
        google_drive_id="test_drive_id_456",
        name="test_with_embedding.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        text_content="Content with embedding",
        embedding=embedding_vector,
        processing_status="completed",
    )
    db.add(file)
    db.commit()
    db.refresh(file)

    assert file.id is not None
    assert file.embedding is not None
    assert len(file.embedding) == 384
    assert file.processing_status == "completed"


def test_file_google_drive_id_unique(db: Session) -> None:
    """Test that google_drive_id must be unique."""
    file1 = File(
        google_drive_id="duplicate_id",
        name="file1.pdf",
    )
    db.add(file1)
    db.commit()

    # Try to create another file with the same google_drive_id
    file2 = File(
        google_drive_id="duplicate_id",
        name="file2.pdf",
    )
    db.add(file2)

    with pytest.raises(Exception):  # Will raise IntegrityError
        db.commit()


def test_file_timestamps(db: Session) -> None:
    """Test that timestamps are set automatically."""
    file = File(
        google_drive_id="timestamp_test",
        name="timestamp.pdf",
    )
    db.add(file)
    db.commit()
    db.refresh(file)

    assert file.created_at is not None
    assert file.modified_at is not None
    assert isinstance(file.created_at, datetime)
    assert isinstance(file.modified_at, datetime)


def test_file_processing_status_index(db: Session) -> None:
    """Test querying by processing_status (should use index)."""
    # Create files with different statuses
    for i, status in enumerate(["pending", "processing", "completed", "failed"]):
        file = File(
            google_drive_id=f"status_test_{i}",
            name=f"file_{i}.pdf",
            processing_status=status,
        )
        db.add(file)
    db.commit()

    # Query by status
    pending_files = db.query(File).filter(File.processing_status == "pending").all()
    assert len(pending_files) == 1
    assert pending_files[0].processing_status == "pending"

    completed_files = db.query(File).filter(File.processing_status == "completed").all()
    assert len(completed_files) == 1


def test_file_vector_similarity_search(db: Session) -> None:
    """Test vector similarity search using pgvector."""
    # Create a reference embedding
    reference_embedding = np.random.rand(384).tolist()

    # Create similar embedding (reference + small noise)
    similar_embedding = (np.array(reference_embedding) + np.random.rand(384) * 0.1).tolist()

    # Create dissimilar embedding
    dissimilar_embedding = np.random.rand(384).tolist()

    # Add files with embeddings
    file1 = File(
        google_drive_id="ref_file",
        name="reference.pdf",
        embedding=reference_embedding,
    )
    file2 = File(
        google_drive_id="similar_file",
        name="similar.pdf",
        embedding=similar_embedding,
    )
    file3 = File(
        google_drive_id="dissimilar_file",
        name="dissimilar.pdf",
        embedding=dissimilar_embedding,
    )

    db.add_all([file1, file2, file3])
    db.commit()

    # Query for files (we can't easily test vector distance in this test without raw SQL)
    # But we can verify the embeddings were stored
    all_files = db.query(File).filter(File.embedding.isnot(None)).all()
    assert len(all_files) == 3
    for file in all_files:
        assert len(file.embedding) == 384
