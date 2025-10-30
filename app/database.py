"""
Database connection and session management.
Uses SQLAlchemy for ORM and connection pooling.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from app.config import get_settings

settings = get_settings()

# Create database engine with connection pooling
engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # verifies connections before using them
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Session:
    """
    Dependency function to get database session.
    Used in FastAPI endpoints for dependency injection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions.
    Used in workers and background tasks.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    Initialises database tables.
    Called on application startup.
    """
    from app.models import FileUpload, User, ProcessingMetric
    Base.metadata.create_all(bind=engine)