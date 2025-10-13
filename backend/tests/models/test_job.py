"""Tests for ProcessingJob model."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.job import ProcessingJob


def test_create_processing_job(db: Session) -> None:
    """Test creating a processing job."""
    job = ProcessingJob(
        folder_id="test_folder_123",
        status="queued",
        total_files=10,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    assert job.id is not None
    assert job.folder_id == "test_folder_123"
    assert job.status == "queued"
    assert job.total_files == 10
    assert job.processed_files == 0
    assert job.progress_percentage == 0
    assert job.created_at is not None
    assert job.completed_at is None
    assert job.error_message is None


def test_processing_job_with_error(db: Session) -> None:
    """Test processing job with error message."""
    job = ProcessingJob(
        folder_id="error_folder",
        status="failed",
        error_message="Failed to connect to Google Drive API",
        total_files=5,
        processed_files=2,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    assert job.status == "failed"
    assert job.error_message == "Failed to connect to Google Drive API"
    assert job.processed_files == 2
    assert job.total_files == 5


def test_processing_job_progress_tracking(db: Session) -> None:
    """Test tracking job progress."""
    job = ProcessingJob(
        folder_id="progress_folder",
        status="running",
        total_files=100,
    )
    db.add(job)
    db.commit()

    # Simulate progress updates
    job.processed_files = 25
    job.progress_percentage = 25
    db.commit()

    assert job.processed_files == 25
    assert job.progress_percentage == 25

    # Update to 50%
    job.processed_files = 50
    job.progress_percentage = 50
    db.commit()

    assert job.processed_files == 50
    assert job.progress_percentage == 50


def test_processing_job_completion(db: Session) -> None:
    """Test completing a processing job."""
    job = ProcessingJob(
        folder_id="completion_folder",
        status="running",
        total_files=10,
        processed_files=9,
        progress_percentage=90,
    )
    db.add(job)
    db.commit()

    # Complete the job
    job.processed_files = 10
    job.progress_percentage = 100
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    assert job.status == "completed"
    assert job.processed_files == 10
    assert job.progress_percentage == 100
    assert job.completed_at is not None
    assert isinstance(job.completed_at, datetime)


def test_query_jobs_by_status(db: Session) -> None:
    """Test querying jobs by status (uses index)."""
    # Create jobs with different statuses
    jobs = [
        ProcessingJob(folder_id=f"folder_{i}", status=status)
        for i, status in enumerate(["queued", "running", "completed", "failed", "queued"])
    ]
    db.add_all(jobs)
    db.commit()

    # Query by status
    queued_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "queued").all()
    assert len(queued_jobs) == 2

    running_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "running").all()
    assert len(running_jobs) == 1

    completed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "completed").all()
    assert len(completed_jobs) == 1

    failed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "failed").all()
    assert len(failed_jobs) == 1


def test_processing_job_default_values(db: Session) -> None:
    """Test that default values are set correctly."""
    job = ProcessingJob(folder_id="defaults_folder")
    db.add(job)
    db.commit()
    db.refresh(job)

    assert job.status == "queued"
    assert job.progress_percentage == 0
    assert job.total_files == 0
    assert job.processed_files == 0
    assert job.error_message is None
    assert job.completed_at is None


def test_processing_job_long_error_message(db: Session) -> None:
    """Test storing long error messages."""
    long_error = "Error: " + "x" * 10000  # Very long error message
    job = ProcessingJob(
        folder_id="long_error_folder",
        status="failed",
        error_message=long_error,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    assert job.error_message == long_error
    assert len(job.error_message) > 10000


def test_multiple_jobs_same_folder(db: Session) -> None:
    """Test that multiple jobs can be created for the same folder."""
    # This might happen if a folder is reprocessed
    job1 = ProcessingJob(
        folder_id="same_folder",
        status="completed",
        completed_at=datetime.utcnow(),
    )
    job2 = ProcessingJob(
        folder_id="same_folder",
        status="queued",
    )
    db.add_all([job1, job2])
    db.commit()

    jobs = db.query(ProcessingJob).filter(ProcessingJob.folder_id == "same_folder").all()
    assert len(jobs) == 2
