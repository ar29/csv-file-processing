# Quick Start Guide

Get the CSV File Processing Service running in 5 minutes!

## Prerequisites

- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+)
- 4GB+ RAM available
- 10GB+ disk space

## Installation

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/ar29/csv-file-processing
cd csv-file-processing
# Quick Start Guide

Get the CSV File Processing Service running in 5 minutes!

## Prerequisites

- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+)
- 4GB+ RAM available
- 10GB+ disk space

## Installation

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/ar29/csv-file-processing
cd csv-file-processing

# Run setup script
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create `.env` file from template
- Build Docker images
- Start all services
- Run database migrations

### 2. Verify Installation

```bash
# Check if all services are running
docker-compose ps

# Test API health
curl http://localhost:8000/health
```

You should see all services as "healthy" or "running".

## First Steps

### 1. Access the API Documentation

Open your browser and visit:
```
http://localhost:8000/docs
```

This provides interactive API documentation where you can test endpoints.

### 2. Upload Your First CSV File

Create a sample CSV file named `users.csv`:

```csv
name,email,phone,age
John Doe,john@example.com,9876543210,30
Jane Smith,jane@example.com,9876543211,25
Bob Wilson,bob@example.com,9876543212,35
```

Upload it using curl:

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@users.csv" \
  -F "email=your-email@example.com"
```

You'll get a response with a `job_id`:

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "message": "File uploaded successfully and queued for processing",
  "filename": "users.csv",
  "uploaded_at": "2025-10-29T10:30:00Z"
}
```

### 3. Check Processing Status

```bash
# Replace JOB_ID with the actual job ID from step 2
curl -X GET "http://localhost:8000/status/JOB_ID" \
  -H "X-API-Key: your-secret-api-key"
```

Response:

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "filename": "users.csv",
  "total_rows": 3,
  "valid_rows": 3,
  "invalid_rows": 0,
  "processing_time_seconds": 2.5
}
```

## Monitoring Dashboards

Access these URLs in your browser:

| Service | URL | Credentials |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | - |
| Temporal UI | http://localhost:8088 | - |
| RabbitMQ Management | http://localhost:15672 | guest/guest |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin/admin |

## Common Commands

```bash
# View logs
make logs

# View API logs only
make logs-api

# View worker logs only
make logs-worker

# Run tests
make test

# Restart services
make restart

# Stop services
make down

# Clean everything (including volumes)
make clean

# Scale workers
make scale-workers n=5
```

## Troubleshooting

### Services Not Starting

```bash
# Check Docker resources
docker system df

# Restart services
make restart

# Check logs for errors
make logs
```

### Database Connection Issues

```bash
# Check database status
docker-compose exec db pg_isready -U postgres

# Restart database
docker-compose restart db

# Re-run migrations
make migrate
```

### File Upload Fails

1. Check file size (max 100MB by default)
2. Verify CSV format has required columns
3. Check API key in `.env` file
4. Review API logs: `make logs-api`

### Worker Not Processing

```bash
# Check worker status
docker-compose ps worker

# View worker logs
make logs-worker

# Restart worker
docker-compose restart worker

# Scale up workers
make scale-workers n=3
```

## Next Steps

1. **Read the full documentation**: Check `README.md`
2. **Explore the API**: Visit http://localhost:8000/docs
3. **Monitor your jobs**: Check Temporal UI at http://localhost:8088
4. **Set up Grafana**: Create custom dashboards at http://localhost:3000
5. **Run tests**: `make test` to verify everything works
6. **Review code**: Explore the `app/` directory

## Configuration

Edit `.env` file to customise:

```bash
# Maximum file size (in bytes)
MAX_FILE_SIZE=104857600

# Number of rows to process at once
CHUNK_SIZE=1000

# API rate limit (requests per minute)
RATE_LIMIT=100

# Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

After changes, restart services:
```bash
make restart
```

## Example Workflow

Here's a complete example using Python:

```python
import requests
import time

API_URL = "http://localhost:8000"
API_KEY = "your-secret-api-key"

# Upload file
with open('users.csv', 'rb') as f:
    response = requests.post(
        f"{API_URL}/upload",
        headers={"X-API-Key": API_KEY},
        files={"file": f},
        data={"email": "notify@example.com"}
    )
    job_id = response.json()['job_id']
    print(f"Job ID: {job_id}")

# Poll for status
while True:
    response = requests.get(
        f"{API_URL}/status/{job_id}",
        headers={"X-API-Key": API_KEY}
    )
    status = response.json()
    
    print(f"Status: {status['status']}")
    
    if status['status'] in ['completed', 'failed']:
        print(f"Results: {status}")
        break
    
    time.sleep(2)
```

## Getting Help

- Check the logs: `make logs`
- Review documentation: `README.md`
- API reference: http://localhost:8000/docs
- Check GitHub issues: https://github.com/ar29/csv-file-processing/issues

## Stopping the Service

```bash
# Stop all services
make down

# Stop and remove volumes (clean slate)
make clean
```

---

**Congratulations!** You now have a fully functional CSV processing service running locally. 🎉

For production deployment, see `docs/DEPLOYMENT.md`.
# Run setup script
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create `.env` file from template
- Build Docker images
- Start all services
- Run database migrations

