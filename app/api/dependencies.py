"""
API dependencies for FastAPI.
Handles authentication, rate limiting, and common validations.
"""
from fastapi import Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import time
from collections import defaultdict
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Simple in-memory rate limiter (for production, use Redis)
rate_limit_store = defaultdict(list)


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Verifies API key from request header.
    
    Args:
        x_api_key: API key from X-API-Key header
    
    Returns:
        Verified API key
    
    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required. Provide it via X-API-Key header"
        )
    
    if x_api_key != settings.api_key:
        logger.warning(f"Invalid API key attempted: {x_api_key[:10]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return x_api_key


async def rate_limit_check(request: Request) -> None:
    """
    Simple rate limiting based on IP address.
    
    Args:
        request: FastAPI request object
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = request.client.host
    current_time = time.time()
    
    # Clean old entries (older than 1 minute)
    rate_limit_store[client_ip] = [
        timestamp for timestamp in rate_limit_store[client_ip]
        if current_time - timestamp < 60
    ]
    
    # Check rate limit
    if len(rate_limit_store[client_ip]) >= settings.rate_limit:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {settings.rate_limit} requests per minute."
        )
    
    # Add current request
    rate_limit_store[client_ip].append(current_time)


def get_client_ip(request: Request) -> str:
    """
    Extracts client IP address from request.
    
    Args:
        request: FastAPI request object
    
    Returns:
        Client IP address
    """
    # Check for forwarded IP (when behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    return request.client.host