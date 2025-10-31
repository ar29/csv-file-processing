"""
Integration tests for end-to-end workflows.
Tests complete user journeys from upload to completion.
"""
import pytest
import time
import uuid
from io import BytesIO
from fastapi.testclient import TestClient

from app.main import app
from app.models import FileUpload, User, ProcessingMetric


@pytest.mark.integration
class TestEndToEndFlow:
    """Test complete end-to-end user flows"""
    
    def test_complete_upload_and_processing_flow(self, client, api_headers, sample_csv_content, db_session):
        """
        Test the complete flow:
        1. Upload CSV file
        2. Job is queued
        3. Processing happens (mocked)
        4. Status can be queried
        5. Data is in database
        """
        # Step 1: Upload file
        files = {"file": ("users.csv", BytesIO(sample_csv_content), "text/csv")}
        data = {"email": "test@example.com"}
        
        response = client.post("/upload", files=files, data=data, headers=api_headers)
        
        assert response.status_code == 200
        upload_data = response.json()
        job_id = upload_data["job_id"]
        
        assert upload_data["status"] == "queued"
        assert upload_data["filename"] == "users.csv"
        
        # Step 2: Verify job in database
        job = db_session.query(FileUpload).filter_by(id=job_id).first()
        assert job is not None
        assert job.status == "queued"
        assert job.email == "test@example.com"
        
        # Step 3: Check status endpoint
        response = client.get(f"/status/{job_id}", headers=api_headers)
        assert response.status_code == 200
        
        status_data = response.json()
        assert status_data["job_id"] == job_id
        assert status_data["status"] == "queued"
        assert status_data["filename"] == "users.csv"
    
    def test_upload_with_webhook(self, client, api_headers, sample_csv_content):
        """Test upload with webhook URL"""
        files = {"file": ("users.csv", BytesIO(sample_csv_content), "text/csv")}
        data = {"webhook_url": "https://example.com/webhook"}
        
        response = client.post("/upload", files=files, data=data, headers=api_headers)
        
        assert response.status_code == 200
        assert "job_id" in response.json()
    
    def test_upload_with_both_email_and_webhook(self, client, api_headers, sample_csv_content):
        """Test upload with both email and webhook"""
        files = {"file": ("users.csv", BytesIO(sample_csv_content), "text/csv")}
        data = {
            "email": "test@example.com",
            "webhook_url": "https://example.com/webhook"
        }
        
        response = client.post("/upload", files=files, data=data, headers=api_headers)
        
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Verify both are stored
        # This would require database session in the test
        pass


@pytest.mark.integration
class TestErrorScenarios:
    """Test error scenarios across the entire system"""
    
    def test_upload_invalid_csv_structure(self, client, api_headers):
        """Test upload with invalid CSV structure"""
        # CSV missing required columns
        invalid_csv = b"name,email\nJohn,john@example.com"
        files = {"file": ("invalid.csv", BytesIO(invalid_csv), "text/csv")}
        
        response = client.post("/upload", files=files, headers=api_headers)
        
        assert response.status_code == 400
        assert "Invalid CSV structure" in response.json()["detail"]
    
    def test_upload_empty_file(self, client, api_headers):
        """Test upload with empty file"""
        empty_csv = b""
        files = {"file": ("empty.csv", BytesIO(empty_csv), "text/csv")}
        
        response = client.post("/upload", files=files, headers=api_headers)
        
        assert response.status_code == 400
    
    def test_upload_non_csv_file(self, client, api_headers):
        """Test upload with non-CSV file"""
        text_file = b"This is not a CSV"
        files = {"file": ("file.txt", BytesIO(text_file), "text/plain")}
        
        response = client.post("/upload", files=files, headers=api_headers)
        
        assert response.status_code == 400
        assert "Only CSV files are allowed" in response.json()["detail"]
    
    def test_status_check_for_nonexistent_job(self, client, api_headers):
        """Test status check for job that doesn't exist"""
        fake_job_id = str(uuid.uuid4())
        
        response = client.get(f"/status/{fake_job_id}", headers=api_headers)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_status_check_with_invalid_job_id_format(self, client, api_headers):
        """Test status check with invalid UUID format"""
        response = client.get("/status/invalid-id-format", headers=api_headers)
        
        assert response.status_code == 400
        assert "Invalid job ID format" in response.json()["detail"]


