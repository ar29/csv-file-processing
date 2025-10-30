# Production Deployment Guide

This guide covers deploying the CSV File Processing Service to production environments.

## Pre-deployment Checklist

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Database backups configured
- [ ] Monitoring alerts set up
- [ ] SSL certificates ready
- [ ] Load balancer configured
- [ ] Scaling policies defined

## Environment Configuration

### Required Environment Variables

Update `.env` file with production values:

```bash
# Database - Use managed PostgreSQL service
DATABASE_URL=postgresql://user:password@prod-db.example.com:5432/fileprocessing
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=20

# RabbitMQ - Use managed service
RABBITMQ_HOST=rmq.example.com
RABBITMQ_PORT=5672
RABBITMQ_USER=production_user
RABBITMQ_PASSWORD=strong_password_here

# Temporal - Use managed Temporal Cloud or self-hosted cluster
TEMPORAL_HOST=temporal.example.com:7233
TEMPORAL_NAMESPACE=production

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
MAX_FILE_SIZE=104857600
LOG_LEVEL=INFO

# Email - Use production SMTP service
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_api_key

# Security
API_KEY=generate_strong_random_key_here
RATE_LIMIT=1000  # Adjust based on your needs
```

## Deployment Options

### Option 1: Docker Compose (Small Scale)

Suitable for small to medium workloads.

```bash
# Clone repository
git clone <repository-url>
cd csv-file-processing

# Set up environment
cp .env.example .env
# Edit .env with production values

# Deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Scale workers
docker-compose up -d --scale worker=5
```

### Option 2: Kubernetes (Large Scale)

For production-grade deployments with high availability.

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: csv-processor-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: csv-processor-api
  template:
    metadata:
      labels:
        app: csv-processor-api
    spec:
      containers:
      - name: api
        image: your-registry/csv-processor-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: csv-processor-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: csv-processor-worker
spec:
  replicas: 5
  selector:
    matchLabels:
      app: csv-processor-worker
  template:
    metadata:
      labels:
        app: csv-processor-worker
    spec:
      containers:
      - name: worker
        image: your-registry/csv-processor-worker:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: csv-processor-secrets
              key: database-url
        resources:
          requests:
            memory: "1Gi"
            cpu: "1000m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
```

## Database Setup

### PostgreSQL Configuration

```sql
-- Create production database
CREATE DATABASE fileprocessing;

-- Create dedicated user
CREATE USER csv_processor WITH ENCRYPTED PASSWORD 'strong_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE fileprocessing TO csv_processor;

-- Enable extensions if needed
\c fileprocessing
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Connection Pooling

Use PgBouncer for connection pooling:

```ini
[databases]
fileprocessing = host=postgres-server dbname=fileprocessing

[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'csv-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
```

### Alert Rules

```yaml
# alert_rules.yml
groups:
  - name: csv_processor_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(csv_processing_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/second"
      
      - alert: LargeQueueBacklog
        expr: rabbitmq_queue_depth > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Large queue backlog"
          description: "Queue depth is {{ $value }}"
      
      - alert: SlowProcessing
        expr: histogram_quantile(0.95, csv_processing_duration_seconds) > 300
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Slow processing detected"
          description: "95th percentile processing time is {{ $value }}s"
```

## Security Hardening

### 1. API Security

```python
# Update app/config.py for production
class Settings(BaseSettings):
    # ... other settings ...
    
    # Security
    allowed_origins: list = ["https://yourdomain.com"]
    api_key_header_name: str = "X-API-Key"
    enable_cors: bool = False  # Disable CORS in production
```

### 2. Network Security

- Use VPC/private subnets for internal services
- Enable TLS for all connections
- Use security groups to restrict access
- Implement WAF rules

### 3. Secrets Management

Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.):

```python
# Example with AWS Secrets Manager
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Load secrets
secrets = get_secret('csv-processor/production')
DATABASE_URL = secrets['database_url']
API_KEY = secrets['api_key']
```

