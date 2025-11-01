"""
Temporal activities for CSV processing workflow.
Each activity is a discrete unit of work that can be retried.
"""
from temporalio import activity
from datetime import datetime
from typing import Dict, List
from sqlalchemy.exc import IntegrityError
from app.database import get_db_context
from app.models import FileUpload, User, ProcessingMetric
from app.services.validation import process_csv_in_chunks
from app.services.notification import notification_service
from app.services.file_service import file_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


@activity.defn
async def update_job_status(job_id: str, status: str, extra_fields: dict = None) -> bool:
    try:
        with get_db_context() as db:
            job = db.query(FileUpload).filter(FileUpload.id == job_id).first()
            if job:
                job.status = status
                if extra_fields:
                    for key, value in extra_fields.items():
                        if hasattr(job, key):
                            setattr(job, key, value)
                db.commit()
                logger.info(f"Job {job_id} status updated to {status}")
                return True
            return False
    except Exception as e:
        logger.error(f"Error updating job status: {e}")
        raise



@activity.defn
async def validate_and_process_csv(job_id: str, filepath: str) -> Dict:
    """
    Validates and processes CSV file in chunks.
    
    Args:
        job_id: Job identifier
        filepath: Path to CSV file
    
    Returns:
        Dictionary with processing results
    """
    activity.logger.info(f"Starting CSV processing for job {job_id}")
    
    total_rows = 0
    valid_rows = 0
    invalid_rows = 0
    errors = []
    
    try:
        # Process CSV in chunks to handle large files
        for chunk in process_csv_in_chunks(filepath):
            with get_db_context() as db:
                for item in chunk:
                    total_rows += 1
                    
                    if item['is_valid']:
                        try:
                            # Create user record
                            user = User(
                                name=item['record'].name,
                                email=item['record'].email,
                                phone=item['record'].phone,
                                age=item['record'].age,
                                upload_id=job_id
                            )
                            db.add(user)
                            db.commit()
                            valid_rows += 1
                        
                        except IntegrityError:
                            # Handle duplicate email
                            db.rollback()
                            error_msg = f"Row {item['row_number']}: Duplicate email {item['record'].email}"
                            errors.append(error_msg)
                            invalid_rows += 1
                            logger.warning(error_msg)
                        
                        except Exception as e:
                            db.rollback()
                            error_msg = f"Row {item['row_number']}: Database error - {str(e)}"
                            errors.append(error_msg)
                            invalid_rows += 1
                            logger.error(error_msg)
                    else:
                        invalid_rows += 1
                        errors.append(item['error'])
            
            # Report progress (for Temporal heartbeat)
            def safe_heartbeat(msg):
                try:
                    activity.heartbeat(msg)
                except RuntimeError:
                    pass  # not running inside Temporal context
            safe_heartbeat(f"Processed {total_rows} rows")
        
        logger.info(f"CSV processing completed for job {job_id}: {valid_rows}/{total_rows} valid rows")
        
        return {
            'total_rows': total_rows,
            'valid_rows': valid_rows,
            'invalid_rows': invalid_rows,
            'errors': errors[:100]  # limit errors stored
        }
    
    except Exception as e:
        logger.error(f"Error processing CSV for job {job_id}: {e}")
        raise


@activity.defn
async def send_notification(
    job_id: str,
    filename: str,
    status: str,
    total_rows: int,
    valid_rows: int,
    invalid_rows: int,
    processing_time: float,
    errors: List[str],
    email: str = None,
    webhook_url: str = None
) -> bool:
    """
    Sends completion notification to user.
    
    Args:
        job_id: Job identifier
        filename: Processed filename
        status: Final status
        total_rows: Total rows processed
        valid_rows: Valid rows count
        invalid_rows: Invalid rows count
        processing_time: Processing duration
        errors: List of errors
        email: Optional email address
        webhook_url: Optional webhook URL
    
    Returns:
        True if notification sent successfully
    """
    try:
        await notification_service.notify_processing_complete(
            job_id=job_id,
            filename=filename,
            status=status,
            total_rows=total_rows,
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            processing_time=processing_time,
            errors=errors,
            email=email,
            webhook_url=webhook_url
        )
        logger.info(f"Notification sent for job {job_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending notification for job {job_id}: {e}")
        # Don't fail the workflow if notification fails
        return False


@activity.defn
async def cleanup_file(filepath: str) -> bool:
    """
    Cleans up processed file from disk.
    
    Args:
        filepath: Path to file
    
    Returns:
        True if deleted successfully
    """
    try:
        result = file_service.delete_file(filepath)
        logger.info(f"File cleanup: {filepath} - {'success' if result else 'not found'}")
        return result
    except Exception as e:
        logger.error(f"Error during file cleanup: {e}")
        return False


@activity.defn
async def record_metric(job_id: str, metric_name: str, metric_value: float) -> bool:
    """
    Records processing metric in database.
    
    Args:
        job_id: Job identifier
        metric_name: Name of metric
        metric_value: Metric value
    
    Returns:
        True if recorded successfully
    """
    try:
        with get_db_context() as db:
            metric = ProcessingMetric(
                job_id=job_id,
                metric_name=metric_name,
                metric_value=metric_value
            )
            db.add(metric)
            db.commit()
            return True
    except Exception as e:
        logger.error(f"Error recording metric: {e}")
        return False