### 2. Verify Installation

```bash
# Check if all services are running
docker-compose ps

# Test API health
curl http://localhost:8000/health
```

You should see all services as "healthy" or "running".

## First Steps

### 1. Access the API Documentation

Open your browser and visit:
```
http://localhost:8000/docs
```

This provides interactive API documentation where you can test endpoints.

### 2. Upload Your First CSV File

Create a sample CSV file named `users.csv`:

```csv
name,email,phone,age
John Doe,john@example.com,9876543210,30
Jane Smith,jane@example.com,9876543211,25
Bob Wilson,bob@example.com,9876543212,35
```

Upload it using curl:

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@users.csv" \
  -F "email=your-email@example.com"
```

You'll get a response with a `job_id`:

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "message": "File uploaded successfully and queued for processing",
  "filename": "users.csv",
  "uploaded_at": "2025-10-29T10:30:00Z"
}
```

### 3. Check Processing Status

```bash
# Replace JOB_ID with the actual job ID from step 2
curl -X GET "http://localhost:8000/status/JOB_ID" \
  -H "X-API-Key: your-secret-api-key"
```

Response:

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "filename": "users.csv",
  "total_rows": 3,
  "valid_rows": 3,
  "invalid_rows": 0,
  "processing_time_seconds": 2.5
}
```

## Monitoring Dashboards

Access these URLs in your browser:

| Service | URL | Credentials |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | - |
| Temporal UI | http://localhost:8088 | - |
| RabbitMQ Management | http://localhost:15672 | guest/guest |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin/admin |

## Common Commands

```bash
# View logs
make logs

# View API logs only
make logs-api

# View worker logs only
make logs-worker

# Run tests
make test

# Restart services
make restart

# Stop services
make down

# Clean everything (including volumes)
make clean

# Scale workers
make scale-workers n=5
```

## Troubleshooting

### Services Not Starting

```bash
# Check Docker resources
docker system df

# Restart services
make restart

# Check logs for errors
make logs
```

### Database Connection Issues

```bash
# Check database status
docker-compose exec db pg_isready -U postgres

# Restart database
docker-compose restart db

# Re-run migrations
make migrate
```

### File Upload Fails

1. Check file size (max 100MB by default)
2. Verify CSV format has required columns
3. Check API key in `.env` file
4. Review API logs: `make logs-api`

### Worker Not Processing

```bash
# Check worker status
docker-compose ps worker

# View worker logs
make logs-worker

# Restart worker
docker-compose restart worker

# Scale up workers
make scale-workers n=3
```

## Next Steps

1. **Read the full documentation**: Check `README.md`
2. **Explore the API**: Visit http://localhost:8000/docs
3. **Monitor your jobs**: Check Temporal UI at http://localhost:8088
4. **Set up Grafana**: Create custom dashboards at http://localhost:3000
5. **Run tests**: `make test` to verify everything works
6. **Review code**: Explore the `app/` directory

## Configuration

Edit `.env` file to customise:

```bash
# Maximum file size (in bytes)
MAX_FILE_SIZE=104857600

# Number of rows to process at once
CHUNK_SIZE=1000

# API rate limit (requests per minute)
RATE_LIMIT=100

# Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

After changes, restart services:
```bash
make restart
```

## Example Workflow

Here's a complete example using Python:

```python
import requests
import time

API_URL = "http://localhost:8000"
API_KEY = "your-secret-api-key"

# Upload file
with open('users.csv', 'rb') as f:
    response = requests.post(
        f"{API_URL}/upload",
        headers={"X-API-Key": API_KEY},
        files={"file": f},
        data={"email": "notify@example.com"}
    )
    job_id = response.json()['job_id']
    print(f"Job ID: {job_id}")

# Poll for status
while True:
    response = requests.get(
        f"{API_URL}/status/{job_id}",
        headers={"X-API-Key": API_KEY}
    )
    status = response.json()
    
    print(f"Status: {status['status']}")
    
    if status['status'] in ['completed', 'failed']:
        print(f"Results: {status}")
        break
    
    time.sleep(2)
```

## Getting Help

- Check the logs: `make logs`
- Review documentation: `README.md`
- API reference: http://localhost:8000/docs
- Check GitHub issues: https://github.com/ar29/csv-file-processing/issues

## Stopping the Service

```bash
# Stop all services
make down

# Stop and remove volumes (clean slate)
make clean
```

---

**Congratulations!** You now have a fully functional CSV processing service running locally. 🎉

For production deployment, see `docs/DEPLOYMENT.md`.

┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │─────>│   FastAPI    │─────>│  RabbitMQ   │
└─────────────┘      │   REST API   │      │   Queue     │
                     └──────────────┘      └─────────────┘
                            │                      │
                            │                      ▼
                            │              ┌─────────────┐
                            │              │  Temporal   │
                            │              │   Worker    │
                            │              └─────────────┘
                            │                      │
                            ▼                      ▼
                     ┌──────────────┐      ┌─────────────┐
                     │  PostgreSQL  │<─────│ Processing  │
                     │   Database   │      │   Logic     │
                     └──────────────┘      └─────────────┘
                                                   │
                                                   ▼
                                          ┌─────────────┐
                                          │Notification │
                                          │  Service    │
                                          └─────────────┘