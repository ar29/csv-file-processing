# Docker Configuration

This directory contains Docker-related configuration files for the CSV File Processing Service.

## Directory Structure

```
docker/
├── README.md                    # This file
├── Dockerfile.api              # API service container
├── Dockerfile.worker           # Worker service container
└── temporal/                   # Temporal configuration
    └── development-sql.yaml    # Temporal dynamic config
```

## Dockerfiles

### Dockerfile.api

Builds the FastAPI application container.

**Base Image**: `python:3.11-slim`

**Features**:
- Minimal image size using slim variant
- System dependencies (gcc, postgresql-client)
- Python package installation with caching
- Non-root user execution (production-ready)
- Health check endpoint
- Multi-stage build support (can be enhanced)

**Build**:
```bash
docker build -f docker/Dockerfile.api -t csv-processor-api:latest .
```

**Run**:
```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  csv-processor-api:latest
```

**Size Optimisation**:
- Uses slim base image (~150MB vs 900MB for full Python image)
- Multi-stage build can reduce to ~100MB
- Layer caching for requirements.txt

### Dockerfile.worker

Builds the Temporal worker container.

**Base Image**: `python:3.11-slim`

**Features**:
- Same base as API for consistency
- Dedicated worker process
- Long-running process optimisations
- Resource limits (can be set in docker-compose)

**Build**:
```bash
docker build -f docker/Dockerfile.worker -t csv-processor-worker:latest .
```

**Run**:
```bash
docker run \
  -e DATABASE_URL=postgresql://... \
  -e TEMPORAL_HOST=temporal:7233 \
  csv-processor-worker:latest
```

**Scaling**:
```bash
# Run multiple workers
docker-compose up -d --scale worker=5
```

## Temporal Configuration

### development-sql.yaml

Contains Temporal's dynamic configuration for the development environment.

**Key Settings**:

1. **Workflow Limits**:
   - Max workflow ID length: 255 characters
   - History size: 50,000 events
   - Blob size: 2MB error, 256KB warning

2. **Task Queue Settings**:
   - Write partitions: 3
   - Read partitions: 3

3. **Retry Policies**:
   - Initial interval: 1s
   - Backoff coefficient: 2.0
   - Maximum interval: 100s
   - Unlimited attempts by default

4. **Retention**:
   - Default: 7 days
   - Can be overridden per namespace

**Customisation**:
Edit values in `development-sql.yaml` and restart Temporal:
```bash
docker-compose restart temporal
```

## Building Images

### Development Build

Quick build for local development:

```bash
# Build all images
docker-compose build

# Build specific service
docker-compose build api
docker-compose build worker

# Build with no cache
docker-compose build --no-cache
```

### Production Build

Optimised build for production:

```bash
# Multi-stage build (add to Dockerfile)
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Build
docker build -f docker/Dockerfile.api -t csv-processor-api:prod .
```

### Image Registry

Push to registry for deployment:

```bash
# Tag images
docker tag csv-processor-api:latest your-registry/csv-processor-api:v1.0.0
docker tag csv-processor-worker:latest your-registry/csv-processor-worker:v1.0.0

# Push images
docker push your-registry/csv-processor-api:v1.0.0
docker push your-registry/csv-processor-worker:v1.0.0
```

## Docker Compose Integration

The Dockerfiles are used by `docker-compose.yml` in the root directory:

```yaml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    # ... other config
  
  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    # ... other config
```

## Optimisation Tips

### 1. Layer Caching

Order Dockerfile commands from least to most frequently changed:

```dockerfile
# Good - requirements change less than code
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Bad - invalidates cache on any code change
COPY . .
RUN pip install -r requirements.txt
```

### 2. Multi-stage Builds

Reduce final image size:

```dockerfile
# Build stage
FROM python:3.11 as builder
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY app/ /app/
```

### 3. Use .dockerignore

Create `.dockerignore` in project root:

```
__pycache__
*.pyc
*.pyo
*.pyd
.git
.pytest_cache
*.egg-info
.coverage
htmlcov/
dist/
build/
*.log
.env
uploads/
```

