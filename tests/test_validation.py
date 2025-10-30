"""
Tests for CSV validation logic.
"""
import pytest
from app.services.validation import validate_csv_structure, CSVValidator
from app.schemas import UserRecord
from pydantic import ValidationError


def test_validate_valid_csv(sample_csv_content):
    """Test validation passes for valid CSV"""
    is_valid, errors = validate_csv_structure(sample_csv_content)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_empty_csv():
    """Test validation fails for empty CSV"""
    is_valid, errors = validate_csv_structure(b"")
    assert is_valid is False
    assert len(errors) > 0


def test_validate_missing_headers():
    """Test validation fails when required headers are missing"""
    csv_content = b"name,email\nJohn,john@example.com"
    is_valid, errors = validate_csv_structure(csv_content)
    assert is_valid is False
    assert any("Missing required columns" in error for error in errors)


def test_validate_invalid_encoding():
    """Test validation fails for invalid encoding"""
    # Create bytes with invalid UTF-8
    csv_content = b"\xff\xfe"
    is_valid, errors = validate_csv_structure(csv_content)
    assert is_valid is False


def test_csv_validator_headers():
    """Test CSVValidator header validation"""
    validator = CSVValidator()
    
    # Valid headers
    valid_headers = ['name', 'email', 'phone', 'age']
    assert validator.validate_headers(valid_headers) is True
    
    # Missing headers
    invalid_headers = ['name', 'email']
    assert validator.validate_headers(invalid_headers) is False


def test_csv_validator_valid_row():
    """Test validation of valid row"""
    validator = CSVValidator()
    row = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'phone': '9876543210',
        'age': '30'
    }
    
    is_valid, record, error = validator.validate_row(row, 1)
    assert is_valid is True
    assert isinstance(record, UserRecord)
    assert record.name == 'John Doe'


def test_csv_validator_invalid_email():
    """Test validation fails for invalid email"""
    validator = CSVValidator()
    row = {
        'name': 'John Doe',
        'email': 'not-an-email',
        'phone': '9876543210',
        'age': '30'
    }
    
    is_valid, record, error = validator.validate_row(row, 1)
    assert is_valid is False
    assert 'email' in error.lower()


def test_csv_validator_invalid_phone():
    """Test validation fails for invalid phone"""
    validator = CSVValidator()
    row = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'phone': '123',  # too short
        'age': '30'
    }
    
    is_valid, record, error = validator.validate_row(row, 1)
    assert is_valid is False
    assert 'phone' in error.lower()


def test_csv_validator_invalid_age():
    """Test validation fails for invalid age"""
    validator = CSVValidator()
    row = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'phone': '9876543210',
        'age': '999'  # too high
    }
    
    is_valid, record, error = validator.validate_row(row, 1)
    assert is_valid is False
    assert 'age' in error.lower()


def test_user_record_schema():
    """Test UserRecord pydantic schema"""
    # Valid record
    valid_data = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'phone': '9876543210',
        'age': 30
    }
    record = UserRecord(**valid_data)
    assert record.name == 'John Doe'
    
    # Invalid email
    with pytest.raises(ValidationError):
        UserRecord(
            name='John',
            email='invalid',
            phone='9876543210',
            age=30
        )
    
    # Invalid age
    with pytest.raises(ValidationError):
        UserRecord(
            name='John',
            email='john@example.com',
            phone='9876543210',
            age=999
        )