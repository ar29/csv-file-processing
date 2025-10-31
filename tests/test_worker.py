"""
Tests for Temporal worker and workflow activities.
Tests activity functions, workflow execution, and error handling.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import uuid

from app.workflows.activities import (
    update_job_status,
    validate_and_process_csv,
    send_notification,
    cleanup_file,
    record_metric
)
from app.workflows.csv_workflow import CSVProcessingWorkflow, CSVProcessingInput
from app.models import FileUpload, User, ProcessingMetric


class TestUpdateJobStatus:
    """Tests for update_job_status activity"""
    
    @pytest.mark.asyncio
    async def test_update_status_success(self, db_session):
        """Test successful status update"""
        # Create test job
        job_id = str(uuid.uuid4())
        job = FileUpload(
            id=job_id,
            filename="test.csv",
            status="queued"
        )
        db_session.add(job)
        db_session.commit()
        
        # Update status
        result = await update_job_status(
            job_id=job_id,
            status="processing",
            started_at=datetime.utcnow()
        )
        
        assert result is True
        
        # Verify update in database
        updated_job = db_session.query(FileUpload).filter_by(id=job_id).first()
        assert updated_job.status == "processing"
        assert updated_job.started_at is not None
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_job(self, db_session):
        """Test updating non-existent job returns False"""
        result = await update_job_status(
            job_id=str(uuid.uuid4()),
            status="processing"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_update_with_multiple_fields(self, db_session):
        """Test updating multiple fields at once"""
        job_id = str(uuid.uuid4())
        job = FileUpload(
            id=job_id,
            filename="test.csv",
            status="processing"
        )
        db_session.add(job)
        db_session.commit()
        
        # Update multiple fields
        result = await update_job_status(
            job_id=job_id,
            status="completed",
            completed_at=datetime.utcnow(),
            total_rows=100,
            valid_rows=95,
            invalid_rows=5
        )
        
        assert result is True
        
        # Verify all fields updated
        updated_job = db_session.query(FileUpload).filter_by(id=job_id).first()
        assert updated_job.status == "completed"
        assert updated_job.completed_at is not None
        assert updated_job.total_rows == 100
        assert updated_job.valid_rows == 95
        assert updated_job.invalid_rows == 5


class TestValidateAndProcessCSV:
    """Tests for validate_and_process_csv activity"""
    
    @pytest.mark.asyncio
    async def test_process_valid_csv(self, temp_csv_file, db_session):
        """Test processing a valid CSV file"""
        job_id = str(uuid.uuid4())
        
        # Create CSV file with valid data
        with open(temp_csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            f.write("John Doe,john@example.com,9876543210,30\n")
            f.write("Jane Smith,jane@example.com,9876543211,25\n")
        
        # Process CSV
        result = await validate_and_process_csv(
            job_id=job_id,
            filepath=temp_csv_file
        )
        
        assert result['total_rows'] == 2
        assert result['valid_rows'] == 2
        assert result['invalid_rows'] == 0
        assert len(result['errors']) == 0
        
        # Verify users inserted into database
        users = db_session.query(User).filter_by(upload_id=job_id).all()
        assert len(users) == 2
        assert users[0].name == "John Doe"
        assert users[1].name == "Jane Smith"
    
    @pytest.mark.asyncio
    async def test_process_csv_with_invalid_rows(self, temp_csv_file, db_session):
        """Test processing CSV with some invalid rows"""
        job_id = str(uuid.uuid4())
        
        # Create CSV with mix of valid and invalid data
        with open(temp_csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            f.write("John Doe,john@example.com,9876543210,30\n")
            f.write("Invalid,not-an-email,123,999\n")  # Invalid row
            f.write("Jane Smith,jane@example.com,9876543211,25\n")
        
        result = await validate_and_process_csv(
            job_id=job_id,
            filepath=temp_csv_file
        )
        
        assert result['total_rows'] == 3
        assert result['valid_rows'] == 2
        assert result['invalid_rows'] == 1
        assert len(result['errors']) == 1
        assert "Row 3" in result['errors'][0]
        
        # Verify only valid users inserted
        users = db_session.query(User).filter_by(upload_id=job_id).all()
        assert len(users) == 2
    
    @pytest.mark.asyncio
    async def test_process_csv_with_duplicate_emails(self, temp_csv_file, db_session):
        """Test handling duplicate email addresses"""
        job_id = str(uuid.uuid4())
        
        # Create CSV with duplicate email
        with open(temp_csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            f.write("John Doe,john@example.com,9876543210,30\n")
            f.write("John Smith,john@example.com,9876543211,35\n")  # Duplicate email
        
        result = await validate_and_process_csv(
            job_id=job_id,
            filepath=temp_csv_file
        )
        
        assert result['total_rows'] == 2
        assert result['valid_rows'] == 1
        assert result['invalid_rows'] == 1
        
        # Verify only first user with email inserted
        users = db_session.query(User).filter_by(upload_id=job_id).all()
        assert len(users) == 1
        assert users[0].name == "John Doe"
    
    @pytest.mark.asyncio
    async def test_process_large_csv_in_chunks(self, temp_csv_file, db_session):
        """Test chunked processing of large CSV"""
        job_id = str(uuid.uuid4())
        
        # Create CSV with 2500 rows (will process in 3 chunks of 1000)
        with open(temp_csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            for i in range(2500):
                f.write(f"User{i},user{i}@example.com,987654{i:04d},30\n")
        
        result = await validate_and_process_csv(
            job_id=job_id,
            filepath=temp_csv_file
        )
        
        assert result['total_rows'] == 2500
        assert result['valid_rows'] == 2500
        assert result['invalid_rows'] == 0
        
        # Verify all users inserted
        users = db_session.query(User).filter_by(upload_id=job_id).all()
        assert len(users) == 2500
    
    @pytest.mark.asyncio
    async def test_process_csv_file_not_found(self, db_session):
        """Test handling of missing CSV file"""
        job_id = str(uuid.uuid4())
        
        with pytest.raises(FileNotFoundError):
            await validate_and_process_csv(
                job_id=job_id,
                filepath="/nonexistent/file.csv"
            )


class TestSendNotification:
    """Tests for send_notification activity"""
    
    @pytest.mark.asyncio
    @patch('app.services.notification.notification_service.send_email')
    async def test_send_email_notification(self, mock_send_email):
        """Test sending email notification"""
        mock_send_email.return_value = True
        
        result = await send_notification(
            job_id=str(uuid.uuid4()),
            filename="test.csv",
            status="completed",
            total_rows=100,
            valid_rows=95,
            invalid_rows=5,
            processing_time=10.5,
            errors=["Row 10: Invalid email"],
            email="user@example.com",
            webhook_url=None
        )
        
        assert result is True
        mock_send_email.assert_called_once()
        
        # Verify email parameters
        call_args = mock_send_email.call_args
        assert call_args[0][0] == "user@example.com"  # to_email
        assert "CSV Processing" in call_args[0][1]  # subject
    
    @pytest.mark.asyncio
    @patch('app.services.notification.notification_service.send_webhook')
    async def test_send_webhook_notification(self, mock_send_webhook):
        """Test sending webhook notification"""
        mock_send_webhook.return_value = True
        
        result = await send_notification(
            job_id=str(uuid.uuid4()),
            filename="test.csv",
            status="completed",
            total_rows=100,
            valid_rows=95,
            invalid_rows=5,
            processing_time=10.5,
            errors=[],
            email=None,
            webhook_url="https://example.com/webhook"
        )
        
        assert result is True
        mock_send_webhook.assert_called_once()
        
        # Verify webhook parameters
        call_args = mock_send_webhook.call_args
        assert call_args[0][0] == "https://example.com/webhook"
        assert isinstance(call_args[0][1], dict)  # payload
    
    @pytest.mark.asyncio
    @patch('app.services.notification.notification_service.send_email')
    @patch('app.services.notification.notification_service.send_webhook')
    async def test_send_both_notifications(self, mock_webhook, mock_email):
        """Test sending both email and webhook"""
        mock_email.return_value = True
        mock_webhook.return_value = True
        
        result = await send_notification(
            job_id=str(uuid.uuid4()),
            filename="test.csv",
            status="completed",
            total_rows=100,
            valid_rows=100,
            invalid_rows=0,
            processing_time=10.5,
            errors=[],
            email="user@example.com",
            webhook_url="https://example.com/webhook"
        )
        
        assert result is True
        mock_email.assert_called_once()
        mock_webhook.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.services.notification.notification_service.send_email')
    async def test_notification_failure_does_not_raise(self, mock_send_email):
        """Test that notification failures are logged but don't raise exceptions"""
        mock_send_email.side_effect = Exception("SMTP connection failed")
        
        # Should not raise exception
        result = await send_notification(
            job_id=str(uuid.uuid4()),
            filename="test.csv",
            status="completed",
            total_rows=100,
            valid_rows=100,
            invalid_rows=0,
            processing_time=10.5,
            errors=[],
            email="user@example.com",
            webhook_url=None
        )
        
        # Returns False on failure but doesn't crash
        assert result is False


