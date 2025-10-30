# API Usage Guide

This guide provides practical examples for using the CSV File Processing Service API.

## Prerequisites

- Service running on `http://localhost:8000`
- Valid API key (from `.env` file)

## Authentication

All API requests require an API key in the `X-API-Key` header:

```bash
X-API-Key: your-secret-api-key
```

## 1. Upload CSV File

Upload a CSV file for processing.

### Using cURL

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@/path/to/your/file.csv" \
  -F "email=your-email@example.com"
```

### Using Python

```python
import requests

url = "http://localhost:8000/upload"
headers = {"X-API-Key": "your-secret-api-key"}

files = {"file": open("users.csv", "rb")}
data = {"email": "notification@example.com"}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

### Response

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "message": "File uploaded successfully and queued for processing",
  "filename": "users.csv",
  "uploaded_at": "2025-10-29T10:30:00Z"
}
```

## 2. Check Job Status

Check the processing status of an uploaded file.

### Using cURL

```bash
curl -X GET "http://localhost:8000/status/123e4567-e89b-12d3-a456-426614174000" \
  -H "X-API-Key: your-secret-api-key"
```

### Using Python

```python
import requests

job_id = "123e4567-e89b-12d3-a456-426614174000"
url = f"http://localhost:8000/status/{job_id}"
headers = {"X-API-Key": "your-secret-api-key"}

response = requests.get(url, headers=headers)
print(response.json())
```

### Response (Processing)

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "filename": "users.csv",
  "uploaded_at": "2025-10-29T10:30:00Z",
  "started_at": "2025-10-29T10:30:05Z",
  "completed_at": null,
  "total_rows": 0,
  "valid_rows": 0,
  "invalid_rows": 0,
  "processing_time_seconds": null,
  "errors": null
}
```

### Response (Completed)

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "filename": "users.csv",
  "uploaded_at": "2025-10-29T10:30:00Z",
  "started_at": "2025-10-29T10:30:05Z",
  "completed_at": "2025-10-29T10:32:15Z",
  "total_rows": 10000,
  "valid_rows": 9850,
  "invalid_rows": 150,
  "processing_time_seconds": 130.5,
  "errors": [
    "Row 45: Invalid email format",
    "Row 102: Age out of range"
  ]
}
```

## 3. Upload with Webhook Notification

Receive notifications via webhook when processing completes.

### Using cURL

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@users.csv" \
  -F "webhook_url=https://your-app.com/webhook"
```

### Webhook Payload

Your webhook endpoint will receive:

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "filename": "users.csv",
  "status": "completed",
  "total_rows": 10000,
  "valid_rows": 9850,
  "invalid_rows": 150,
  "processing_time_seconds": 130.5,
  "errors": [
    "Row 45: Invalid email format"
  ]
}
```

## 4. Health Check

Check if the service is running properly.

### Using cURL

```bash
curl -X GET "http://localhost:8000/health"
```

### Response

```json
{
  "status": "healthy",
  "database": "connected",
  "rabbitmq": "connected",
  "temporal": "connected",
  "timestamp": "2025-10-29T10:30:00Z"
}
```

## CSV File Format

Your CSV file must have these columns:

- `name` - Full name (required, max 255 characters)
- `email` - Valid email address (required, unique)
- `phone` - 10-digit Indian phone number (required)
- `age` - Age between 1 and 150 (required)

### Example CSV

```csv
name,email,phone,age
John Doe,john@example.com,9876543210,30
Jane Smith,jane@example.com,9876543211,25
Bob Wilson,bob@example.com,9876543212,35
```

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid CSV structure: Missing required columns: email, phone"
}
```

### 401 Unauthorised

```json
{
  "detail": "API key is required. Provide it via X-API-Key header"
}
```

### 404 Not Found

```json
{
  "detail": "Job 123e4567-e89b-12d3-a456-426614174000 not found"
}
```

### 413 Payload Too Large

```json
{
  "detail": "File size exceeds maximum allowed size of 104857600 bytes"
}
```

### 429 Too Many Requests

```json
{
  "detail": "Rate limit exceeded. Maximum 100 requests per minute."
}
```

## Rate Limiting

- Default: 100 requests per minute per IP address
- Rate limit resets every minute
- Configurable via `RATE_LIMIT` environment variable

## Best Practises

1. **Always check job status** after uploading to monitor progress
2. **Implement retry logic** for transient failures
3. **Use webhooks** for long-running jobs instead of polling
4. **Validate CSV format** before uploading to catch errors early
5. **Handle rate limits** by implementing exponential backoff
6. **Store job IDs** for future reference and troubleshooting

## Complete Example Script

```python
#!/usr/bin/env python3
"""
Example script to upload CSV and monitor processing.
"""
import requests
import time
import sys

API_URL = "http://localhost:8000"
API_KEY = "your-secret-api-key"
HEADERS = {"X-API-Key": API_KEY}

def upload_file(filepath, email=None):
    """Upload CSV file"""
    url = f"{API_URL}/upload"
    
    with open(filepath, 'rb') as f:
        files = {'file': f}
        data = {}
        if email:
            data['email'] = email
        
        response = requests.post(url, headers=HEADERS, files=files, data=data)
        response.raise_for_status()
        return response.json()

def check_status(job_id):
    """Check job status"""
    url = f"{API_URL}/status/{job_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def main():
    if len(sys.argv) < 2:
        print("Usage: python example.py <csv_file> [email]")
        sys.exit(1)
    
    filepath = sys.argv[1]
    email = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Upload file
    print(f"Uploading {filepath}...")
    result = upload_file(filepath, email)
    job_id = result['job_id']
    print(f"Job created: {job_id}")
    
    # Monitor status
    while True:
        status = check_status(job_id)
        print(f"Status: {status['status']}")
        
        if status['status'] in ['completed', 'failed']:
            print(f"\nFinal results:")
            print(f"  Total rows: {status['total_rows']}")
            print(f"  Valid rows: {status['valid_rows']}")
            print(f"  Invalid rows: {status['invalid_rows']}")
            print(f"  Processing time: {status['processing_time_seconds']}s")
            
            if status.get('errors'):
                print(f"\nErrors:")
                for error in status['errors'][:5]:
                    print(f"  - {error}")
            
            break
        
        time.sleep(5)

if __name__ == '__main__':
    main()
```

## Interactive API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger documentation where you can test all endpoints directly from your browser.
