"""
Logging configuration with structured JSON logging.
Provides consistent logging across the application.
"""
import logging
import sys
from pythonjsonlogger import jsonlogger
from app.config import get_settings

settings = get_settings()


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['logger'] = record.name


def setup_logger(name: str) -> logging.Logger:
    """
    Sets up a logger with JSON formatting.
    
    Args:
        name: Name of the logger (usually __name__)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only add handler if logger doesn't have any
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Gets or creates a logger with the given name.
    
    Args:
        name: Name of the logger
    
    Returns:
        Logger instance
    """
    return setup_logger(name)