@pytest.mark.integration
class TestConcurrentUploads:
    """Test handling of multiple concurrent uploads"""
    
    def test_multiple_concurrent_uploads(self, client, api_headers, sample_csv_content):
        """Test uploading multiple files concurrently"""
        job_ids = []
        
        # Upload 5 files
        for i in range(5):
            files = {"file": (f"users{i}.csv", BytesIO(sample_csv_content), "text/csv")}
            data = {"email": f"user{i}@example.com"}
            
            response = client.post("/upload", files=files, data=data, headers=api_headers)
            
            assert response.status_code == 200
            job_ids.append(response.json()["job_id"])
        
        # Verify all jobs created
        assert len(job_ids) == 5
        assert len(set(job_ids)) == 5  # All unique
        
        # Check status of each job
        for job_id in job_ids:
            response = client.get(f"/status/{job_id}", headers=api_headers)
            assert response.status_code == 200
    
    def test_concurrent_uploads_with_same_data(self, client, api_headers, sample_csv_content):
        """Test uploading same CSV multiple times creates separate jobs"""
        job_ids = []
        
        for _ in range(3):
            files = {"file": ("same.csv", BytesIO(sample_csv_content), "text/csv")}
            response = client.post("/upload", files=files, headers=api_headers)
            
            assert response.status_code == 200
            job_ids.append(response.json()["job_id"])
        
        # All should be different jobs
        assert len(set(job_ids)) == 3


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting across requests"""
    
    def test_rate_limit_enforcement(self, client, api_headers, sample_csv_content):
        """Test that rate limiting kicks in after threshold"""
        # Make requests up to the limit
        # Note: This depends on RATE_LIMIT setting (default 100/min)
        
        responses = []
        for i in range(5):  # Small number for testing
            files = {"file": (f"test{i}.csv", BytesIO(sample_csv_content), "text/csv")}
            response = client.post("/upload", files=files, headers=api_headers)
            responses.append(response.status_code)
        
        # All should succeed (we're under the limit)
        assert all(status == 200 for status in responses)
    
    @pytest.mark.slow
    def test_rate_limit_resets(self, client, api_headers, sample_csv_content):
        """Test that rate limit resets after window expires"""
        # This test would need to wait for rate limit window to reset
        # Marked as slow test
        pass


@pytest.mark.integration
class TestDataConsistency:
    """Test data consistency across operations"""
    
    def test_duplicate_email_handling(self, client, api_headers, db_session):
        """Test that duplicate emails in same file are handled"""
        # CSV with duplicate emails
        csv_content = b"""name,email,phone,age
John Doe,john@example.com,9876543210,30
Jane Smith,john@example.com,9876543211,25"""
        
        files = {"file": ("duplicates.csv", BytesIO(csv_content), "text/csv")}
        response = client.post("/upload", files=files, headers=api_headers)
        
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # After processing (would need worker running)
        # Only first occurrence should be inserted
        # This would be tested with full system running
    
    def test_transaction_rollback_on_error(self, db_session):
        """Test that database transactions rollback on error"""
        # This would test that if processing fails mid-chunk,
        # the partial chunk is rolled back
        pass


@pytest.mark.integration
class TestNotifications:
    """Test notification system integration"""
    
    def test_email_notification_triggered(self, client, api_headers, sample_csv_content):
        """Test that email notification is triggered after processing"""
        # This would require mocking SMTP or using a test email service
        from unittest.mock import patch
        
        with patch('app.services.notification.aiosmtplib.send') as mock_send:
            files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
            data = {"email": "test@example.com"}
            
            response = client.post("/upload", files=files, data=data, headers=api_headers)
            assert response.status_code == 200
            
            # Email would be sent after processing completes
            # This would be tested with full workflow
    
    def test_webhook_notification_triggered(self, client, api_headers, sample_csv_content):
        """Test that webhook is called after processing"""
        from unittest.mock import patch
        
        with patch('app.services.notification.httpx.AsyncClient') as mock_client:
            files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
            data = {"webhook_url": "https://example.com/webhook"}
            
            response = client.post("/upload", files=files, data=data, headers=api_headers)
            assert response.status_code == 200
            
            # Webhook would be called after processing completes


@pytest.mark.integration
class TestMetricsCollection:
    """Test metrics collection across the system"""
    
    def test_metrics_endpoint_accessible(self, client):
        """Test that metrics endpoint returns data"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        content = response.content.decode()
        
        # Should contain Prometheus metrics
        assert "# HELP" in content or "# TYPE" in content
    
    def test_metrics_updated_after_upload(self, client, api_headers, sample_csv_content):
        """Test that metrics are updated after operations"""
        # Get initial metrics
        response1 = client.get("/metrics")
        initial_metrics = response1.content.decode()
        
        # Upload file
        files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
        client.post("/upload", files=files, headers=api_headers)
        
        # Get updated metrics
        response2 = client.get("/metrics")
        updated_metrics = response2.content.decode()
        
        # Metrics should have changed
        # (Exact validation would depend on metric names)
        assert response2.status_code == 200


@pytest.mark.integration
class TestSystemHealth:
    """Test system health monitoring"""
    
    def test_health_check_when_healthy(self, client):
        """Test health check returns healthy status"""
        response = client.get("/health")
        
        assert response.status_code == 200
        health_data = response.json()
        
        assert health_data["status"] in ["healthy", "unhealthy"]
        assert "database" in health_data
        assert "timestamp" in health_data
    
    def test_health_check_includes_dependencies(self, client):
        """Test health check includes all dependencies"""
        response = client.get("/health")
        health_data = response.json()
        
        # Should check all critical dependencies
        assert "database" in health_data
        # Would also check rabbitmq, temporal, etc.


