"""
Tests for API endpoints.
"""
import pytest
from io import BytesIO


def test_root_endpoint(client):
    """Test root endpoint returns service information"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CSV File Processing Service"
    assert "endpoints" in data


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data


def test_upload_without_api_key(client, sample_csv_content):
    """Test upload fails without API key"""
    files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
    response = client.post("/upload", files=files)
    assert response.status_code == 401
    assert "API key is required" in response.json()["detail"]


def test_upload_with_invalid_api_key(client, sample_csv_content):
    """Test upload fails with invalid API key"""
    files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
    headers = {"X-API-Key": "invalid-key"}
    response = client.post("/upload", files=files, headers=headers)
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_upload_non_csv_file(client, api_headers):
    """Test upload fails for non-CSV files"""
    files = {"file": ("test.txt", BytesIO(b"not a csv"), "text/plain")}
    response = client.post("/upload", files=files, headers=api_headers)
    assert response.status_code == 400
    assert "Only CSV files are allowed" in response.json()["detail"]


def test_upload_empty_file(client, api_headers):
    """Test upload fails for empty files"""
    files = {"file": ("test.csv", BytesIO(b""), "text/csv")}
    response = client.post("/upload", files=files, headers=api_headers)
    assert response.status_code == 400


def test_get_status_invalid_job_id(client, api_headers):
    """Test status check with invalid job ID format"""
    response = client.get("/status/invalid-id", headers=api_headers)
    assert response.status_code == 400
    assert "Invalid job ID format" in response.json()["detail"]


def test_get_status_nonexistent_job(client, api_headers):
    """Test status check for non-existent job"""
    import uuid
    job_id = str(uuid.uuid4())
    response = client.get(f"/status/{job_id}", headers=api_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_metrics_endpoint(client):
    """Test metrics endpoint returns Prometheus format"""
    response = client.get("/metrics")
    assert response.status_code == 200
    # Check for Prometheus metric format
    assert b"# HELP" in response.content or b"# TYPE" in response.content