"""
Temporal workflow for CSV processing.
Orchestrates the entire processing pipeline with fault tolerance.
"""
from temporalio import workflow
from datetime import timedelta
from dataclasses import dataclass
from typing import Optional
import time

# Import activities
with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        update_job_status,
        validate_and_process_csv,
        send_notification,
        cleanup_file,
        record_metric
    )


@dataclass
class CSVProcessingInput:
    """Input parameters for CSV processing workflow"""
    job_id: str
    filepath: str
    filename: str
    email: Optional[str] = None
    webhook_url: Optional[str] = None


@workflow.defn
class CSVProcessingWorkflow:
    """
    Main workflow for processing CSV files.
    Handles the complete lifecycle with automatic retries and fault tolerance.
    """
    
    @workflow.run
    async def run(self, input: CSVProcessingInput) -> dict:
        """
        Executes the CSV processing workflow.
        
        Args:
            input: CSVProcessingInput with job details
        
        Returns:
            Dictionary with processing results
        """
        workflow.logger.info(f"Starting workflow for job {input.job_id}")
        start_time = time.time()
        
        try:
            # Step 1: Update status to processing
            await workflow.execute_activity(
                update_job_status,
                args=[input.job_id, "processing", {"started_at": workflow.now()}],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0
                )
            )
            
            # Step 2: Process CSV file
            workflow.logger.info(f"Processing CSV file: {input.filepath}")
            result = await workflow.execute_activity(
                validate_and_process_csv,
                args=[input.job_id, input.filepath],
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=5,
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=1),
                    backoff_coefficient=2.0
                )
            )
            
            processing_time = time.time() - start_time
            
            # Step 3: Update status to completed
            await workflow.execute_activity(
                update_job_status,
                args=[
                    input.job_id,
                    "completed",
                    {
                        "completed_at": workflow.now(),
                        "total_rows": result['total_rows'],
                        "valid_rows": result['valid_rows'],
                        "invalid_rows": result['invalid_rows'],
                        "errors": result['errors']
                    }
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=workflow.RetryPolicy(maximum_attempts=3)
            )
            
            # Step 4: Record metrics
            await workflow.execute_activity(
                record_metric,
                args=[input.job_id, "processing_time", processing_time],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=workflow.RetryPolicy(maximum_attempts=2)
            )
            
            # Step 5: Send notification (best effort, don't fail workflow)
            try:
                await workflow.execute_activity(
                    send_notification,
                    args=[
                        input.job_id,
                        input.filename,
                        "completed",
                        result['total_rows'],
                        result['valid_rows'],
                        result['invalid_rows'],
                        processing_time,
                        result['errors'],
                        input.email,
                        input.webhook_url
                    ],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=workflow.RetryPolicy(
                        maximum_attempts=3,
                        initial_interval=timedelta(seconds=2)
                    )
                )
            except Exception as e:
                workflow.logger.warning(f"Notification failed but continuing: {e}")
            
            # Step 6: Cleanup file (best effort)
            try:
                await workflow.execute_activity(
                    cleanup_file,
                    args=[input.filepath],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=workflow.RetryPolicy(maximum_attempts=2)
                )
            except Exception as e:
                workflow.logger.warning(f"File cleanup failed: {e}")
            
            workflow.logger.info(f"Workflow completed successfully for job {input.job_id}")
            
            return {
                "status": "completed",
                "total_rows": result['total_rows'],
                "valid_rows": result['valid_rows'],
                "invalid_rows": result['invalid_rows'],
                "processing_time": processing_time
            }
        
        except Exception as e:
            workflow.logger.error(f"Workflow failed for job {input.job_id}: {e}")
            processing_time = time.time() - start_time
            
            # Update status to failed
            try:
                await workflow.execute_activity(
                    update_job_status,
                    args=[
                        input.job_id,
                        "failed",
                        {
                            "completed_at": workflow.now(),
                            "errors": [str(e)]
                        }
                    ],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=workflow.RetryPolicy(maximum_attempts=2)
                )
            except Exception as update_error:
                workflow.logger.error(f"Failed to update status: {update_error}")
            
            # Send failure notification
            try:
                await workflow.execute_activity(
                    send_notification,
                    args=[
                        input.job_id,
                        input.filename,
                        "failed",
                        0, 0, 0,
                        processing_time,
                        [str(e)],
                        input.email,
                        input.webhook_url
                    ],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=workflow.RetryPolicy(maximum_attempts=2)
                )
            except Exception as notif_error:
                workflow.logger.warning(f"Failed notification: {notif_error}")
            
            # Cleanup file
            try:
                await workflow.execute_activity(
                    cleanup_file,
                    args=[input.filepath],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=workflow.RetryPolicy(maximum_attempts=1)
                )
            except:
                pass
            
            return {
                "status": "failed",
                "error": str(e),
                "processing_time": processing_time
            }