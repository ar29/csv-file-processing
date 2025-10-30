"""
Prometheus metrics collection for monitoring.
Tracks key performance indicators and system health.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time

# Counters - things that only go up
csv_processing_total = Counter(
    'csv_processing_total',
    'Total number of CSV files processed',
    ['status']  # labels: completed, failed
)

csv_processing_errors_total = Counter(
    'csv_processing_errors_total',
    'Total number of processing errors',
    ['error_type']
)

csv_validation_failures_total = Counter(
    'csv_validation_failures_total',
    'Total number of validation failures',
    ['validation_type']
)

csv_rows_processed_total = Counter(
    'csv_rows_processed_total',
    'Total number of rows processed'
)

csv_rows_valid_total = Counter(
    'csv_rows_valid_total',
    'Total number of valid rows'
)

# Histograms - for measuring distributions
csv_processing_duration_seconds = Histogram(
    'csv_processing_duration_seconds',
    'Time taken to process CSV files',
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

csv_file_size_bytes = Histogram(
    'csv_file_size_bytes',
    'Size of uploaded CSV files in bytes',
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600]
)

# Gauges - things that can go up or down
rabbitmq_queue_depth = Gauge(
    'rabbitmq_queue_depth',
    'Current number of messages in RabbitMQ queue'
)

active_workers = Gauge(
    'active_workers',
    'Number of active worker processes'
)


def track_processing_time(func):
    """
    Decorator to track processing time of functions.
    Records duration in histogram metric.
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            csv_processing_duration_seconds.observe(time.time() - start_time)
            return result
        except Exception as e:
            csv_processing_duration_seconds.observe(time.time() - start_time)
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            csv_processing_duration_seconds.observe(time.time() - start_time)
            return result
        except Exception as e:
            csv_processing_duration_seconds.observe(time.time() - start_time)
            raise
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def record_processing_metrics(status: str, duration: float, total_rows: int, 
                              valid_rows: int, invalid_rows: int):
    """
    Records metrics after processing a file.
    
    Args:
        status: Processing status (completed/failed)
        duration: Processing duration in seconds
        total_rows: Total rows processed
        valid_rows: Number of valid rows
        invalid_rows: Number of invalid rows
    """
    csv_processing_total.labels(status=status).inc()
    csv_processing_duration_seconds.observe(duration)
    csv_rows_processed_total.inc(total_rows)
    csv_rows_valid_total.inc(valid_rows)
    
    if invalid_rows > 0:
        csv_validation_failures_total.labels(validation_type='row_validation').inc(invalid_rows)


def get_metrics():
    """
    Returns current metrics in Prometheus format.
    Used by /metrics endpoint.
    """
    return generate_latest()


def get_metrics_content_type():
    """Returns the content type for Prometheus metrics"""
    return CONTENT_TYPE_LATEST