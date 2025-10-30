"""
Pytest configuration and shared fixtures.
"""
import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.config import get_settings

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh database session for each test.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Creates a test client with overridden database dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_csv_content():
    """Returns sample CSV content for testing"""
    return b"""name,email,phone,age
John Doe,john@example.com,9876543210,30
Jane Smith,jane@example.com,9876543211,25
Bob Wilson,bob@example.com,9876543212,35"""


@pytest.fixture
def invalid_csv_content():
    """Returns invalid CSV content for testing"""
    return b"""name,email,phone,age
John Doe,invalid-email,123,999
Jane Smith,jane@example.com,abc,25"""


@pytest.fixture
def api_headers():
    """Returns headers with valid API key"""
    settings = get_settings()
    return {"X-API-Key": settings.api_key}


@pytest.fixture
def temp_csv_file(tmp_path, sample_csv_content):
    """Creates a temporary CSV file for testing"""
    csv_file = tmp_path / "test.csv"
    csv_file.write_bytes(sample_csv_content)
    return str(csv_file)