### 4. Security Hardening

```dockerfile
# Run as non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Use specific versions
FROM python:3.11.5-slim

# Scan for vulnerabilities
# docker scan csv-processor-api:latest
```

## Environment Variables

Required environment variables for containers:

### API Container
```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
RABBITMQ_HOST=rabbitmq
TEMPORAL_HOST=temporal:7233
API_KEY=secret-key
SMTP_HOST=smtp.gmail.com
SMTP_USER=user@gmail.com
SMTP_PASSWORD=app-password
```

### Worker Container
```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
TEMPORAL_HOST=temporal:7233
RABBITMQ_HOST=rabbitmq
```

## Health Checks

### API Health Check

Built into Dockerfile.api:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

Check status:
```bash
docker inspect --format='{{.State.Health.Status}}' csv_processor_api
```

### Worker Health Check

Add to docker-compose.yml:

```yaml
worker:
  healthcheck:
    test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
    interval: 30s
    timeout: 10s
    retries: 3
```

## Resource Limits

Set in docker-compose.yml:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
  
  worker:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

## Logging

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker

# Last 100 lines
docker-compose logs --tail=100 api

# Since specific time
docker-compose logs --since 2025-10-29T10:00:00 api
```

### Log Configuration

Configure in docker-compose.yml:

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Check container status
docker-compose ps

# Inspect container
docker inspect csv_processor_api

# Enter container
docker-compose exec api /bin/bash
```

### Permission Issues

```bash
# Fix upload directory permissions
docker-compose exec api chown -R appuser:appuser /tmp/uploads

# Run as root temporarily
docker-compose exec -u root api /bin/bash
```

### Network Issues

```bash
# Check network
docker network ls
docker network inspect csv-file-processing_default

# Test connectivity
docker-compose exec api ping db
docker-compose exec api curl http://rabbitmq:15672
```

### Image Size Issues

```bash
# Check image size
docker images | grep csv-processor

# Analyse layers
docker history csv-processor-api:latest

# Remove unused images
docker image prune -a
```

## Production Deployment

### Best Practises

1. **Use specific versions**:
   ```dockerfile
   FROM python:3.11.5-slim
   ```

2. **Security scanning**:
   ```bash
   docker scan csv-processor-api:latest
   trivy image csv-processor-api:latest
   ```

3. **Image signing**:
   ```bash
   docker trust sign your-registry/csv-processor-api:v1.0.0
   ```

4. **Use secrets**:
   ```yaml
   services:
     api:
       secrets:
         - db_password
         - api_key
   
   secrets:
     db_password:
       external: true
     api_key:
       external: true
   ```

5. **Resource limits**:
   - Always set memory and CPU limits
   - Monitor resource usage

6. **Health checks**:
   - Implement for all services
   - Set appropriate timeouts

## Kubernetes Deployment

Convert to Kubernetes using kompose:

```bash
# Install kompose
curl -L https://github.com/kubernetes/kompose/releases/download/v1.28.0/kompose-linux-amd64 -o kompose
chmod +x kompose

# Convert
kompose convert -f docker-compose.yml

# Deploy
kubectl apply -f api-deployment.yaml
kubectl apply -f worker-deployment.yaml
```

Or create custom manifests in `k8s/` directory.

## Maintenance

### Regular Tasks

1. **Update base images**:
   ```bash
   docker pull python:3.11-slim
   docker-compose build --pull
   ```

2. **Clean up**:
   ```bash
   # Remove unused images
   docker image prune -a
   
   # Remove unused volumes
   docker volume prune
   
   # Full cleanup
   docker system prune -a --volumes
   ```

3. **Backup volumes**:
   ```bash
   docker run --rm -v postgres_data:/data -v $(pwd):/backup \
     alpine tar czf /backup/postgres_backup.tar.gz /data
   ```

## References

- [Docker Best Practises](https://docs.docker.com/develop/dev-best-practices/)
- [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Temporal Configuration](https://docs.temporal.io/references/configuration)