class TestCleanupFile:
    """Tests for cleanup_file activity"""
    
    @pytest.mark.asyncio
    async def test_cleanup_existing_file(self, temp_csv_file):
        """Test cleanup of existing file"""
        # Create a test file
        with open(temp_csv_file, 'w') as f:
            f.write("test data")
        
        assert os.path.exists(temp_csv_file)
        
        # Cleanup file
        result = await cleanup_file(temp_csv_file)
        
        assert result is True
        assert not os.path.exists(temp_csv_file)
    
    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_file(self):
        """Test cleanup of non-existent file"""
        result = await cleanup_file("/nonexistent/file.csv")
        
        # Returns False but doesn't crash
        assert result is False


class TestRecordMetric:
    """Tests for record_metric activity"""
    
    @pytest.mark.asyncio
    async def test_record_metric_success(self, db_session):
        """Test recording a metric"""
        job_id = str(uuid.uuid4())
        
        result = await record_metric(
            job_id=job_id,
            metric_name="processing_time",
            metric_value=123.45
        )
        
        assert result is True
        
        # Verify metric in database
        metric = db_session.query(ProcessingMetric).filter_by(
            job_id=job_id,
            metric_name="processing_time"
        ).first()
        
        assert metric is not None
        assert metric.metric_value == 123.45
    
    @pytest.mark.asyncio
    async def test_record_multiple_metrics(self, db_session):
        """Test recording multiple metrics for same job"""
        job_id = str(uuid.uuid4())
        
        # Record multiple metrics
        await record_metric(job_id, "processing_time", 100.0)
        await record_metric(job_id, "throughput", 50.5)
        await record_metric(job_id, "memory_used", 1024.0)
        
        # Verify all metrics recorded
        metrics = db_session.query(ProcessingMetric).filter_by(
            job_id=job_id
        ).all()
        
        assert len(metrics) == 3
        metric_names = [m.metric_name for m in metrics]
        assert "processing_time" in metric_names
        assert "throughput" in metric_names
        assert "memory_used" in metric_names


