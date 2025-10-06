"""Tests for FileRelationship model."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.file import File
from app.models.relationship import FileRelationship


def test_create_relationship(db: Session) -> None:
    """Test creating a basic file relationship."""
    # Create two files
    file1 = File(google_drive_id="file1", name="doc1.pdf")
    file2 = File(google_drive_id="file2", name="doc2.pdf")
    db.add_all([file1, file2])
    db.commit()

    # Create relationship
    relationship = FileRelationship(
        source_file_id=file1.id,
        target_file_id=file2.id,
        similarity_score=0.85,
        relationship_type="semantic_similarity",
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)

    assert relationship.id is not None
    assert relationship.source_file_id == file1.id
    assert relationship.target_file_id == file2.id
    assert relationship.similarity_score == 0.85
    assert relationship.relationship_type == "semantic_similarity"


def test_relationship_no_self_reference(db: Session) -> None:
    """Test that a file cannot have a relationship with itself."""
    file = File(google_drive_id="self_ref", name="self.pdf")
    db.add(file)
    db.commit()

    # Try to create self-relationship
    relationship = FileRelationship(
        source_file_id=file.id,
        target_file_id=file.id,
        similarity_score=1.0,
    )
    db.add(relationship)

    with pytest.raises(IntegrityError) as exc_info:
        db.commit()
    assert "ck_no_self_relationship" in str(exc_info.value)


def test_relationship_similarity_score_min_bound(db: Session) -> None:
    """Test that similarity_score cannot be less than 0.0."""
    file1 = File(google_drive_id="file1_min", name="doc1.pdf")
    file2 = File(google_drive_id="file2_min", name="doc2.pdf")
    db.add_all([file1, file2])
    db.commit()

    # Try to create relationship with negative similarity
    relationship = FileRelationship(
        source_file_id=file1.id,
        target_file_id=file2.id,
        similarity_score=-0.1,
    )
    db.add(relationship)

    with pytest.raises(IntegrityError) as exc_info:
        db.commit()
    assert "ck_similarity_score_range" in str(exc_info.value)


def test_relationship_similarity_score_max_bound(db: Session) -> None:
    """Test that similarity_score cannot be greater than 1.0."""
    file1 = File(google_drive_id="file1_max", name="doc1.pdf")
    file2 = File(google_drive_id="file2_max", name="doc2.pdf")
    db.add_all([file1, file2])
    db.commit()

    # Try to create relationship with similarity > 1.0
    relationship = FileRelationship(
        source_file_id=file1.id,
        target_file_id=file2.id,
        similarity_score=1.5,
    )
    db.add(relationship)

    with pytest.raises(IntegrityError) as exc_info:
        db.commit()
    assert "ck_similarity_score_range" in str(exc_info.value)


def test_relationship_similarity_score_valid_bounds(db: Session) -> None:
    """Test that similarity_score can be exactly 0.0 or 1.0."""
    file1 = File(google_drive_id="file1_bounds", name="doc1.pdf")
    file2 = File(google_drive_id="file2_bounds", name="doc2.pdf")
    file3 = File(google_drive_id="file3_bounds", name="doc3.pdf")
    db.add_all([file1, file2, file3])
    db.commit()

    # Create relationship with score = 0.0
    rel1 = FileRelationship(
        source_file_id=file1.id,
        target_file_id=file2.id,
        similarity_score=0.0,
    )
    # Create relationship with score = 1.0
    rel2 = FileRelationship(
        source_file_id=file1.id,
        target_file_id=file3.id,
        similarity_score=1.0,
    )
    db.add_all([rel1, rel2])
    db.commit()

    assert rel1.similarity_score == 0.0
    assert rel2.similarity_score == 1.0


def test_relationship_unique_pair(db: Session) -> None:
    """Test that duplicate relationships are not allowed."""
    file1 = File(google_drive_id="file1_dup", name="doc1.pdf")
    file2 = File(google_drive_id="file2_dup", name="doc2.pdf")
    db.add_all([file1, file2])
    db.commit()

    # Create first relationship
    rel1 = FileRelationship(
        source_file_id=file1.id,
        target_file_id=file2.id,
        similarity_score=0.8,
    )
    db.add(rel1)
    db.commit()

    # Try to create duplicate relationship
    rel2 = FileRelationship(
        source_file_id=file1.id,
        target_file_id=file2.id,
        similarity_score=0.9,
    )
    db.add(rel2)

    with pytest.raises(IntegrityError) as exc_info:
        db.commit()
    assert "uq_file_relationship_pair" in str(exc_info.value)


def test_relationship_cascade_delete_source(db: Session) -> None:
    """Test that relationships are deleted when source file is deleted."""
    file1 = File(google_drive_id="source_cascade", name="source.pdf")
    file2 = File(google_drive_id="target_1", name="target1.pdf")
    file3 = File(google_drive_id="target_2", name="target2.pdf")
    db.add_all([file1, file2, file3])
    db.commit()

    # Create relationships
    rel1 = FileRelationship(source_file_id=file1.id, target_file_id=file2.id, similarity_score=0.8)
    rel2 = FileRelationship(source_file_id=file1.id, target_file_id=file3.id, similarity_score=0.7)
    db.add_all([rel1, rel2])
    db.commit()

    # Verify relationships exist
    assert db.query(FileRelationship).count() == 2

    # Delete source file
    db.delete(file1)
    db.commit()

    # Verify relationships were cascade deleted
    assert db.query(FileRelationship).count() == 0
    # Target files should still exist
    assert db.query(File).count() == 2


def test_relationship_cascade_delete_target(db: Session) -> None:
    """Test that relationships are deleted when target file is deleted."""
    file1 = File(google_drive_id="source_1", name="source1.pdf")
    file2 = File(google_drive_id="source_2", name="source2.pdf")
    file3 = File(google_drive_id="target_cascade", name="target.pdf")
    db.add_all([file1, file2, file3])
    db.commit()

    # Create relationships
    rel1 = FileRelationship(source_file_id=file1.id, target_file_id=file3.id, similarity_score=0.8)
    rel2 = FileRelationship(source_file_id=file2.id, target_file_id=file3.id, similarity_score=0.7)
    db.add_all([rel1, rel2])
    db.commit()

    # Verify relationships exist
    assert db.query(FileRelationship).count() == 2

    # Delete target file
    db.delete(file3)
    db.commit()

    # Verify relationships were cascade deleted
    assert db.query(FileRelationship).count() == 0
    # Source files should still exist
    assert db.query(File).count() == 2


def test_relationship_query_by_similarity(db: Session) -> None:
    """Test querying relationships by similarity score (uses index)."""
    file1 = File(google_drive_id="query_file1", name="doc1.pdf")
    file2 = File(google_drive_id="query_file2", name="doc2.pdf")
    file3 = File(google_drive_id="query_file3", name="doc3.pdf")
    db.add_all([file1, file2, file3])
    db.commit()

    # Create relationships with different scores
    rel1 = FileRelationship(source_file_id=file1.id, target_file_id=file2.id, similarity_score=0.9)
    rel2 = FileRelationship(source_file_id=file1.id, target_file_id=file3.id, similarity_score=0.5)
    db.add_all([rel1, rel2])
    db.commit()

    # Query high similarity relationships (> 0.7)
    high_similarity = db.query(FileRelationship).filter(
        FileRelationship.similarity_score > 0.7
    ).all()
    assert len(high_similarity) == 1
    assert high_similarity[0].similarity_score == 0.9

    # Query low similarity relationships (< 0.7)
    low_similarity = db.query(FileRelationship).filter(
        FileRelationship.similarity_score < 0.7
    ).all()
    assert len(low_similarity) == 1
    assert low_similarity[0].similarity_score == 0.5
