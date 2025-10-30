"""
Helper utilities for common operations.
Contains reusable functions used across the application.
"""
import os
import hashlib
from datetime import datetime
from typing import Optional
from pathlib import Path


def generate_file_hash(filepath: str) -> str:
    """
    Generates SHA256 hash of a file for deduplication.
    
    Args:
        filepath: Path to the file
    
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def ensure_directory_exists(directory: str) -> None:
    """
    Creates directory if it doesn't exist.
    
    Args:
        directory: Path to directory
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


def clean_old_files(directory: str, max_age_hours: int = 24) -> int:
    """
    Removes files older than specified hours.
    
    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files in hours
    
    Returns:
        Number of files deleted
    """
    deleted_count = 0
    now = datetime.now().timestamp()
    max_age_seconds = max_age_hours * 3600
    
    for filepath in Path(directory).glob("*"):
        if filepath.is_file():
            file_age = now - filepath.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    filepath.unlink()
                    deleted_count += 1
                except Exception:
                    pass  # ignore errors during cleanup
    
    return deleted_count


def calculate_processing_time(started_at: Optional[datetime], 
                              completed_at: Optional[datetime]) -> Optional[float]:
    """
    Calculates processing time in seconds.
    
    Args:
        started_at: Start timestamp
        completed_at: Completion timestamp
    
    Returns:
        Processing time in seconds or None
    """
    if started_at and completed_at:
        return (completed_at - started_at).total_seconds()
    return None


def format_file_size(size_bytes: int) -> str:
    """
    Formats file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"