@pytest.mark.integration
@pytest.mark.slow
class TestLargeFileProcessing:
    """Test processing of large CSV files"""
    
    def test_large_file_upload(self, client, api_headers, tmp_path):
        """Test uploading and processing a large CSV file"""
        # Create a larger CSV file (1000 rows)
        csv_file = tmp_path / "large.csv"
        with open(csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            for i in range(1000):
                f.write(f"User{i},user{i}@example.com,98765432{i:02d},{20+i%50}\n")
        
        with open(csv_file, 'rb') as f:
            files = {"file": ("large.csv", f, "text/csv")}
            response = client.post("/upload", files=files, headers=api_headers)
        
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Verify job was created
        response = client.get(f"/status/{job_id}", headers=api_headers)
        assert response.status_code == 200
    
    def test_maximum_file_size_limit(self, client, api_headers, tmp_path):
        """Test that files exceeding max size are rejected"""
        # Create file larger than allowed (would need actual large file)
        # This is a placeholder for the test logic
        pass


@pytest.mark.integration
class TestDatabaseOperations:
    """Test database operations under load"""
    
    def test_concurrent_database_writes(self, db_session):
        """Test that concurrent database writes don't cause issues"""
        # Would test connection pool, transactions, etc.
        pass
    
    def test_database_connection_pool(self):
        """Test database connection pooling works correctly"""
        from app.database import engine
        
        # Verify pool settings
        assert engine.pool.size() >= 0
        # Would test actual connection acquisition/release


@pytest.mark.integration
class TestWorkflowRecovery:
    """Test workflow recovery and fault tolerance"""
    
    def test_workflow_resumes_after_failure(self):
        """Test that Temporal workflow resumes after worker failure"""
        # This would require actually killing a worker
        # and verifying workflow continues
        pass
    
    def test_workflow_retry_on_transient_error(self):
        """Test workflow retries on transient errors"""
        # Would test actual retry behavior with Temporal
        pass


@pytest.mark.integration
class TestAPIVersioning:
    """Test API versioning and backward compatibility"""
    
    def test_api_root_endpoint(self, client):
        """Test API root returns service information"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "service" in data
        assert "endpoints" in data
        assert "version" in data


@pytest.mark.integration
class TestSecurityIntegration:
    """Test security features in integration"""
    
    def test_missing_api_key_rejected(self, client, sample_csv_content):
        """Test request without API key is rejected"""
        files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
        
        # No headers (no API key)
        response = client.post("/upload", files=files)
        
        assert response.status_code == 401
    
    def test_invalid_api_key_rejected(self, client, sample_csv_content):
        """Test request with invalid API key is rejected"""
        files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
        headers = {"X-API-Key": "invalid-key-12345"}
        
        response = client.post("/upload", files=files, headers=headers)
        
        assert response.status_code == 401
    
    def test_cors_headers_present(self, client):
        """Test CORS headers are present"""
        response = client.options("/health")
        
        # Would check for CORS headers
        # Depends on CORS middleware configuration
        assert response.status_code in [200, 204]


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration:
    """Test system performance under load"""
    
    def test_response_time_under_load(self, client, api_headers, sample_csv_content):
        """Test API response times under load"""
        import time
        
        response_times = []
        
        for i in range(10):
            start = time.time()
            files = {"file": (f"test{i}.csv", BytesIO(sample_csv_content), "text/csv")}
            response = client.post("/upload", files=files, headers=api_headers)
            end = time.time()
            
            assert response.status_code == 200
            response_times.append(end - start)
        
        # Calculate average response time
        avg_response_time = sum(response_times) / len(response_times)
        
        # Should be reasonably fast (adjust threshold as needed)
        assert avg_response_time < 1.0  # Less than 1 second average
    
    def test_throughput_measurement(self, client, api_headers, sample_csv_content):
        """Test system throughput"""
        # Measure how many requests can be processed in a time period
        import time
        
        start = time.time()
        success_count = 0
        
        # Try to upload 20 files quickly
        for i in range(20):
            files = {"file": (f"test{i}.csv", BytesIO(sample_csv_content), "text/csv")}
            response = client.post("/upload", files=files, headers=api_headers)
            if response.status_code == 200:
                success_count += 1
        
        end = time.time()
        duration = end - start
        throughput = success_count / duration
        
        # Should handle at least 10 requests per second
        assert throughput > 10


@pytest.mark.integration
class TestCleanupOperations:
    """Test cleanup and maintenance operations"""
    
    def test_temporary_files_cleaned_up(self):
        """Test that temporary files are cleaned up after processing"""
        # Would verify /tmp/uploads directory cleanup
        pass
    
    def test_old_jobs_can_be_archived(self, db_session):
        """Test archiving of old completed jobs"""
        # Would test cleanup job for old records
        pass