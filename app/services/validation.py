"""
CSV validation service.
Validates CSV structure and individual records.
"""
import csv
import io
from typing import List, Dict, Tuple
from pydantic import ValidationError
from app.schemas import UserRecord
from app.utils.logger import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class CSVValidator:
    """Handles CSV file validation"""
    
    REQUIRED_COLUMNS = ['name', 'email', 'phone', 'age']
    
    def __init__(self):
        self.errors = []
    
    def validate_headers(self, headers: List[str]) -> bool:
        """
        Validates that CSV has all required columns.
        
        Args:
            headers: List of column names from CSV
        
        Returns:
            True if valid, False otherwise
        """
        if not headers:
            logger.error("CSV missing headers")
            return False
        # Strip whitespace and convert to lowercase
        normalized_headers = [h.strip().lower() for h in headers]
        
        missing_columns = []
        for required_col in self.REQUIRED_COLUMNS:
            if required_col not in normalized_headers:
                missing_columns.append(required_col)
        
        if missing_columns:
            error_msg = f"Missing required columns: {', '.join(missing_columns)}"
            self.errors.append(error_msg)
            logger.error(error_msg)
            return False
        
        return True
    
    def validate_row(self, row: Dict[str, str], row_number: int) -> Tuple[bool, UserRecord, str]:
        """
        Validates a single CSV row.
        
        Args:
            row: Dictionary containing row data
            row_number: Row number for error reporting
        
        Returns:
            Tuple of (is_valid, user_record, error_message)
        """
        try:
            # Normalize keys (strip whitespace, lowercase)
            normalized_row = {k.strip().lower(): v.strip() for k, v in row.items()}
            
            # Validate using Pydantic schema
            user_record = UserRecord(**normalized_row)
            return True, user_record, ""
        
        except ValidationError as e:
            # Extract validation errors
            error_messages = []
            for error in e.errors():
                field = error['loc'][0] if error['loc'] else 'unknown'
                msg = error['msg']
                error_messages.append(f"{field}: {msg}")
            
            error_str = f"Row {row_number}: " + ", ".join(error_messages)
            self.errors.append(error_str)
            logger.warning(f"Validation failed for row {row_number}: {error_messages}")
            return False, None, error_str
        
        except Exception as e:
            error_str = f"Row {row_number}: Unexpected error - {str(e)}"
            self.errors.append(error_str)
            logger.error(f"Unexpected error validating row {row_number}: {e}")
            return False, None, error_str
    
    def get_errors(self) -> List[str]:
        """Returns all validation errors"""
        return self.errors
    
    def clear_errors(self):
        """Clears error list"""
        self.errors = []


def validate_csv_structure(file_content: bytes) -> Tuple[bool, List[str]]:
    """
    Validates the basic structure of CSV file.
    
    Args:
        file_content: Raw CSV file content
    
    Returns:
        Tuple of (is_valid, errors)
    """
    validator = CSVValidator()
    
    try:
        # Decode bytes to string
        content = file_content.decode('utf-8')
        
        # Read first line to check headers
        reader = csv.DictReader(io.StringIO(content))
        headers = reader.fieldnames
        
        if not headers:
            return False, ["CSV file is empty or has no headers"]
        
        # Validate headers
        if not validator.validate_headers(headers):
            return False, validator.get_errors()
        
        return True, []
    
    except UnicodeDecodeError:
        return False, ["File encoding is not UTF-8"]
    except csv.Error as e:
        return False, [f"Invalid CSV format: {str(e)}"]
    except Exception as e:
        return False, [f"Error reading CSV: {str(e)}"]


def process_csv_in_chunks(file_path: str, chunk_size: int = None):
    """
    Generator that yields chunks of CSV rows for streaming processing.
    
    Args:
        file_path: Path to CSV file
        chunk_size: Number of rows per chunk
    
    Yields:
        Lists of validated user records with row numbers
    """
    if chunk_size is None:
        chunk_size = settings.chunk_size
    
    validator = CSVValidator()
    chunk = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Validate headers first
            if not validator.validate_headers(reader.fieldnames):
                raise ValueError(f"Invalid CSV headers: {validator.get_errors()}")
            
            for row_number, row in enumerate(reader, start=2):  # start=2 because header is row 1
                is_valid, user_record, error = validator.validate_row(row, row_number)
                
                chunk.append({
                    'row_number': row_number,
                    'is_valid': is_valid,
                    'record': user_record,
                    'error': error
                })
                
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
            
            # Yield remaining rows
            if chunk:
                yield chunk
    
    except Exception as e:
        logger.error(f"Error processing CSV in chunks: {e}")
        raise