## Backup Strategy

### Database Backups

```bash
# Automated daily backups
0 2 * * * pg_dump -h db-host -U csv_processor fileprocessing | gzip > /backups/fileprocessing_$(date +\%Y\%m\%d).sql.gz

# Retention policy: Keep 7 daily, 4 weekly, 3 monthly
find /backups -name "fileprocessing_*.sql.gz" -mtime +7 -delete
```

### File Backups

```bash
# Sync uploaded files to S3
aws s3 sync /tmp/uploads s3://your-bucket/uploads/ --delete

# Or use rsync to backup server
rsync -avz /tmp/uploads/ backup-server:/backups/uploads/
```

## Scaling Strategies

### Horizontal Scaling

```bash
# Scale API servers
kubectl scale deployment csv-processor-api --replicas=10

# Scale workers
kubectl scale deployment csv-processor-worker --replicas=20

# Or with Docker Compose
docker-compose up -d --scale api=5 --scale worker=10
```

### Auto-scaling (Kubernetes)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: csv-processor-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: csv-processor-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Performance Optimisation

### 1. Database Optimisation

```sql
-- Add indexes for common queries
CREATE INDEX idx_file_uploads_status ON file_uploads(status);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_upload_id ON users(upload_id);

-- Partition large tables
CREATE TABLE users_partitioned (
    LIKE users INCLUDING ALL
) PARTITION BY RANGE (created_at);

CREATE TABLE users_2025_01 PARTITION OF users_partitioned
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

### 2. Caching Strategy

```python
# Add Redis for caching job status
import redis

redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

def get_job_status_cached(job_id):
    # Try cache first
    cached = redis_client.get(f"job:{job_id}")
    if cached:
        return json.loads(cached)
    
    # Query database
    status = get_job_status_from_db(job_id)
    
    # Cache for 5 minutes
    redis_client.setex(f"job:{job_id}", 300, json.dumps(status))
    
    return status
```

## Troubleshooting

### Common Issues

1. **High memory usage**
   - Reduce `chunk_size` in config
   - Increase worker memory limits
   - Check for memory leaks

2. **Slow processing**
   - Scale workers horizontally
   - Optimise database queries
   - Check network latency

3. **Database connection exhaustion**
   - Increase connection pool size
   - Implement connection pooling (PgBouncer)
   - Check for connection leaks

### Logging

```bash
# View aggregated logs (ELK stack)
kubectl logs -l app=csv-processor-api -f

# Search specific error
kubectl logs -l app=csv-processor-worker | grep ERROR

# Export logs to file
kubectl logs deployment/csv-processor-api > api-logs.txt
```

## Rollback Procedure

```bash
# Kubernetes rollback
kubectl rollout undo deployment/csv-processor-api
kubectl rollout undo deployment/csv-processor-worker

# Docker Compose rollback
docker-compose pull  # Get previous version
docker-compose up -d

# Database rollback
alembic downgrade -1  # Rollback one migration
```

## Health Checks

```bash
# API health
curl https://api.yourdomain.com/health

# Detailed monitoring
curl https://api.yourdomain.com/metrics | grep csv_processing

# Database health
psql -h db-host -U csv_processor -c "SELECT 1;"
```

## Post-deployment Verification

1. **Smoke tests**
   ```bash
   # Upload test file
   curl -X POST https://api.yourdomain.com/upload \
     -H "X-API-Key: $API_KEY" \
     -F "file=@test.csv"
   ```

2. **Load testing**
   ```bash
   # Using Apache Bench
   ab -n 1000 -c 10 -H "X-API-Key: $API_KEY" \
     https://api.yourdomain.com/health
   ```

3. **Monitor metrics**
   - Check Grafana dashboards
   - Verify alert rules firing correctly
   - Review error rates

## Support

For production issues:
- Check Grafana dashboards
- Review application logs
- Check Temporal UI for workflow status
- Contact: devops@example.com
