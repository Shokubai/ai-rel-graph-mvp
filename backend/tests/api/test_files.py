"""Tests for file endpoints."""
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# TODO: Implement this test when we create the files endpoint
# def test_get_files_empty(client: TestClient):
#     """Test getting files when database is empty."""
#     response = client.get("/api/v1/files")
#     assert response.status_code == 200
#     assert response.json() == []