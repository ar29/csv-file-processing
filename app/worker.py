"""
Temporal worker that executes workflow activities.
Runs continuously to process jobs from the task queue.
"""
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from app.workflows.csv_workflow import CSVProcessingWorkflow
from app.workflows.activities import (
    update_job_status,
    validate_and_process_csv,
    send_notification,
    cleanup_file,
    record_metric
)
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def main():
    """
    Main worker function.
    Connects to Temporal server and starts processing activities.
    """
    logger.info("Starting Temporal worker...")
    
    try:
        # Connect to Temporal server
        client = await Client.connect(settings.temporal_host)
        logger.info(f"Connected to Temporal server at {settings.temporal_host}")
        
        # Create worker with workflow and activities
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[CSVProcessingWorkflow],
            activities=[
                update_job_status,
                validate_and_process_csv,
                send_notification,
                cleanup_file,
                record_metric
            ]
        )
        
        logger.info(f"Worker started on task queue: {settings.temporal_task_queue}")
        
        # Run worker
        await worker.run()
    
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())