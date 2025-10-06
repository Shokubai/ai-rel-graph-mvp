"""Tests for Cluster models."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.file import File
from app.models.cluster import Cluster, FileCluster


def test_create_cluster(db: Session) -> None:
    """Test creating a cluster."""
    cluster = Cluster(label="Machine Learning Papers")
    db.add(cluster)
    db.commit()
    db.refresh(cluster)

    assert cluster.id is not None
    assert cluster.label == "Machine Learning Papers"
    assert cluster.created_at is not None


def test_create_file_cluster_mapping(db: Session) -> None:
    """Test mapping files to clusters."""
    # Create files
    file1 = File(google_drive_id="cluster_file1", name="paper1.pdf")
    file2 = File(google_drive_id="cluster_file2", name="paper2.pdf")
    db.add_all([file1, file2])

    # Create cluster
    cluster = Cluster(label="AI Research")
    db.add(cluster)
    db.commit()

    # Map files to cluster
    fc1 = FileCluster(file_id=file1.id, cluster_id=cluster.id)
    fc2 = FileCluster(file_id=file2.id, cluster_id=cluster.id)
    db.add_all([fc1, fc2])
    db.commit()

    # Query files in cluster
    files_in_cluster = db.query(FileCluster).filter(
        FileCluster.cluster_id == cluster.id
    ).all()
    assert len(files_in_cluster) == 2


def test_file_cluster_duplicate_mapping(db: Session) -> None:
    """Test that duplicate file-cluster mappings are not allowed."""
    file = File(google_drive_id="dup_cluster_file", name="paper.pdf")
    cluster = Cluster(label="Duplicates")
    db.add_all([file, cluster])
    db.commit()

    # Create first mapping
    fc1 = FileCluster(file_id=file.id, cluster_id=cluster.id)
    db.add(fc1)
    db.commit()

    # Try to create duplicate mapping
    fc2 = FileCluster(file_id=file.id, cluster_id=cluster.id)
    db.add(fc2)

    with pytest.raises(IntegrityError):
        db.commit()


def test_file_cluster_cascade_delete_file(db: Session) -> None:
    """Test that cluster mappings are deleted when file is deleted."""
    file = File(google_drive_id="cascade_file", name="file.pdf")
    cluster = Cluster(label="Test Cluster")
    db.add_all([file, cluster])
    db.commit()

    # Create mapping
    fc = FileCluster(file_id=file.id, cluster_id=cluster.id)
    db.add(fc)
    db.commit()

    assert db.query(FileCluster).count() == 1

    # Delete file
    db.delete(file)
    db.commit()

    # Mapping should be cascade deleted
    assert db.query(FileCluster).count() == 0
    # Cluster should still exist
    assert db.query(Cluster).count() == 1


def test_file_cluster_cascade_delete_cluster(db: Session) -> None:
    """Test that cluster mappings are deleted when cluster is deleted."""
    file = File(google_drive_id="cascade_file2", name="file.pdf")
    cluster = Cluster(label="Test Cluster 2")
    db.add_all([file, cluster])
    db.commit()

    # Create mapping
    fc = FileCluster(file_id=file.id, cluster_id=cluster.id)
    db.add(fc)
    db.commit()

    assert db.query(FileCluster).count() == 1

    # Delete cluster
    db.delete(cluster)
    db.commit()

    # Mapping should be cascade deleted
    assert db.query(FileCluster).count() == 0
    # File should still exist
    assert db.query(File).count() == 1


def test_file_multiple_clusters(db: Session) -> None:
    """Test that a file can belong to multiple clusters."""
    file = File(google_drive_id="multi_cluster_file", name="research.pdf")
    cluster1 = Cluster(label="AI")
    cluster2 = Cluster(label="Machine Learning")
    cluster3 = Cluster(label="Neural Networks")
    db.add_all([file, cluster1, cluster2, cluster3])
    db.commit()

    # Map file to multiple clusters
    fc1 = FileCluster(file_id=file.id, cluster_id=cluster1.id)
    fc2 = FileCluster(file_id=file.id, cluster_id=cluster2.id)
    fc3 = FileCluster(file_id=file.id, cluster_id=cluster3.id)
    db.add_all([fc1, fc2, fc3])
    db.commit()

    # Query all clusters for this file
    clusters = db.query(FileCluster).filter(FileCluster.file_id == file.id).all()
    assert len(clusters) == 3


def test_cluster_multiple_files(db: Session) -> None:
    """Test that a cluster can contain multiple files."""
    cluster = Cluster(label="Research Papers")
    files = [
        File(google_drive_id=f"multi_file_{i}", name=f"paper{i}.pdf")
        for i in range(5)
    ]
    db.add(cluster)
    db.add_all(files)
    db.commit()

    # Map all files to cluster
    mappings = [FileCluster(file_id=f.id, cluster_id=cluster.id) for f in files]
    db.add_all(mappings)
    db.commit()

    # Query all files in cluster
    files_in_cluster = db.query(FileCluster).filter(
        FileCluster.cluster_id == cluster.id
    ).all()
    assert len(files_in_cluster) == 5
