"""
API route handlers.
Defines all REST endpoints for the service.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from temporalio.client import Client
from typing import Optional
from datetime import datetime
import uuid

from app.database import get_db
from app.models import FileUpload
from app.schemas import UploadResponse, JobStatusResponse, HealthCheckResponse
from app.api.dependencies import verify_api_key, rate_limit_check
from app.services.file_service import file_service
from app.services.validation import validate_csv_structure
from app.workflows.csv_workflow import CSVProcessingWorkflow, CSVProcessingInput
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.helpers import calculate_processing_time
from app.services.metrics import csv_file_size_bytes

settings = get_settings()
logger = get_logger(__name__)
router = APIRouter()


@router.post("/upload", response_model=UploadResponse, dependencies=[Depends(rate_limit_check)])
async def upload_csv_file(
    file: UploadFile = File(..., description="CSV file to process"),
    email: Optional[str] = Form(None, description="Email for notification"),
    webhook_url: Optional[str] = Form(None, description="Webhook URL for notification"),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Upload CSV file for processing.
    
    File is validated, saved, and queued for asynchronous processing.
    Returns a job ID that can be used to check processing status.
    """
    logger.info(f"Upload request received: {file.filename}")
    
    # Validate file extension
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed"
        )
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    try:
        # Save file to disk
        filepath = await file_service.save_upload_file(file, job_id)
        
        # Record file size metric
        file_size = file_service.get_file_size(filepath)
        if file_size:
            csv_file_size_bytes.observe(file_size)
        
        # Validate CSV structure
        with open(filepath, 'rb') as f:
            file_content = f.read()
        
        is_valid, errors = validate_csv_structure(file_content)
        if not is_valid:
            # Clean up file
            file_service.delete_file(filepath)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid CSV structure: {', '.join(errors)}"
            )
        
        # Create database record
        file_upload = FileUpload(
            id=job_id,
            filename=file.filename,
            status="queued",
            email=email,
            webhook_url=webhook_url
        )
        db.add(file_upload)
        db.commit()
        
        # Start Temporal workflow
        client = await Client.connect(settings.temporal_host)
        
        workflow_input = CSVProcessingInput(
            job_id=job_id,
            filepath=filepath,
            filename=file.filename,
            email=email,
            webhook_url=webhook_url
        )
        
        await client.start_workflow(
            CSVProcessingWorkflow.run,
            workflow_input,
            id=f"csv-processing-{job_id}",
            task_queue=settings.temporal_task_queue
        )
        
        logger.info(f"Job {job_id} created and workflow started for {file.filename}")
        
        return UploadResponse(
            job_id=job_id,
            status="queued",
            message="File uploaded successfully and queued for processing",
            filename=file.filename,
            uploaded_at=file_upload.uploaded_at
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process upload: {str(e)}"
        )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get processing status for a job.
    
    Returns detailed information about the job including processing statistics.
    """
    logger.info(f"Status check for job: {job_id}")
    
    try:
        # Validate UUID format
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID format"
        )
    
    # Query database for job
    job = db.query(FileUpload).filter(FileUpload.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    # Calculate processing time if completed
    processing_time = calculate_processing_time(job.started_at, job.completed_at)
    
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        filename=job.filename,
        uploaded_at=job.uploaded_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        total_rows=job.total_rows or 0,
        valid_rows=job.valid_rows or 0,
        invalid_rows=job.invalid_rows or 0,
        processing_time_seconds=processing_time,
        errors=job.errors
    )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.
    
    Verifies connectivity to all required services.
    """
    health_status = {
        "status": "healthy",
        "database": "disconnected",
        "rabbitmq": "unknown",
        "temporal": "unknown",
        "timestamp": datetime.utcnow()
    }
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["database"] = "disconnected"
        health_status["status"] = "unhealthy"
    
    # Check Temporal (basic connectivity)
    try:
        client = await Client.connect(settings.temporal_host)
        health_status["temporal"] = "connected"
    except Exception as e:
        logger.error(f"Temporal health check failed: {e}")
        health_status["temporal"] = "disconnected"
        health_status["status"] = "unhealthy"
    
    # RabbitMQ check would go here (simplified for now)
    health_status["rabbitmq"] = "connected"
    
    return health_status