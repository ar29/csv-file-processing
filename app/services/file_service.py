"""
File handling service.
Manages file uploads, storage, and cleanup.
"""
import os
import shutil
from pathlib import Path
from typing import Optional
import magic
from fastapi import UploadFile, HTTPException
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.helpers import ensure_directory_exists

settings = get_settings()
logger = get_logger(__name__)


class FileService:
    """Handles file operations"""
    
    ALLOWED_MIME_TYPES = [
        'text/csv',
        'text/plain',
        'application/csv',
        'application/vnd.ms-excel'
    ]
    
    def __init__(self):
        self.upload_dir = settings.upload_dir
        ensure_directory_exists(self.upload_dir)
    
    async def save_upload_file(self, upload_file: UploadFile, job_id: str) -> str:
        """
        Saves uploaded file to disk.
        
        Args:
            upload_file: FastAPI UploadFile object
            job_id: Unique job identifier
        
        Returns:
            Path to saved file
        
        Raises:
            HTTPException: If file validation fails
        """
        # Validate file size
        content = await upload_file.read()
        file_size = len(content)
        
        if file_size > settings.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {settings.max_file_size} bytes"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )
        
        # Validate MIME type using content sniffing
        mime_type = magic.from_buffer(content, mime=True)
        if mime_type not in self.ALLOWED_MIME_TYPES:
            logger.warning(f"Invalid MIME type: {mime_type} for file {upload_file.filename}")
            # Allow if filename ends with .csv (fallback)
            if not upload_file.filename.lower().endswith('.csv'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type. Expected CSV file, got {mime_type}"
                )
        
        # Generate unique filename
        file_extension = Path(upload_file.filename).suffix
        filename = f"{job_id}{file_extension}"
        filepath = os.path.join(self.upload_dir, filename)
        
        # Save file
        try:
            with open(filepath, 'wb') as f:
                f.write(content)
            
            logger.info(f"File saved: {filepath} ({file_size} bytes)")
            return filepath
        
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file: {str(e)}"
            )
    
    def delete_file(self, filepath: str) -> bool:
        """
        Deletes a file from disk.
        
        Args:
            filepath: Path to file
        
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"File deleted: {filepath}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {e}")
            return False
    
    def get_file_size(self, filepath: str) -> Optional[int]:
        """
        Gets file size in bytes.
        
        Args:
            filepath: Path to file
        
        Returns:
            File size in bytes or None if file doesn't exist
        """
        try:
            if os.path.exists(filepath):
                return os.path.getsize(filepath)
            return None
        except Exception as e:
            logger.error(f"Error getting file size for {filepath}: {e}")
            return None
    
    def file_exists(self, filepath: str) -> bool:
        """
        Checks if file exists.
        
        Args:
            filepath: Path to file
        
        Returns:
            True if file exists, False otherwise
        """
        return os.path.exists(filepath) and os.path.isfile(filepath)


# Singleton instance
file_service = FileService()