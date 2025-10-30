"""
Configuration management for the CSV processing service.
Loads settings from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database settings
    database_url: str = "postgresql://postgres:postgres@localhost:5432/fileprocessing"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    
    # RabbitMQ settings
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_queue: str = "csv_processing"
    
    # Temporal settings
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "csv-processing-queue"
    
    # Application settings
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    max_file_size: int = 104857600  # 100MB
    upload_dir: str = "/tmp/uploads"
    log_level: str = "INFO"
    
    # Email settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@fileprocessing.com"
    
    # Security settings
    api_key: str = "your-secret-api-key"
    rate_limit: int = 100
    
    # CSV validation settings
    chunk_size: int = 1000  # rows to process at once
    max_retries: int = 5
    min_age: int = 1
    max_age: int = 150
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Using lru_cache ensures we only create one instance.
    """
    return Settings()