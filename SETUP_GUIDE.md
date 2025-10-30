# Complete Setup Guide

Step-by-step guide to set up the CSV File Processing Service from scratch.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Service](#running-the-service)
5. [Verification](#verification)
6. [First Upload](#first-upload)
7. [Monitoring Setup](#monitoring-setup)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows with WSL2
- **RAM**: Minimum 4GB, Recommended 8GB
- **Disk Space**: Minimum 10GB free
- **CPU**: 2+ cores recommended

### Software Requirements

#### 1. Docker Installation

**Linux (Ubuntu/Debian)**:
```bash
# Update package index
sudo apt-get update

# Install dependencies
sudo apt-get install ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

**macOS**:
1. Download Docker Desktop from https://www.docker.com/products/docker-desktop
2. Install the .dmg file
3. Start Docker Desktop
4. Verify: `docker --version`

**Windows**:
1. Install WSL2: `wsl --install`
2. Download Docker Desktop for Windows
3. Install and enable WSL2 integration
4. Verify: `docker --version`

#### 2. Git Installation

```bash
# Linux
sudo apt-get install git

# macOS (if not installed)
brew install git

# Verify
git --version
```

#### 3. Make (Optional but Recommended)

```bash
# Linux
sudo apt-get install build-essential

# macOS
xcode-select --install

# Verify
make --version
```

## Installation

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-org/csv-file-processing.git
cd csv-file-processing

# Verify files
ls -la
```

Expected output:
```
README.md
docker-compose.yml
requirements.txt
Makefile
setup.sh
app/
docker/
monitoring/
tests/
...
```

### Step 2: Run Setup Script

```bash
# Make script executable
chmod +x setup.sh

# Run setup
./setup.sh
```

The setup script will:
1. ✓ Check Docker installation
2. ✓ Create `.env` file
3. ✓ Create necessary directories
4. ✓ Build Docker images (this takes 5-10 minutes)
5. ✓ Start all services
6. ✓ Run database migrations
7. ✓ Display service URLs

**Expected output**:
```
==========================================
CSV File Processing Service Setup
==========================================

✓ Docker and Docker Compose are installed
✓ .env file created
✓ Directories created
✓ Temporal configuration created

Building Docker images...
[+] Building 234.5s (23/23) FINISHED
...

Starting services...
[+] Running 9/9
 ✓ Network csv-file-processing_default  Created
 ✓ Volume "postgres_data"               Created
 ✓ Container csv_processor_db           Started
 ✓ Container csv_processor_rabbitmq     Started
 ✓ Container csv_processor_temporal     Started
 ✓ Container csv_processor_api          Started
 ✓ Container csv_processor_worker       Started
 ✓ Container csv_processor_prometheus   Started
 ✓ Container csv_processor_grafana      Started

==========================================
Setup Complete!
==========================================

Service URLs:
  • API:                 http://localhost:8000
  • API Documentation:   http://localhost:8000/docs
  • Temporal UI:         http://localhost:8088
  • RabbitMQ Management: http://localhost:15672 (guest/guest)
  • Prometheus:          http://localhost:9090
  • Grafana:             http://localhost:3000 (admin/admin)
```

## Configuration

### Step 3: Configure Environment Variables

Edit the `.env` file:

```bash
nano .env
# or
vim .env
# or use your preferred editor
```

**Critical Settings to Update**:

```bash
# 1. Change API Key (IMPORTANT for security)
API_KEY=generate-a-strong-random-key-here

# 2. Email Notifications (if needed)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use App Password, not regular password
SMTP_FROM=noreply@yourcompany.com

# 3. Adjust limits (optional)
MAX_FILE_SIZE=104857600  # 100MB
RATE_LIMIT=100          # requests per minute
CHUNK_SIZE=1000         # rows per chunk
```

**Getting Gmail App Password**:
1. Go to Google Account settings
2. Security → 2-Step Verification (must be enabled)
3. App passwords → Generate new password
4. Use this password in `SMTP_PASSWORD`

**Restart after changes**:
```bash
docker-compose restart api worker
```

## Running the Service

### Step 4: Verify All Services are Running

```bash
# Check service status
docker-compose ps
```

Expected output:
```
NAME                      STATUS              PORTS
csv_processor_api         Up 2 minutes        0.0.0.0:8000->8000/tcp
csv_processor_worker      Up 2 minutes        
csv_processor_db          Up 2 minutes (healthy)  0.0.0.0:5432->5432/tcp
csv_processor_rabbitmq    Up 2 minutes (healthy)  0.0.0.0:5672->5672/tcp, 0.0.0.0:15672->15672/tcp
csv_processor_temporal    Up 2 minutes        0.0.0.0:7233->7233/tcp
csv_processor_prometheus  Up 2 minutes        0.0.0.0:9090->9090/tcp
csv_processor_grafana     Up 2 minutes        0.0.0.0:3000->3000/tcp
```

**All services should show "Up" status.**

### Step 5: Check Logs

```bash
# View all logs
make logs

# View API logs only
make logs-api

# View worker logs
make logs-worker
```

Look for:
- ✓ "Application startup complete" (API)
- ✓ "Worker started on task queue" (Worker)
- ✓ No error messages

## Verification

### Step 6: Health Check

```bash
# Test health endpoint
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "rabbitmq": "connected",
  "temporal": "connected",
  "timestamp": "2025-10-29T10:30:00Z"
}
```

### Step 7: Access API Documentation

Open your browser and visit:
```
http://localhost:8000/docs
```

You should see the Swagger UI with all available endpoints.

### Step 8: Test Database Connection

```bash
# Connect to database
docker-compose exec db psql -U postgres -d fileprocessing

# Check tables
\dt

# Expected output:
#           List of relations
#  Schema |        Name         | Type  |  Owner   
# --------+---------------------+-------+----------
#  public | alembic_version     | table | postgres
#  public | file_uploads        | table | postgres
#  public | processing_metrics  | table | postgres
#  public | users               | table | postgres

# Exit
\q
```

## First Upload

### Step 9: Create Sample CSV

Create a file named `test-users.csv`:

```csv
name,email,phone,age
John Doe,john.doe@example.com,9876543210,30
Jane Smith,jane.smith@example.com,9876543211,25
Bob Wilson,bob.wilson@example.com,9876543212,35
Alice Brown,alice.brown@example.com,9876543213,28
```

### Step 10: Upload File

Using cURL:
```bash
curl -X POST "http://localhost:8000/upload" \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@test-users.csv" \
  -F "email=your-email@example.com"
```

Expected response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "message": "File uploaded successfully and queued for processing",
  "filename": "test-users.csv",
  "uploaded_at": "2025-10-29T10:30:00.123456"
}
```

**Save the `job_id` for the next step!**

### Step 11: Check Processing Status

```bash
# Replace JOB_ID with the actual job ID from step 10
curl -X GET "http://localhost:8000/status/JOB_ID" \
  -H "X-API-Key: your-secret-api-key"
```

Response (processing):
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "filename": "test-users.csv",
  ...
}
```

Response (completed):
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "filename": "test-users.csv",
  "total_rows": 4,
  "valid_rows": 4,
  "invalid_rows": 0,
  "processing_time_seconds": 2.5,
  "errors": null
}
```

### Step 12: Verify Data in Database

```bash
# Connect to database
docker-compose exec db psql -U postgres -d fileprocessing

# Check uploaded users
SELECT * FROM users;

# Expected output:
#  id |    name     |           email            |   phone    | age |         created_at         |              upload_id              
# ----+-------------+----------------------------+------------+-----+----------------------------+-------------------------------------
#   1 | John Doe    | john.doe@example.com       | 9876543210 |  30 | 2025-10-29 10:30:05.123456 | 123e4567-e89b-12d3-a456-426614174000
#   2 | Jane Smith  | jane.smith@example.com     | 9876543211 |  25 | 2025-10-29 10:30:05.234567 | 123e4567-e89b-12d3-a456-426614174000
#   3 | Bob Wilson  | bob.wilson@example.com     | 9876543212 |  35 | 2025-10-29 10:30:05.345678 | 123e4567-e89b-12d3-a456-426614174000
#   4 | Alice Brown | alice.brown@example.com    | 9876543213 |  28 | 2025-10-29 10:30:05.456789 | 123e4567-e89b-12d3-a456-426614174000

# Exit
\q
```

## Monitoring Setup

### Step 13: Access Temporal UI

Open browser: http://localhost:8088

You should see:
- Workflow executions
- Your processed job
- Execution history
- Activity details

### Step 14: Access Prometheus

Open browser: http://localhost:9090

Try these queries in the "Graph" tab:
```promql
# Total files processed
sum(csv_processing_total)

# Processing rate
rate(csv_processing_total[5m])

# Average processing time
rate(csv_processing_duration_seconds_sum[5m]) / rate(csv_processing_duration_seconds_count[5m])
```

### Step 15: Access Grafana

1. Open browser: http://localhost:3000
2. Login: admin / admin
3. Change password when prompted
4. Go to "Dashboards" → "CSV Processor Overview"

You should see:
- Total files processed
- Valid rows processed
- Processing errors
- Processing time graphs

### Step 16: Access RabbitMQ Management

1. Open browser: http://localhost:15672
2. Login: guest / guest
3. Check "Queues" tab
4. You should see `csv_processing` queue

## Troubleshooting

### Services Not Starting

**Problem**: Some services show as "Exited" or "Unhealthy"

**Solution**:
```bash
# Check logs
docker-compose logs [service-name]

# Restart services
docker-compose restart

# If still failing, rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database Connection Failed

**Problem**: API shows "database disconnected" in health check

**Solution**:
```bash
# Check database logs
docker-compose logs db

# Restart database
docker-compose restart db

# Wait 10 seconds and test again
sleep 10
curl http://localhost:8000/health
```

### File Upload Fails

**Problem**: Upload returns 401 or 400 error

**Solutions**:

1. **401 Unauthorized**:
   ```bash
   # Check API key in .env
   cat .env | grep API_KEY
   
   # Use correct API key in request
   curl -H "X-API-Key: correct-key-here" ...
   ```

2. **400 Bad Request**:
   - Check CSV format (must have: name, email, phone, age)
   - Ensure file size < 100MB
   - Verify file has `.csv` extension

3. **413 Payload Too Large**:
   ```bash
   # Increase max file size in .env
   MAX_FILE_SIZE=209715200  # 200MB
   
   # Restart API
   docker-compose restart api
   ```

### Worker Not Processing

**Problem**: Jobs stuck in "queued" status

**Solution**:
```bash
# Check worker logs
docker-compose logs worker

# Check Temporal connection
docker-compose logs temporal

# Restart worker
docker-compose restart worker

# Scale up workers if needed
docker-compose up -d --scale worker=3
```

### Port Already in Use

**Problem**: "port is already allocated" error

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000
# or
netstat -tulpn | grep 8000

# Kill the process
kill -9 [PID]

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

### Out of Disk Space

**Problem**: "no space left on device"

**Solution**:
```bash
# Check Docker disk usage
docker system df

# Clean up
docker system prune -a --volumes

# Remove old images
docker image prune -a

# Remove unused volumes
docker volume prune
```

### Permission Denied

**Problem**: Permission errors on uploads directory

**Solution**:
```bash
# Fix permissions
sudo chown -R $USER:$USER uploads/
chmod 755 uploads/

# Or inside container
docker-compose exec api chown -R appuser:appuser /tmp/uploads
```

## Next Steps

Now that your service is running:

1. **Read the documentation**:
   - `README.md` - Full documentation
   - `docs/API_USAGE.md` - API examples
   - `docs/DEPLOYMENT.md` - Production deployment

2. **Explore monitoring**:
   - Create custom Grafana dashboards
   - Set up alerts in Prometheus
   - Monitor Temporal workflows

3. **Run tests**:
   ```bash
   make test
   ```

4. **Scale the service**:
   ```bash
   # Scale workers
   make scale-workers n=5
   
   # Scale API (with load balancer)
   docker-compose up -d --scale api=3
   ```

5. **Customise configuration**:
   - Adjust chunk size for processing
   - Configure email notifications
   - Set up webhooks

## Getting Help

- **Check logs**: `make logs`
- **View documentation**: `README.md`
- **API reference**: http://localhost:8000/docs
- **Report issues**: Create GitHub issue with logs

## Quick Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
make logs

# Run tests
make test

# Scale workers
make scale-workers n=5

# Restart everything
make restart

# Clean everything
make clean
```

---

**Congratulations!** Your CSV File Processing Service is now fully set up and running! 🎉