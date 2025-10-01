"""Celery tasks."""
from app.core.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.test_task")
def test_task(x: int, y: int) -> int:
    """Test task for verification."""
    return x + y