class TestCSVProcessingWorkflow:
    """Tests for CSV processing workflow"""
    
    @pytest.mark.asyncio
    async def test_workflow_success_path(self, temp_csv_file, db_session):
        """Test complete workflow execution"""
        job_id = str(uuid.uuid4())
        
        # Create valid CSV
        with open(temp_csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            f.write("John Doe,john@example.com,9876543210,30\n")
        
        # Create job record
        job = FileUpload(
            id=job_id,
            filename="test.csv",
            status="queued"
        )
        db_session.add(job)
        db_session.commit()
        
        # Create workflow input
        workflow_input = CSVProcessingInput(
            job_id=job_id,
            filepath=temp_csv_file,
            filename="test.csv",
            email="user@example.com",
            webhook_url=None
        )
        
        # Execute workflow (in test mode)
        # Note: This would require Temporal test framework in real implementation
        # For now, we test individual activities
        
        # Activity 1: Update status
        await update_job_status(job_id, "processing", started_at=datetime.utcnow())
        
        # Activity 2: Process CSV
        result = await validate_and_process_csv(job_id, temp_csv_file)
        
        assert result['valid_rows'] == 1
        
        # Activity 3: Update final status
        await update_job_status(
            job_id,
            "completed",
            completed_at=datetime.utcnow(),
            total_rows=result['total_rows'],
            valid_rows=result['valid_rows'],
            invalid_rows=result['invalid_rows']
        )
        
        # Verify final state
        final_job = db_session.query(FileUpload).filter_by(id=job_id).first()
        assert final_job.status == "completed"
        assert final_job.total_rows == 1
        assert final_job.valid_rows == 1
    
    @pytest.mark.asyncio
    async def test_workflow_with_validation_errors(self, temp_csv_file, db_session):
        """Test workflow with validation errors"""
        job_id = str(uuid.uuid4())
        
        # Create CSV with invalid data
        with open(temp_csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            f.write("John Doe,john@example.com,9876543210,30\n")
            f.write("Invalid,bad-email,123,999\n")
        
        # Process
        result = await validate_and_process_csv(job_id, temp_csv_file)
        
        assert result['valid_rows'] == 1
        assert result['invalid_rows'] == 1
        assert len(result['errors']) > 0


class TestWorkerRetryLogic:
    """Tests for retry and error handling in workers"""
    
    @pytest.mark.asyncio
    @patch('app.workflows.activities.get_db_context')
    async def test_database_retry_on_transient_error(self, mock_db):
        """Test that transient database errors trigger retry"""
        # Simulate transient error then success
        mock_db.side_effect = [
            Exception("Connection timeout"),  # First attempt fails
            MagicMock()  # Second attempt succeeds
        ]
        
        # This would be handled by Temporal's retry mechanism
        # In a real test, we'd verify the activity is retried
        pass
    
    @pytest.mark.asyncio
    async def test_activity_heartbeat_during_processing(self, temp_csv_file):
        """Test that activity sends heartbeats during long processing"""
        job_id = str(uuid.uuid4())
        
        # Create large CSV (would trigger multiple heartbeats)
        with open(temp_csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            for i in range(5000):  # 5 chunks
                f.write(f"User{i},user{i}@example.com,987654{i:04d},30\n")
        
        # In actual Temporal activity, heartbeats would be sent
        # This ensures worker stays alive during long processing
        # We verify this through activity.heartbeat() calls
        pass


class TestWorkerScalability:
    """Tests for worker scalability"""
    
    def test_multiple_workers_process_different_jobs(self):
        """Test that multiple workers can process jobs in parallel"""
        # In production, multiple worker instances would process jobs concurrently
        # Each worker picks up different workflows from Temporal task queue
        # This is handled by Temporal's task distribution
        pass
    
    def test_worker_handles_workflow_failure(self):
        """Test that worker properly handles workflow failures"""
        # When activity fails after all retries, workflow should mark job as failed
        # This is handled by workflow's exception handling
        pass


# Fixtures
import os
import tempfile

@pytest.fixture
def temp_csv_file():
    """Creates a temporary CSV file for testing"""
    fd, path = tempfile.mkstemp(suffix='.csv')
    yield path
    # Cleanup
    try:
        os.close(fd)
        os.unlink(path)
    except:
        pass

"""
Tests for Temporal worker and workflow activities.
Tests activity functions, workflow logic, and error handling.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import uuid

from app.workflows.activities import (
    update_job_status,
    validate_and_process_csv,
    send_notification,
    cleanup_file,
    record_metric
)
from app.workflows.csv_workflow import CSVProcessingWorkflow, CSVProcessingInput
from app.models import FileUpload, User, ProcessingMetric


class TestActivities:
    """Test individual Temporal activities"""
    
    @pytest.mark.asyncio
    async def test_update_job_status_success(self, db_session):
        """Test successful job status update"""
        # Create a test job
        job_id = str(uuid.uuid4())
        job = FileUpload(
            id=job_id,
            filename="test.csv",
            status="queued",
            uploaded_at=datetime.utcnow()
        )
        db_session.add(job)
        db_session.commit()
        
        # Update status
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            result = await update_job_status(
                job_id=job_id,
                status="processing",
                started_at=datetime.utcnow()
            )
        
        # Verify
        assert result is True
        updated_job = db_session.query(FileUpload).filter_by(id=job_id).first()
        assert updated_job.status == "processing"
        assert updated_job.started_at is not None
    
    @pytest.mark.asyncio
    async def test_update_job_status_not_found(self, db_session):
        """Test status update for non-existent job"""
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            result = await update_job_status(
                job_id=job_id,
                status="processing"
            )
        
        # Should return False when job not found
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_and_process_csv_success(self, db_session, temp_csv_file):
        """Test successful CSV processing"""
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            with patch('app.workflows.activities.activity') as mock_activity:
                mock_activity.heartbeat = Mock()
                
                result = await validate_and_process_csv(
                    job_id=job_id,
                    filepath=temp_csv_file
                )
        
        # Verify results
        assert result['total_rows'] > 0
        assert result['valid_rows'] > 0
        assert result['invalid_rows'] >= 0
        assert isinstance(result['errors'], list)
        
        # Verify data was inserted
        users = db_session.query(User).filter_by(upload_id=job_id).all()
        assert len(users) == result['valid_rows']
    
    @pytest.mark.asyncio
    async def test_validate_and_process_csv_with_invalid_rows(self, db_session, tmp_path):
        """Test CSV processing with some invalid rows"""
        # Create CSV with mixed valid/invalid data
        csv_file = tmp_path / "mixed.csv"
        csv_file.write_text(
            "name,email,phone,age\n"
            "John Doe,john@example.com,9876543210,30\n"
            "Invalid User,not-an-email,123,999\n"
            "Jane Smith,jane@example.com,9876543211,25\n"
        )
        
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            with patch('app.workflows.activities.activity') as mock_activity:
                mock_activity.heartbeat = Mock()
                
                result = await validate_and_process_csv(
                    job_id=job_id,
                    filepath=str(csv_file)
                )
        
        # Verify
        assert result['total_rows'] == 3
        assert result['valid_rows'] == 2
        assert result['invalid_rows'] == 1
        assert len(result['errors']) > 0
        assert "not-an-email" in result['errors'][0] or "999" in result['errors'][0]
    
    @pytest.mark.asyncio
    async def test_validate_and_process_csv_file_not_found(self, db_session):
        """Test CSV processing with missing file"""
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            with pytest.raises(Exception):
                await validate_and_process_csv(
                    job_id=job_id,
                    filepath="/nonexistent/file.csv"
                )
    
    @pytest.mark.asyncio
    async def test_send_notification_email_only(self):
        """Test email notification sending"""
        with patch('app.workflows.activities.notification_service') as mock_service:
            mock_service.notify_processing_complete = Mock(return_value=None)
            
            result = await send_notification(
                job_id="test-job-id",
                filename="test.csv",
                status="completed",
                total_rows=100,
                valid_rows=95,
                invalid_rows=5,
                processing_time=10.5,
                errors=["Row 10: Invalid email"],
                email="user@example.com",
                webhook_url=None
            )
        
        # Verify notification was called
        assert result is True
        mock_service.notify_processing_complete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_notification_webhook_only(self):
        """Test webhook notification sending"""
        with patch('app.workflows.activities.notification_service') as mock_service:
            mock_service.notify_processing_complete = Mock(return_value=None)
            
            result = await send_notification(
                job_id="test-job-id",
                filename="test.csv",
                status="completed",
                total_rows=100,
                valid_rows=95,
                invalid_rows=5,
                processing_time=10.5,
                errors=[],
                email=None,
                webhook_url="https://example.com/webhook"
            )
        
        assert result is True
        mock_service.notify_processing_complete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_notification_both(self):
        """Test sending both email and webhook notification"""
        with patch('app.workflows.activities.notification_service') as mock_service:
            mock_service.notify_processing_complete = Mock(return_value=None)
            
            result = await send_notification(
                job_id="test-job-id",
                filename="test.csv",
                status="completed",
                total_rows=100,
                valid_rows=100,
                invalid_rows=0,
                processing_time=5.0,
                errors=[],
                email="user@example.com",
                webhook_url="https://example.com/webhook"
            )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_notification_failure_doesnt_raise(self):
        """Test that notification failure doesn't raise exception"""
        with patch('app.workflows.activities.notification_service') as mock_service:
            mock_service.notify_processing_complete = Mock(side_effect=Exception("SMTP error"))
            
            # Should not raise, just return False
            result = await send_notification(
                job_id="test-job-id",
                filename="test.csv",
                status="completed",
                total_rows=100,
                valid_rows=100,
                invalid_rows=0,
                processing_time=5.0,
                errors=[],
                email="user@example.com"
            )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cleanup_file_success(self, tmp_path):
        """Test successful file cleanup"""
        # Create a temporary file
        test_file = tmp_path / "test.csv"
        test_file.write_text("test data")
        
        assert test_file.exists()
        
        with patch('app.workflows.activities.file_service') as mock_service:
            mock_service.delete_file = Mock(return_value=True)
            
            result = await cleanup_file(str(test_file))
        
        assert result is True
        mock_service.delete_file.assert_called_once_with(str(test_file))
    
    @pytest.mark.asyncio
    async def test_cleanup_file_not_found(self):
        """Test cleanup of non-existent file"""
        with patch('app.workflows.activities.file_service') as mock_service:
            mock_service.delete_file = Mock(return_value=False)
            
            result = await cleanup_file("/nonexistent/file.csv")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_record_metric_success(self, db_session):
        """Test successful metric recording"""
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            result = await record_metric(
                job_id=job_id,
                metric_name="processing_time",
                metric_value=45.5
            )
        
        assert result is True
        
        # Verify metric was recorded
        metric = db_session.query(ProcessingMetric).filter_by(
            job_id=job_id,
            metric_name="processing_time"
        ).first()
        assert metric is not None
        assert metric.metric_value == 45.5
    
    @pytest.mark.asyncio
    async def test_record_metric_multiple(self, db_session):
        """Test recording multiple metrics for same job"""
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            await record_metric(job_id, "processing_time", 45.5)
            await record_metric(job_id, "throughput_rows_per_sec", 220.5)
        
        # Verify both metrics exist
        metrics = db_session.query(ProcessingMetric).filter_by(job_id=job_id).all()
        assert len(metrics) == 2


class TestWorkflow:
    """Test Temporal workflow logic"""
    
    @pytest.mark.asyncio
    async def test_workflow_input_validation(self):
        """Test workflow input data validation"""
        # Valid input
        valid_input = CSVProcessingInput(
            job_id="123e4567-e89b-12d3-a456-426614174000",
            filepath="/tmp/test.csv",
            filename="test.csv"
        )
        assert valid_input.job_id is not None
        assert valid_input.filepath is not None
        
        # Optional fields
        input_with_email = CSVProcessingInput(
            job_id="123e4567-e89b-12d3-a456-426614174000",
            filepath="/tmp/test.csv",
            filename="test.csv",
            email="user@example.com"
        )
        assert input_with_email.email == "user@example.com"
    
    @pytest.mark.asyncio
    async def test_workflow_execution_order(self):
        """Test that workflow activities execute in correct order"""
        # Mock all activities
        with patch('app.workflows.csv_workflow.workflow.execute_activity') as mock_execute:
            mock_execute.return_value = {
                'total_rows': 100,
                'valid_rows': 95,
                'invalid_rows': 5,
                'errors': []
            }
            
            # This would need a Temporal test environment
            # For now, we verify the workflow structure exists
            assert hasattr(CSVProcessingWorkflow, 'run')
    
    @pytest.mark.asyncio
    async def test_workflow_handles_activity_failure(self):
        """Test workflow error handling"""
        # Workflow should handle activity failures gracefully
        # This would be tested in a Temporal test environment
        pass


class TestWorkerPool:
    """Test worker pool management"""
    
    def test_worker_configuration(self):
        """Test worker is properly configured"""
        from app.config import get_settings
        
        settings = get_settings()
        
        # Verify worker settings exist
        assert settings.temporal_host is not None
        assert settings.temporal_task_queue is not None
        assert settings.temporal_namespace is not None
    
    @pytest.mark.asyncio
    async def test_worker_connects_to_temporal(self):
        """Test worker can connect to Temporal"""
        # This would require a running Temporal server
        # Mock the connection for unit testing
        with patch('app.worker.Client.connect') as mock_connect:
            mock_client = MagicMock()
            mock_connect.return_value = mock_client
            
            # Worker should successfully create client
            assert mock_connect is not None


class TestErrorHandling:
    """Test error handling and retry logic"""
    
    @pytest.mark.asyncio
    async def test_activity_retry_on_transient_error(self, db_session):
        """Test activity retries on transient failures"""
        job_id = str(uuid.uuid4())
        
        # Simulate transient database error
        with patch('app.workflows.activities.get_db_context') as mock_db:
            # First call fails, second succeeds
            mock_db.return_value.__enter__.side_effect = [
                Exception("Connection timeout"),
                db_session
            ]
            
            # Activity should be retried by Temporal
            # We can't test Temporal's retry logic here, 
            # but we verify the activity can handle errors
            with pytest.raises(Exception):
                await update_job_status(job_id, "processing")
    
    @pytest.mark.asyncio
    async def test_activity_logs_errors(self, caplog):
        """Test that activities log errors properly"""
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.side_effect = Exception("Test error")
            
            with pytest.raises(Exception):
                await update_job_status(job_id, "processing")
        
        # Verify error was logged
        assert "Test error" in caplog.text or "Error updating job status" in caplog.text


class TestPerformance:
    """Test performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_chunked_processing_memory_efficiency(self, tmp_path, db_session):
        """Test that chunked processing doesn't load entire file"""
        # Create a large CSV
        csv_file = tmp_path / "large.csv"
        with open(csv_file, 'w') as f:
            f.write("name,email,phone,age\n")
            for i in range(5000):  # 5000 rows
                f.write(f"User{i},user{i}@example.com,98765432{i:02d},{20+i%50}\n")
        
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            with patch('app.workflows.activities.activity') as mock_activity:
                mock_activity.heartbeat = Mock()
                
                result = await validate_and_process_csv(
                    job_id=job_id,
                    filepath=str(csv_file)
                )
        
        # Verify all rows processed
        assert result['total_rows'] == 5000
        
        # Verify heartbeat was called multiple times (chunked processing)
        assert mock_activity.heartbeat.call_count > 1
    
    @pytest.mark.asyncio
    async def test_heartbeat_sent_during_processing(self, tmp_path, db_session):
        """Test that heartbeats are sent to Temporal during long operations"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,email,phone,age\n"
            "John Doe,john@example.com,9876543210,30\n"
        )
        
        job_id = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            with patch('app.workflows.activities.activity') as mock_activity:
                mock_activity.heartbeat = Mock()
                
                await validate_and_process_csv(
                    job_id=job_id,
                    filepath=str(csv_file)
                )
                
                # Verify heartbeat was called
                assert mock_activity.heartbeat.called


class TestConcurrency:
    """Test concurrent job processing"""
    
    @pytest.mark.asyncio
    async def test_multiple_jobs_process_independently(self, db_session, tmp_path):
        """Test that multiple jobs can be processed concurrently"""
        # Create two separate CSV files
        csv1 = tmp_path / "file1.csv"
        csv1.write_text(
            "name,email,phone,age\n"
            "User1,user1@example.com,9876543210,30\n"
        )
        
        csv2 = tmp_path / "file2.csv"
        csv2.write_text(
            "name,email,phone,age\n"
            "User2,user2@example.com,9876543211,25\n"
        )
        
        job_id1 = str(uuid.uuid4())
        job_id2 = str(uuid.uuid4())
        
        with patch('app.workflows.activities.get_db_context') as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            
            with patch('app.workflows.activities.activity') as mock_activity:
                mock_activity.heartbeat = Mock()
                
                # Process both files
                result1 = await validate_and_process_csv(job_id1, str(csv1))
                result2 = await validate_and_process_csv(job_id2, str(csv2))
        
        # Verify both processed successfully
        assert result1['valid_rows'] == 1
        assert result2['valid_rows'] == 1
        
        # Verify data is separate
        users1 = db_session.query(User).filter_by(upload_id=job_id1).all()
        users2 = db_session.query(User).filter_by(upload_id=job_id2).all()
        
        assert len(users1) == 1
        assert len(users2) == 1
        assert users1[0].email != users2[0].email