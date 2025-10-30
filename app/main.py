"""
FastAPI application entry point.
Initialises the API server with all routes and middleware.
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.api.routes import router
from app.database import init_db
from app.config import get_settings
from app.utils.logger import get_logger
from app.services.metrics import get_metrics, get_metrics_content_type

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler.
    Runs startup and shutdown logic.
    """
    # Startup
    logger.info("Starting CSV Processing Service...")
    
    # Initialise database
    try:
        init_db()
        logger.info("Database initialised successfully")
    except Exception as e:
        logger.error(f"Failed to initialise database: {e}")
        raise
    
    logger.info("Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down CSV Processing Service...")


# Create FastAPI application
app = FastAPI(
    title="CSV File Processing Service",
    description="Scalable service for processing CSV files with fault tolerance",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all HTTP requests.
    Adds correlation ID and measures request duration.
    """
    start_time = time.time()
    
    # Generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID", str(time.time()))
    
    # Log request
    logger.info(
        "Request started",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host
        }
    )
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log response
    logger.info(
        "Request completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2)
        }
    )
    
    # Add correlation ID to response
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(
        f"Unhandled exception: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error occurred",
            "path": request.url.path
        }
    )


# Include API routes
app.include_router(router, tags=["CSV Processing"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information"""
    return {
        "service": "CSV File Processing Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "upload": "/upload",
            "status": "/status/{job_id}",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus exposition format.
    """
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True
    )