"""
SQLAlchemy models for database tables.
Defines the schema for file uploads, users, and processing metrics.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.database import Base


class FileUpload(Base):
    """
    Stores metadata about uploaded CSV files and their processing status.
    """
    __tablename__ = "file_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="queued")  # queued, processing, completed, failed
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Processing statistics
    total_rows = Column(Integer, default=0)
    valid_rows = Column(Integer, default=0)
    invalid_rows = Column(Integer, default=0)
    
    # Notification details
    email = Column(String(255), nullable=True)
    webhook_url = Column(String(500), nullable=True)
    
    # Error tracking
    errors = Column(JSON, nullable=True)  # list of error messages
    
    def __repr__(self):
        return f"<FileUpload {self.id} - {self.filename} - {self.status}>"


class User(Base):
    """
    Stores validated user records from CSV files.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(20), nullable=False)
    age = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    upload_id = Column(UUID(as_uuid=True), nullable=False)  # reference to file upload
    
    def __repr__(self):
        return f"<User {self.id} - {self.email}>"


class ProcessingMetric(Base):
    """
    Stores metrics about file processing for monitoring and analysis.
    """
    __tablename__ = "processing_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Metric {self.metric_name}={self.metric_value}>"