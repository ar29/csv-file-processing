"""
Pydantic schemas for request/response validation.
Defines the structure of API inputs and outputs.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class UploadResponse(BaseModel):
    """Response schema for file upload endpoint"""
    job_id: UUID
    status: str
    message: str
    filename: str
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    """Response schema for job status endpoint"""
    job_id: UUID
    status: str
    filename: str
    uploaded_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    processing_time_seconds: Optional[float] = None
    errors: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class UserRecord(BaseModel):
    """Schema for a single user record from CSV"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(..., pattern=r'^\d{10}$')
    age: int = Field(..., ge=1, le=150)
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        """Validates that name is not just whitespace"""
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    @validator('phone')
    def validate_phone(cls, v):
        """Validates Indian phone number format"""
        if not v.isdigit():
            raise ValueError('Phone must contain only digits')
        if len(v) != 10:
            raise ValueError('Phone must be 10 digits')
        return v


class HealthCheckResponse(BaseModel):
    """Response schema for health check endpoint"""
    status: str
    database: str
    rabbitmq: str
    temporal: str
    timestamp: datetime