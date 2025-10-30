### High-Level Architecture

```mermaid
graph TB
    Client[Client Applications] --> API[FastAPI REST API]
    API --> Auth[Authentication & Rate Limiting]
    Auth --> Upload[File Upload Handler]
    Upload --> Storage[File Storage /tmp/uploads]
    Upload --> DB[(PostgreSQL Database)]
    Upload --> Temporal[Temporal Server]
    
    Temporal --> Workers[Temporal Workers Pool]
    Workers --> Process[CSV Processing Activities]
    Process --> Validate[Validate & Parse CSV]
    Validate --> Insert[Insert Valid Records]
    Insert --> DB
    Process --> Notify[Send Notifications]
    Notify --> Email[Email Service SMTP]
    Notify --> Webhook[Webhook HTTP POST]
    
    Process --> Metrics[Record Metrics]
    Metrics --> Prometheus[Prometheus]
    Prometheus --> Grafana[Grafana Dashboards]
    
    Workers --> RabbitMQ[RabbitMQ Queue]
    RabbitMQ --> Workers
    
    style API fill:#4CAF50
    style Temporal fill:#9C27B0
    style DB fill:#2196F3
    style Prometheus fill:#FF9800
```

**Architecture Overview:**

The system uses a microservices architecture with clear separation of concerns:

- **API Layer**: FastAPI handles HTTP requests, authentication, and file uploads
- **Orchestration Layer**: Temporal manages workflow execution and fault tolerance
- **Processing Layer**: Workers execute CSV validation and database operations
- **Storage Layer**: PostgreSQL stores user data and job metadata
- **Messaging Layer**: RabbitMQ ensures reliable task distribution
- **Monitoring Layer**: Prometheus and Grafana provide observability

### Detailed Data Flow

#### Phase 1: File Upload & Validation

```
Client Application
    |
    | POST /upload (multipart/form-data)
    | - file: users.csv
    | - email: notify@example.com (optional)
    | - webhook_url: https://api.example.com/webhook (optional)
    v
+---------------------------------------------------+
|  API Server: Authentication & Validation          |
|  1. Verify X-API-Key header                       |
|  2. Check rate limit (100 req/min per IP)         |
|  3. Validate file extension (.csv)                |
|  4. Check file size (max 100MB)                   |
|  5. Verify MIME type                              |
+---------------------------------------------------+
    |
    | All checks passed
    v
+---------------------------------------------------+
|  API Server: File Processing                      |
|  1. Generate unique job_id (UUID)                 |
|  2. Save file: /tmp/uploads/{job_id}.csv          |
|  3. Validate CSV structure (headers present)      |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  Database: Create Job Record                      |
|  INSERT INTO file_uploads (                       |
|    id = job_id,                                   |
|    filename = "users.csv",                        |
|    status = "queued",                             |
|    uploaded_at = NOW()                            |
|  )                                                |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  API Server: Start Temporal Workflow              |
|  workflow_id = "csv-processing-{job_id}"          |
|  Submit to Temporal Server                        |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  API Server: Return Response                      |
|  HTTP 200 OK                                      |
|  {                                                |
|    "job_id": "123e4567-...",                      |
|    "status": "queued",                            |
|    "filename": "users.csv"                        |
|  }                                                |
+---------------------------------------------------+
```

#### Phase 2: Asynchronous Processing

```
Temporal Worker (picks up workflow from queue)
    |
    v
+---------------------------------------------------+
|  Activity 1: Update Status                        |
|  UPDATE file_uploads                              |
|  SET status = 'processing', started_at = NOW()    |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  Activity 2: Process CSV (Main Logic)             |
|                                                   |
|  Open CSV file: /tmp/uploads/{job_id}.csv         |
|                                                   |
|  FOR EACH CHUNK (1000 rows):                      |
|    |                                              |
|    FOR EACH ROW in chunk:                         |
|      |                                            |
|      +-- Validate name (not empty, max 255)       |
|      +-- Validate email (RFC 5322 format)         |
|      +-- Validate phone (10 digits)               |
|      +-- Validate age (1-150)                     |
|      |                                            |
|      IF valid:                                    |
|        INSERT INTO users (...)                    |
|        valid_rows++                               |
|      ELSE:                                        |
|        Log error                                  |
|        invalid_rows++                             |
|    END FOR                                        |
|    |                                              |
|    COMMIT transaction                             |
|    Send heartbeat (progress update)               |
|  END FOR                                          |
|                                                   |
|  Return: {total_rows, valid_rows, invalid_rows}   |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  Activity 3: Update Final Status                  |
|  UPDATE file_uploads                              |
|  SET status = 'completed',                        |
|      completed_at = NOW(),                        |
|      total_rows = X,                              |
|      valid_rows = Y,                              |
|      invalid_rows = Z                             |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  Activity 4: Record Metrics                       |
|  - Insert processing_time into metrics table      |
|  - Update Prometheus counters                     |
|  - Record success/failure counts                  |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  Activity 5: Send Notifications                   |
|  IF email provided:                               |
|    - Generate HTML email                          |
|    - Send via SMTP (with retry)                   |
|  IF webhook_url provided:                         |
|    - Prepare JSON payload                         |
|    - POST to webhook (with retry)                 |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  Activity 6: Cleanup                              |
|  - Delete file: /tmp/uploads/{job_id}.csv         |
|  - Free disk space                                |
+---------------------------------------------------+
    |
    v
Workflow Complete
```

#### Phase 3: Status Monitoring (Parallel)

```
Client (polling every 5 seconds)
    |
    | GET /status/{job_id}
    v
+---------------------------------------------------+
|  API Server: Authenticate & Query                 |
|  SELECT * FROM file_uploads WHERE id = job_id     |
+---------------------------------------------------+
    |
    v
+---------------------------------------------------+
|  API Server: Return Status                        |
|  {                                                |
|    "job_id": "123e4567-...",                      |
|    "status": "processing" | "completed",          |
|    "total_rows": 10000,                           |
|    "valid_rows": 9850,                            |
|    "invalid_rows": 150,                           |
|    "processing_time_seconds": 130.5               |
|  }                                                |
+---------------------------------------------------+
    |
    | IF status == "completed" or "failed"
    v
Client stops polling and displays results
```

### Data Flow Summary Table

| Phase | Duration | Key Actions | Database Operations | Network Calls |
|-------|----------|-------------|---------------------|---------------|
| **Upload** | ~500ms | File validation, save | 1 INSERT | 1 (client→API) |
| **Queue** | ~100ms | Workflow submission | - | 1 (API→Temporal) |
| **Processing** | ~2min | Parse, validate, insert | ~10,000 INSERTs | - |
| **Completion** | ~2s | Status update, metrics | 2 UPDATEs, 2 INSERTs | - |
| **Notification** | ~1s | Email/webhook | - | 1-2 (SMTP/HTTP) |
| **Cleanup** | ~100ms | File deletion | - | - |
| **Total** | **~2min** | Complete pipeline | **~10,005 writes** | **4-5 calls** |

*Note: Timings based on 10,000-row CSV file*

### Processing Flow Details

**Chunked Processing Strategy:**

```
File: users.csv (10,000 rows)
    |
    +-- Chunk 1 (rows 1-1000)    → Process → Insert to DB → Commit
    |
    +-- Chunk 2 (rows 1001-2000) → Process → Insert to DB → Commit
    |
    +-- Chunk 3 (rows 2001-3000) → Process → Insert to DB → Commit
    |
    ... (continue for remaining chunks)
    |
    +-- Chunk 10 (rows 9001-10000) → Process → Insert to DB → Commit

Benefits:
- Memory efficient (only 1000 rows in memory at once)
- Progress tracking via heartbeats
- Partial success (can recover from chunk 5 if chunk 4 fails)
- Better transaction management
```

**Error Handling with Retries:**

```
Activity Execution Timeline:

Attempt 1 (t=0s):     ------X  (Network timeout)
                        wait 2s
Attempt 2 (t=2s):     ------X  (DB connection failed)
                        wait 4s (exponential backoff)
Attempt 3 (t=6s):     ------X  (Temporary error)
                        wait 8s
Attempt 4 (t=14s):    ------✓  (Success!)

Total: 14 seconds with automatic retries
Temporal ensures the workflow continues despite transient failures
```

### Concurrent Request Handling

When multiple clients upload files simultaneously:

```
Client A    Client B    Client C
   |           |           |
   v           v           v
+-----------------------------+
|   Load Balancer (nginx)     |
+-----------------------------+
   |           |           |
   v           v           v
API-1       API-2       API-3
   |           |           |
   +------ Database -------+
   |           |           |
   +------ Temporal -------+
               |
        Task Queue
               |
   +-----------+-----------+
   |           |           |
   v           v           v
Worker-1    Worker-2    Worker-3
(job_a)     (job_b)     (job_c)

All workers process jobs in parallel
Database connection pooling prevents resource exhaustion
```

### Monitoring & Observability Flow

```
Application Events
    |
    +-- Counter: csv_processing_total{status="completed"}
    +-- Histogram: csv_processing_duration_seconds
    +-- Counter: csv_rows_valid_total
    +-- Gauge: rabbitmq_queue_depth
    |
    v
Prometheus Server
(scrapes /metrics every 15s)
    |
    v
Time-Series Database
(stores metrics for 15 days)
    |
    | PromQL queries
    v
Grafana Dashboards
(real-time visualization)
    |
    v
Operations Team
(monitoring and alerts)
```

### Security Layers

The system implements multiple security layers:

1. **Network Security**
   - TLS/HTTPS encryption
   - Firewall rules
   - VPC isolation

2. **Authentication**
   - API key validation
   - Rate limiting (100 req/min)
   - IP whitelisting (optional)

3. **Input Validation**
   - File type checking
   - Size limits (100MB)
   - CSV structure validation
   - SQL injection prevention

4. **Data Protection**
   - Database encryption at rest
   - Automatic file cleanup
   - PII handling compliance

5. **Audit & Monitoring**
   - All operations logged
   - Failed auth attempts tracked
   - Suspicious activity alerts

### Scalability Pattern

**Horizontal Scaling:**

```
Current Load: 100 files/hour
    |
    +-- 3 API instances (load balanced)
    +-- 5 Worker instances
    +-- PostgreSQL (with read replicas)
    +-- RabbitMQ (clustered)
    |
    v
Can handle: 1000+ files/hour

Scaling Strategy:
- Add more workers when queue depth > 100
- Scale API instances based on CPU/memory
- Use database read replicas for status queries
- Implement caching (Redis) for frequent queries
```

### Database Schema

**Tables Overview:**

#### 1. file_uploads

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key, unique job identifier |
| filename | VARCHAR(255) | Original uploaded filename |
| status | VARCHAR(50) | Job status: queued, processing, completed, failed |
| uploaded_at | TIMESTAMP | Upload timestamp |
| started_at | TIMESTAMP | Processing start time (nullable) |
| completed_at | TIMESTAMP | Processing completion time (nullable) |
| total_rows | INTEGER | Total rows in CSV |
| valid_rows | INTEGER | Successfully inserted rows |
| invalid_rows | INTEGER | Rows that failed validation |
| email | VARCHAR(255) | Notification email (nullable) |
| webhook_url | VARCHAR(500) | Webhook URL (nullable) |
| errors | JSON | Array of error messages |

#### 2. users

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key, auto-increment |
| name | VARCHAR(255) | User's full name |
| email | VARCHAR(255) | User's email (unique) |
| phone | VARCHAR(20) | 10-digit phone number |
| age | INTEGER | User's age (1-150) |
| created_at | TIMESTAMP | Record creation timestamp |
| upload_id | UUID | Foreign key to file_uploads |

#### 3. processing_metrics

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| job_id | UUID | Job identifier |
| metric_name | VARCHAR(100) | Metric name (e.g., processing_time) |
| metric_value | FLOAT | Metric value |
| timestamp | TIMESTAMP | Metric recording time |

### Key Design Decisions

**1. Why Temporal for Orchestration?**

- **Fault Tolerance**: Survives system crashes and restarts
- **Automatic Retries**: Built-in exponential backoff for transient failures
- **Durable Execution**: Workflow state persisted, can resume from any point
- **Observability**: Built-in UI for tracking workflow execution
- **Testability**: Workflows can be tested in isolation

**2. Why Chunk-based Processing?**

- **Memory Efficiency**: Only 1000 rows in memory at once (configurable)
- **Progress Tracking**: Send heartbeats after each chunk
- **Partial Success**: Can recover if processing fails mid-way
- **Transaction Management**: Smaller transactions reduce lock contention
- **Performance**: Better throughput with batched database operations

**3. Why PostgreSQL?**

- **ACID Compliance**: Strong consistency guarantees
- **JSON Support**: Native JSON column for flexible error storage
- **Scalability**: Proven at scale with read replicas
- **Extensions**: Rich ecosystem (uuid-ossp, pg_stat_statements)
- **Connection Pooling**: Efficient resource management

**4. Why RabbitMQ?**

- **Message Persistence**: Ensures no job loss
- **Acknowledgments**: Reliable message delivery
- **Dead Letter Queue**: Handle failed messages gracefully
- **Priority Queues**: Support urgent jobs if needed
- **Battle-tested**: Proven reliability at scale

### Performance Characteristics

**Throughput (per worker):**

| File Size | Rows | Processing Time | Throughput |
|-----------|------|-----------------|------------|
| Small | 1,000 | ~5 seconds | 200 rows/sec |
| Medium | 10,000 | ~2 minutes | 83 rows/sec |
| Large | 100,000 | ~20 minutes | 83 rows/sec |
| Extra Large | 1,000,000 | ~200 minutes | 83 rows/sec |

**Scaling Calculations:**

```
Goal: Process 10,000 files/hour (each with 10,000 rows)

Single worker throughput: 30 files/hour (2 min per file)
Workers needed: 10,000 / 30 = 334 workers

With safety margin (1.5x): 334 × 1.5 = 501 workers

Practical deployment:
- 500 worker instances
- Or 50 machines with 10 workers each
- Database: PostgreSQL with 20 read replicas
- RabbitMQ: 5-node cluster for redundancy
```

**Resource Requirements (per worker):**

- **CPU**: 0.5-1.0 cores
- **Memory**: 512MB-1GB
- **Disk**: Minimal (temporary files only)
- **Network**: Low bandwidth (< 1Mbps)
- **Database Connections**: 2-5 per worker

### Assumptions & Design Constraints

**File Format Assumptions:**

1. **CSV Structure**: Standard RFC 4180 compliant CSV
2. **Encoding**: UTF-8 text encoding
3. **Headers**: First row contains column names
4. **Columns**: Exactly 4 required columns (name, email, phone, age)
5. **Separators**: Comma-separated (not semicolon or tab)
6. **Line Endings**: Unix (\n) or Windows (\r\n) compatible

**Validation Rules:**

1. **Name**: 
   - Required, not empty after trimming whitespace
   - Maximum 255 characters
   - No special validation (allows unicode, symbols)

2. **Email**:
   - Must be valid RFC 5322 format
   - Case-insensitive uniqueness check
   - No disposable email detection

3. **Phone**:
   - Exactly 10 digits (Indian mobile format)
   - No international dialing codes
   - No formatting (spaces, dashes, parentheses removed)

4. **Age**:
   - Integer between 1 and 150 inclusive
   - No decimal values
   - No future birth dates validation

**Processing Constraints:**

1. **File Size**: Maximum 100MB (configurable via MAX_FILE_SIZE)
2. **Chunk Size**: 1000 rows per batch (configurable via CHUNK_SIZE)
3. **Timeout**: 30 minutes per file (Temporal workflow timeout)
4. **Retries**: Maximum 5 attempts with exponential backoff
5. **Rate Limit**: 100 requests per minute per IP address
6. **Concurrent Jobs**: Unlimited (limited only by worker capacity)

**Idempotency Guarantees:**

1. **Upload**: Each upload creates new job (no deduplication)
2. **Processing**: Duplicate emails within same file rejected
3. **Notifications**: Sent exactly once (best effort with retries)
4. **Workflows**: Same workflow ID prevents duplicate execution

**Data Retention:**

1. **Uploaded Files**: Deleted immediately after processing
2. **Job Metadata**: Retained indefinitely (can add cleanup job)
3. **User Records**: Retained indefinitely
4. **Metrics**: Retained for 7 days in database, 15 days in Prometheus
5. **Logs**: Retained based on log aggregation system (typically 7-30 days)

**Notification Behavior:**

1. **Email**:
   - Sent via SMTP (Gmail, SendGrid, etc.)
   - Includes job summary and first 10 errors
   - Retries: 3 attempts with 2-second delays
   - Failure: Logged but doesn't fail workflow

2. **Webhook**:
   - HTTP POST with JSON payload
   - 30-second timeout
   - Retries: 3 attempts with exponential backoff
   - Failure: Logged but doesn't fail workflow

**Error Handling Philosophy:**

1. **Transient Errors**: Retry automatically (network, DB timeouts)
2. **Permanent Errors**: Fail fast (invalid data, missing file)
3. **Partial Failures**: Continue processing (invalid rows don't stop job)
4. **Notification Failures**: Log but don't fail job (best effort)
5. **System Failures**: Temporal recovers and resumes automatically

### API Rate Limiting

**Rate Limit Implementation:**

- **Algorithm**: Sliding window counter
- **Window**: 60 seconds (rolling)
- **Limit**: 100 requests per IP address
- **Storage**: In-memory (can be moved to Redis for distributed setup)
- **Response**: HTTP 429 with Retry-After header

**Rate Limit Headers:**

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1698765490
```

**Bypassing Rate Limits:**

For trusted clients or internal services, rate limits can be increased via:
- Dedicated API keys with higher limits
- IP whitelisting
- OAuth2 scopes with different tiers

### Security Considerations

**Authentication:**

- **API Keys**: Simple but effective for service-to-service
- **Rotation**: Keys should be rotated periodically
- **Storage**: Never commit keys to version control
- **Transmission**: Always use HTTPS in production

**Data Protection:**

- **In Transit**: TLS 1.2+ for all connections
- **At Rest**: Database encryption via PostgreSQL
- **PII Handling**: Email and phone considered sensitive
- **GDPR Compliance**: User deletion endpoints should be added
- **Data Minimization**: Only collect necessary fields

**Vulnerability Prevention:**

- **SQL Injection**: Prevented via parameterized queries (SQLAlchemy ORM)
- **XSS**: Not applicable (no HTML rendering)
- **CSRF**: Not applicable (stateless API)
- **File Upload**: Extension validation, size limits, MIME type checking
- **DoS**: Rate limiting, file size limits, request timeouts

### Monitoring & Alerting Strategy

**Critical Alerts (immediate action required):**

1. **No Active Workers**: All workers down
2. **High Error Rate**: > 5% of jobs failing
3. **Database Connection Pool Exhausted**: No available connections
4. **Disk Space Critical**: < 10% free space
5. **Queue Depth Explosion**: > 10,000 pending jobs

**Warning Alerts (investigate soon):**

1. **Slow Processing**: 95th percentile > 5 minutes
2. **Queue Backlog**: > 1000 pending jobs for > 10 minutes
3. **Elevated Error Rate**: > 1% of jobs failing
4. **Memory Usage High**: > 80% of allocated memory
5. **Database Replication Lag**: > 5 seconds

**Info Alerts (good to know):**

1. **Scaling Event**: Workers scaled up/down
2. **Large File Uploaded**: File > 50MB
3. **High Volume**: > 1000 files/hour
4. **Database Backup Completed**: Daily backup success

### Operational Runbook

**Common Operations:**

1. **Scale Workers Up**:
   ```bash
   docker-compose up -d --scale worker=10
   # or
   kubectl scale deployment csv-processor-worker --replicas=10
   ```

2. **Check System Health**:
   ```bash
   curl http://localhost:8000/health
   docker-compose ps
   ```

3. **View Worker Logs**:
   ```bash
   docker-compose logs -f worker --tail=100
   ```

4. **Query Job Status in Database**:
   ```sql
   SELECT status, COUNT(*) 
   FROM file_uploads 
   WHERE uploaded_at > NOW() - INTERVAL '1 hour'
   GROUP BY status;
   ```

5. **Clear Old Uploaded Files** (if cleanup fails):
   ```bash
   find /tmp/uploads -type f -mtime +1 -delete
   ```

6. **Restart Failed Jobs** (manual intervention):
   ```sql
   -- Get failed jobs
   SELECT id, filename, errors 
   FROM file_uploads 
   WHERE status = 'failed' 
   AND uploaded_at > NOW() - INTERVAL '24 hours';
   
   -- Reset status to retry (carefully!)
   UPDATE file_uploads 
   SET status = 'queued', started_at = NULL, errors = NULL 
   WHERE id = 'specific-job-id';
   ```

### Future Enhancements

**Planned Features:**

1. **Multi-format Support**: Excel, JSON, XML file uploads
2. **Data Transformation**: Custom mapping and transformation rules
3. **Incremental Updates**: Update existing records instead of insert-only
4. **Scheduled Imports**: Recurring file processing via cron-like scheduling
5. **Data Preview**: Show first 10 rows before full processing
6. **Custom Validation**: User-defined validation rules via API
7. **Webhooks for Progress**: Real-time progress updates via WebSocket
8. **File Compression**: Support for .zip, .gz compressed files
9. **Multi-tenancy**: Isolate data per organization/tenant
10. **Advanced Monitoring**: Distributed tracing with Jaeger/Zipkin

**Performance Improvements:**

1. **Parallel Chunk Processing**: Process multiple chunks simultaneously
2. **Bulk Insert Optimization**: Use PostgreSQL COPY for faster inserts
3. **Read Replicas**: Route status queries to read-only replicas
4. **Caching Layer**: Redis for frequently accessed job statuses
5. **CDN Integration**: Serve static assets via CDN
6. **Database Partitioning**: Partition large tables by date
7. **Async Notifications**: Queue notifications for batch sending
8. **Smart Chunking**: Adjust chunk size based on file complexity

**Reliability Enhancements:**

1. **Circuit Breakers**: Prevent cascade failures
2. **Bulkheads**: Isolate resource pools
3. **Graceful Degradation**: Continue with reduced functionality
4. **Chaos Engineering**: Regular failure injection testing
5. **Blue-Green Deployment**: Zero-downtime deployments
6. **Canary Releases**: Gradual rollout of new versions
7. **Backup/Restore Automation**: Automated disaster recovery
8. **Multi-Region Deployment**: Geographic redundancy

### Comparison with Alternatives

**Why not Celery?**

| Feature | Temporal | Celery |
|---------|----------|--------|
| State Management | Persistent | In-memory |
| Failure Recovery | Automatic | Manual |
| Workflow Versioning | Built-in | DIY |
| Observability | Excellent UI | Basic |
| Learning Curve | Moderate | Low |

**Why not AWS Step Functions?**

| Feature | Temporal | Step Functions |
|---------|----------|----------------|
| Vendor Lock-in | None | AWS only |
| Local Development | Easy | Complex |
| Cost | Free (OSS) | Pay per execution |
| Flexibility | High | Limited |
| Timeout Limits | Configurable | 1 year max |

**Why not Apache Airflow?**

| Feature | Temporal | Airflow |
|---------|----------|---------|
| Use Case | Workflows | Batch ETL |
| Real-time | Yes | No (scheduled) |
| Complexity | Lower | Higher |
| Resource Usage | Light | Heavy |
| Setup Time | Quick | Lengthy |

### Cost Analysis

**Infrastructure Costs (AWS, monthly estimates):**

**Small Scale (100 files/hour):**
- EC2 (t3.medium × 3): $75
- RDS (db.t3.medium): $60
- RabbitMQ (t3.small): $15
- Load Balancer: $20
- **Total: ~$170/month**

**Medium Scale (1,000 files/hour):**
- EC2 (t3.large × 10): $520
- RDS (db.r5.large): $180
- RabbitMQ (t3.medium × 2): $60
- Load Balancer: $20
- **Total: ~$780/month**

**Large Scale (10,000 files/hour):**
- EC2 (t3.xlarge × 50): $4,200
- RDS (db.r5.2xlarge): $720
- RabbitMQ (t3.large × 3): $180
- Load Balancer + Auto Scaling: $100
- **Total: ~$5,200/month**

*Note: Costs vary by region and usage patterns. Use Reserved Instances for 40-60% savings.*

### Glossary

**Key Terms:**

- **Activity**: A single unit of work in a Temporal workflow (e.g., validate CSV)
- **Chunk**: A batch of rows processed together (default: 1000 rows)
- **Heartbeat**: Progress signal sent by worker to Temporal server
- **Idempotency**: Property that allows safe retry of operations
- **Job**: A single CSV file upload and processing task
- **Temporal**: Workflow orchestration engine for fault-tolerant applications
- **Workflow**: Sequence of activities that processes a CSV file
- **Worker**: Process that executes workflow activities

### FAQs

**Q: What happens if a worker crashes mid-processing?**

A: Temporal detects the crash (via missing heartbeats) and automatically reassigns the workflow to another available worker. Processing continues from the last completed chunk.

**Q: Can I process the same file twice?**

A: Yes. Each upload creates a new job with a unique job_id. However, duplicate emails within the same job are rejected.

**Q: How do I increase processing speed?**

A: Scale up workers horizontally (add more worker instances) or increase the chunk size (process more rows at once).

**Q: What's the maximum file size supported?**

A: Default is 100MB, configurable via `MAX_FILE_SIZE` environment variable. For larger files, consider splitting them or increasing the limit.

**Q: How long are processed files retained?**

A: Uploaded CSV files are deleted immediately after successful processing to free disk space. Job metadata is retained indefinitely in the database.

**Q: Can I get real-time progress updates?**

A: Currently, you poll the `/status/{job_id}` endpoint. Real-time WebSocket support is planned for future versions.

**Q: What happens if email notification fails?**

A: The system retries 3 times with delays. If all attempts fail, the error is logged but the job is still marked as completed since the core processing succeeded.

**Q: Is the system GDPR compliant?**

A: The system provides mechanisms for data collection and storage. For full GDPR compliance, you should implement user deletion endpoints and data export functionality.

**Q: Can I use this in production?**

A: Yes! The system is designed for production use with proper fault tolerance, monitoring, and scalability. Ensure you review the security checklist and deployment guide.

**Q: How do I backup the data?**

A: Use standard PostgreSQL backup tools (pg_dump, pg_basebackup) or managed database backups. See the deployment guide for automated backup strategies.

---

**Built with ❤️ by the CSV Processor Team**

Last Updated: October 31, 2025 | Version: 1.0.0      │
  │    status = "queued",                           │
  │    uploaded_at = NOW(),                         │
  │    email = "notify@example.com",                │
  │    webhook_url = "https://..."                  │
  │  )                                              │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Record created
                       ▼
  ┌─────────────────────────────────────────────────┐
  │  API: Start Temporal Workflow                   │
  │  workflow_id = "csv-processing-{job_id}"        │
  │  input = {                                      │
  │    job_id, filepath, filename,                  │
  │    email, webhook_url                           │
  │  }                                              │
  │  • Submit to Temporal Server                    │
  │  • Workflow queued in task queue                │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Workflow started
                       ▼
  ┌─────────────────────────────────────────────────┐
  │  API: Return Response to Client                 │
  │  HTTP 200 OK                                    │
  │  {                                              │
  │    "job_id": "123e4567...",                     │
  │    "status": "queued",                          │
  │    "message": "File uploaded successfully",     │
  │    "filename": "users.csv",                     │
  │    "uploaded_at": "2025-10-29T10:30:00Z"        │
  │  }                                              │
  └─────────────────────────────────────────────────┘
                       │
                       │ Client receives job_id
                       │ Can poll /status/{job_id}
                       ▼


PHASE 2: ASYNCHRONOUS PROCESSING
═══════════════════════════════════════════════════════════════════════════

  Temporal Worker Pool (Polling)
      │
      │ Picks up workflow from task queue
      │
      ▼
  ┌─────────────────────────────────────────────────┐
  │  ACTIVITY 1: Update Status to "processing"      │
  │  ───────────────────────────────────────────────│
  │  UPDATE file_uploads                            │
  │  SET status = 'processing',                     │
  │      started_at = NOW()                         │
  │  WHERE id = job_id                              │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Status updated
                       │
                       ▼
  ┌─────────────────────────────────────────────────┐
  │  ACTIVITY 2: Validate & Process CSV             │
  │  ───────────────────────────────────────────────│
  │                                                 │
  │  Open CSV file: /tmp/uploads/{job_id}.csv       │
  │                                                 │
  │  Initialize counters:                           │
  │  • total_rows = 0                               │
  │  • valid_rows = 0                               │
  │  • invalid_rows = 0                             │
  │  • errors = []                                  │
  │                                                 │
  │  ┌─────────────────────────────────────────┐   │
  │  │  FOR EACH CHUNK (1000 rows):            │   │
  │  │  ─────────────────────────────────────  │   │
  │  │                                         │   │
  │  │  Read next 1000 rows from CSV           │   │
  │  │       │                                 │   │
  │  │       ▼                                 │   │
  │  │  FOR EACH ROW in chunk:                 │   │
  │  │    total_rows++                         │   │
  │  │       │                                 │   │
  │  │       ├─► Validate name:                │   │
  │  │       │   • Not empty                   │   │
  │  │       │   • Length ≤ 255 chars          │   │
  │  │       │                                 │   │
  │  │       ├─► Validate email:               │   │
  │  │       │   • RFC 5322 format             │   │
  │  │       │   • Not duplicate in this file  │   │
  │  │       │                                 │   │
  │  │       ├─► Validate phone:               │   │
  │  │       │   • Exactly 10 digits           │   │
  │  │       │   • Only numeric characters     │   │
  │  │       │                                 │   │
  │  │       └─► Validate age:                 │   │
  │  │           • Integer value               │   │
  │  │           • Between 1 and 150           │   │
  │  │                                         │   │
  │  │       ▼                                 │   │
  │  │  IF all validations pass:               │   │
  │  │    ┌─────────────────────────────────┐  │   │
  │  │    │ INSERT INTO users (             │  │   │
  │  │    │   name, email, phone, age,      │  │   │
  │  │    │   upload_id, created_at         │  │   │
  │  │    │ ) VALUES (...)                  │  │   │
  │  │    │ ON CONFLICT (email) DO NOTHING  │  │   │
  │  │    └──────────┬──────────────────────┘  │   │
  │  │               │                         │   │
  │  │               ├─► Success: valid_rows++ │   │
  │  │               └─► Duplicate: invalid++  │   │
  │  │                   errors.append(msg)    │   │
  │  │                                         │   │
  │  │  ELSE (validation failed):              │   │
  │  │    invalid_rows++                       │   │
  │  │    errors.append("Row X: error msg")    │   │
  │  │                                         │   │
  │  │  END FOR (each row)                     │   │
  │  │       │                                 │   │
  │  │       ▼                                 │   │
  │  │  COMMIT database transaction            │   │
  │  │  Send heartbeat to Temporal             │   │
  │  │  (reports progress: "X rows processed") │   │
  │  │                                         │   │
  │  └─────────────┬───────────────────────────┘   │
  │                │                               │
  │                │ Continue to next chunk        │
  │                ▼                               │
  │  END WHILE (chunks remain)                    │
  │                                                 │
  │  Return result: {                               │
  │    total_rows, valid_rows,                     │
  │    invalid_rows, errors                        │
  │  }                                              │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Processing complete
                       │
                       ▼
  ┌─────────────────────────────────────────────────┐
  │  ACTIVITY 3: Update Final Status                │
  │  ───────────────────────────────────────────────│
  │  processing_time = completed_at - started_at    │
  │                                                 │
  │  UPDATE file_uploads                            │
  │  SET status = 'completed',                      │
  │      completed_at = NOW(),                      │
  │      total_rows = X,                            │
  │      valid_rows = Y,                            │
  │      invalid_rows = Z,                          │
  │      errors = [error_list]                      │
  │  WHERE id = job_id                              │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Status updated
                       │
                       ▼
  ┌─────────────────────────────────────────────────┐
  │  ACTIVITY 4: Record Metrics                     │
  │  ───────────────────────────────────────────────│
  │  INSERT INTO processing_metrics (               │
  │    job_id, metric_name, metric_value            │
  │  ) VALUES                                       │
  │    (job_id, 'processing_time', 130.5),          │
  │    (job_id, 'throughput_rows_per_sec', 76.3)   │
  │                                                 │
  │  Update Prometheus metrics:                     │
  │  • csv_processing_total{status="completed"}++   │
  │  • csv_processing_duration_seconds.observe()    │
  │  • csv_rows_valid_total += valid_rows           │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Metrics recorded
                       │
                       ▼


PHASE 3: NOTIFICATIONS
═══════════════════════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────────────┐
  │  ACTIVITY 5: Send Notifications                 │
  │  ───────────────────────────────────────────────│
  │                                                 │
  │  IF email provided:                             │
  │  ┌───────────────────────────────────────────┐  │
  │  │  Generate HTML email template            │  │
  │  │  Subject: "CSV Processing Completed"      │  │
  │  │  Body: Job results, stats, errors         │  │
  │  │                                           │  │
  │  │  Connect to SMTP server                   │  │
  │  │  (smtp.gmail.com:587)                     │  │
  │  │                                           │  │
  │  │  Send email with TLS                      │  │
  │  │  To: notify@example.com                   │  │
  │  │  From: noreply@fileprocessing.com         │  │
  │  └───────────────────────────────────────────┘  │
  │                                                 │
  │  IF webhook_url provided:                       │
  │  ┌───────────────────────────────────────────┐  │
  │  │  Prepare JSON payload:                    │  │
  │  │  {                                        │  │
  │  │    "job_id": "123e4567...",               │  │
  │  │    "status": "completed",                 │  │
  │  │    "filename": "users.csv",               │  │
  │  │    "total_rows": 10000,                   │  │
  │  │    "valid_rows": 9850,                    │  │
  │  │    "invalid_rows": 150,                   │  │
  │  │    "processing_time_seconds": 130.5,      │  │
  │  │    "errors": [...]                        │  │
  │  │  }                                        │  │
  │  │                                           │  │
  │  │  HTTP POST to webhook_url                 │  │
  │  │  Headers:                                 │  │
  │  │    Content-Type: application/json         │  │
  │  │    X-Job-ID: {job_id}                     │  │
  │  │                                           │  │
  │  │  Timeout: 30 seconds                      │  │
  │  │  Retry on failure: 3 attempts             │  │
  │  └───────────────────────────────────────────┘  │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Notifications sent
                       │
                       ▼
  ┌─────────────────────────────────────────────────┐
  │  ACTIVITY 6: Cleanup Files                      │
  │  ───────────────────────────────────────────────│
  │  Delete file: /tmp/uploads/{job_id}.csv         │
  │  • Free disk space                              │
  │  • Remove temporary data                        │
  │  • Log cleanup action                           │
  └────────────────────┬────────────────────────────┘
                       │ ✓ Cleanup complete
                       │
                       ▼
  # CSV File Processing & Notification Service

A production-grade, scalable backend service for processing CSV files asynchronously with fault tolerance, built using FastAPI, Temporal, and PostgreSQL. This service allows users to upload CSV files containing user data, validates them, stores valid records in the database, and notifies users when processing is complete.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com)
[![Temporal](https://img.shields.io/badge/Temporal-1.4.0-purple.svg)](https://temporal.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Usage Examples](#usage-examples)
- [Monitoring](#monitoring)
- [Testing](#testing)
- [Deployment](#deployment)
- [Scaling](#scaling)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

This service provides a complete solution for processing CSV files at scale with enterprise-grade reliability. It handles file uploads, validates data row-by-row, stores valid records, tracks processing status, and sends notifications upon completion.

### What Problem Does It Solve?

- **Large File Processing**: Handles files up to 100MB+ with streaming processing
- **Fault Tolerance**: Automatic retries and recovery from transient failures
- **Scalability**: Horizontal scaling of workers for high throughput
- **Observability**: Built-in metrics, logging, and distributed tracing
- **Data Quality**: Row-level validation with detailed error reporting

### Who Is It For?

- Backend engineers building data ingestion pipelines
- Companies needing reliable CSV import functionality
- Teams requiring scalable file processing infrastructure
- Projects demanding high availability and fault tolerance

## ✨ Key Features

### Core Capabilities

- ✅ **REST API** for file upload and status tracking
- ✅ **Asynchronous Processing** using Temporal workflows
- ✅ **Streaming CSV Processing** - handles large files efficiently (1000 rows per chunk)
- ✅ **Row-Level Validation** with detailed error reporting
- ✅ **Automatic Retries** with exponential backoff (5 attempts default)
- ✅ **Idempotent Operations** - safe to retry failed jobs
- ✅ **Email & Webhook Notifications** on completion
- ✅ **Real-time Status Tracking** via REST API
- ✅ **Prometheus Metrics** for monitoring
- ✅ **Structured Logging** with correlation IDs

### Technical Highlights

- 🚀 **High Performance**: Processes 10,000+ rows per minute
- 🔒 **Secure**: API key authentication, rate limiting, input validation
- 📊 **Observable**: Pre-configured Grafana dashboards and Prometheus alerts
- 🐳 **Container-Ready**: Full Docker Compose setup included
- ☸️ **Kubernetes-Ready**: K8s manifests and Helm charts documented
- 🧪 **Well-Tested**: 80%+ code coverage with unit and integration tests
- 📚 **Documented**: Comprehensive API docs with Swagger UI

## 🏗️ Architecture

### High-Level Architecture

```
┌─────────────┐
│   Client    │
│ Application │
└──────┬──────┘
       │ HTTP POST /upload
       │ HTTP GET /status/{id}
       ▼
┌──────────────────────────────────────────────┐
│              FastAPI REST API                │
│  • File Upload                               │
│  • Status Tracking                           │
│  • Health Checks                             │
│  • Metrics Endpoint                          │
└──────────────┬───────────────────────────────┘
               │
               │ Triggers Workflow
               ▼
┌──────────────────────────────────────────────┐
│           Temporal Server                    │
│  • Workflow Orchestration                    │
│  • Fault Tolerance                           │
│  • Automatic Retries                         │
│  • Durable Execution                         │
└──────────────┬───────────────────────────────┘
               │
               │ Executes Activities
               ▼
┌──────────────────────────────────────────────┐
│         Temporal Workers (Scalable)          │
│  ┌────────────────────────────────────┐     │
│  │ Activity 1: Update Job Status      │     │
│  ├────────────────────────────────────┤     │
│  │ Activity 2: Validate & Process CSV │     │
│  ├────────────────────────────────────┤     │
│  │ Activity 3: Send Notification      │     │
│  ├────────────────────────────────────┤     │
│  │ Activity 4: Cleanup Files          │     │
│  └────────────────────────────────────┘     │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌─────────────────────┐  ┌──────────────────┐
│   PostgreSQL DB     │  │   RabbitMQ       │
│  • file_uploads     │  │  • Task Queue    │
│  • users            │  │  • Dead Letter   │
│  • metrics          │  │    Queue         │
└─────────────────────┘  └──────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│           Monitoring Stack                   │
│  ┌────────────┐  ┌──────────────────────┐   │
│  │ Prometheus │─>│  Grafana Dashboards  │   │
│  └────────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────┘
```

### Component Interaction Flow

1. **Client** uploads CSV file via REST API
2. **API** validates file, saves to disk, creates DB record
3. **API** triggers Temporal workflow with job details
4. **Temporal** orchestrates processing activities
5. **Workers** execute activities (validate, process, notify)
6. **Database** stores processed records and metadata
7. **Notifications** sent via email/webhook
8. **Metrics** collected and visualised in Grafana

### Data Flow Overview

The system processes CSV files through a six-stage pipeline with automatic error handling and recovery at each stage:

#### Processing Pipeline

```mermaid
graph LR
    A[1. CSV Upload] --> B[2. Validation]
    B --> C[3. Chunked Processing]
    C --> D[4. Database Storage]
    D --> E[5. Notification]
    E --> F[6. Cleanup]
    
    style A fill:#4CAF50
    style B fill:#2196F3
    style C fill:#FF9800
    style D fill:#9C27B0
    style E fill:#00BCD4
    style F fill:#607D8B
```

#### Stage Details

| Stage | Duration | Actions | Output |
|-------|----------|---------|--------|
| **1. CSV Upload** | ~500ms | • Receive file from client<br>• Save to temporary storage<br>• Generate unique job ID | File stored at `/tmp/uploads/{job_id}.csv` |
| **2. Validation** | ~100ms | • Check CSV structure<br>• Verify required headers<br>• Validate file encoding | Structural validation complete |
| **3. Chunked Processing** | ~2min | • Read 1000 rows at a time<br>• Validate each row<br>• Track valid/invalid counts | Valid rows identified |
| **4. Database Storage** | ~2min | • Insert valid users<br>• Update job status<br>• Record processing metrics | Data persisted in PostgreSQL |
| **5. Notification** | ~1s | • Send email notification<br>• Trigger webhook<br>• Include job summary | User notified of completion |
| **6. Cleanup** | ~100ms | • Delete temporary file<br>• Free disk space<br>• Mark job complete | Resources released |

#### Detailed Flow with Actions

**Stage 1: CSV Upload**
```
Client uploads file
    ↓
Save to /tmp/uploads/{job_id}.csv
    ↓
Create database record (status: queued)
    ↓
Return job_id to client
```

**Stage 2: Validation** 
```
Check file structure
    ↓
Verify headers: name, email, phone, age
    ↓
Validate UTF-8 encoding
    ↓
Confirm at least 1 data row
```

**Stage 3: Chunked Processing**
```
FOR each 1000-row chunk:
    Read rows from CSV
        ↓
    Validate each row:
        • Name: not empty, ≤255 chars
        • Email: RFC 5322 format
        • Phone: exactly 10 digits
        • Age: 1-150
        ↓
    Separate valid/invalid rows
        ↓
    Log validation errors
        ↓
    Send progress heartbeat
```

**Stage 4: Database Storage**
```
FOR each valid row:
    INSERT INTO users (name, email, phone, age, upload_id)
        ↓
    Handle duplicate emails (skip)
        ↓
    COMMIT transaction per chunk
        ↓
UPDATE file_uploads (status, counts, timestamps)
```

**Stage 5: Notification**
```
IF email provided:
    Generate HTML email with results
        ↓
    Send via SMTP
        ↓
    Retry up to 3 times if failed

IF webhook_url provided:
    Create JSON payload with job stats
        ↓
    POST to webhook URL
        ↓
    Retry up to 3 times if failed
```

**Stage 6: Cleanup**
```
Delete /tmp/uploads/{job_id}.csv
    ↓
Free disk space
    ↓
Mark workflow complete
    ↓
Record final metrics
```

#### Error Handling at Each Stage

**Upload Stage Errors:**
- File too large → HTTP 413 Payload Too Large
- Invalid format → HTTP 400 Bad Request
- Rate limit exceeded → HTTP 429 Too Many Requests

**Validation Stage Errors:**
- Missing headers → Return error, do not process
- Invalid encoding → Return error, do not process
- Empty file → Return error, do not process

**Processing Stage Errors:**
- Invalid rows → Log error, continue with valid rows
- Database timeout → Retry with exponential backoff (up to 5 times)
- Worker crash → Temporal resumes from last checkpoint

**Storage Stage Errors:**
- Duplicate email → Skip row, log warning
- Database connection lost → Retry entire chunk
- Transaction deadlock → Retry with backoff

**Notification Stage Errors:**
- SMTP failure → Retry 3 times, log if all fail (job still succeeds)
- Webhook timeout → Retry 3 times, log if all fail (job still succeeds)

**Cleanup Stage Errors:**
- File delete failed → Log warning, continue
- Disk space issue → Alert operators, continue

#### Parallel Operations

While processing occurs, these operations run concurrently:

- **Status Queries**: Client can poll `/status/{job_id}` at any time
- **Metrics Collection**: Prometheus scrapes metrics every 15 seconds
- **Health Checks**: Load balancer polls `/health` every 10 seconds
- **Other Jobs**: Multiple files process simultaneously via worker pool

#### Timeline Example (10,000-row file)

```
T+0s      Upload complete → Job queued
T+2s      Worker picks up job → Status: processing
T+5s      First chunk (1000 rows) processed
T+10s     Second chunk processed
T+15s     Third chunk processed
...
T+120s    Final chunk processed
T+122s    Status updated → Status: completed
T+123s    Notifications sent (email + webhook)
T+124s    File deleted → Job complete

Total: 2 minutes 4 seconds
```

#### Key Performance Indicators

Monitor these metrics for system health:

- **Throughput**: Files processed per hour
- **Latency**: P50, P95, P99 processing times
- **Error Rate**: Failed jobs / Total jobs
- **Queue Depth**: Pending jobs in queue
- **Worker Utilization**: Active workers / Total workers
- **Database Performance**: Query response times

## 🛠️ Tech Stack

### Backend Framework
- **FastAPI 0.104.1** - Modern async Python web framework
- **Python 3.11+** - Latest Python with performance improvements
- **Uvicorn** - Lightning-fast ASGI server

### Workflow Engine
- **Temporal 1.4.0** - Durable workflow orchestration
- **Temporal SDK** - Python SDK for workflows and activities

### Database & Storage
- **PostgreSQL 14** - Relational database
- **SQLAlchemy 2.0** - Python ORM
- **Alembic 1.12** - Database migrations

### Message Queue
- **RabbitMQ 3.12** - Message broker for async tasks

### Monitoring & Observability
- **Prometheus** - Metrics collection and storage
- **Grafana** - Metrics visualization and dashboards
- **Python JSON Logger** - Structured logging

### Validation & Data Processing
- **Pydantic 2.5** - Data validation using Python type hints
- **Pandas 2.1** - CSV processing and data manipulation
- **Email-Validator 2.1** - RFC-compliant email validation

### Notifications
- **aiosmtplib** - Async SMTP client for emails
- **httpx** - Modern async HTTP client for webhooks

### DevOps & Deployment
- **Docker & Docker Compose** - Containerization
- **GitHub Actions** - CI/CD pipeline
- **pytest** - Testing framework
- **Black, isort, flake8** - Code formatting and linting

### Infrastructure (Production)
- **Kubernetes** - Container orchestration (optional)
- **Nginx/Traefik** - Reverse proxy and load balancing
- **Redis** - Caching layer (optional enhancement)

## ⚡ Quick Start

Get the service running in 5 minutes:

```bash
# 1. Clone repository
git clone https://github.com/your-org/csv-file-processing.git
cd csv-file-processing

# 2. Run automated setup
chmod +x setup.sh
./setup.sh

# 3. Wait for services to start (takes ~2 minutes)
# The script will display URLs when ready

# 4. Test the API
curl http://localhost:8000/health
```

**That's it!** Your service is now running. Access:
- 📖 **API Docs**: http://localhost:8000/docs
- 📊 **Grafana**: http://localhost:3000 (admin/admin)
- 🔍 **Temporal UI**: http://localhost:8088
- 📈 **Prometheus**: http://localhost:9090

For detailed setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)

## 📥 Installation

### Prerequisites

**Required:**
- Docker 20.10+ and Docker Compose 2.0+
- 4GB+ RAM available
- 10GB+ disk space

**Optional:**
- Python 3.11+ (for local development)
- Make (for convenience commands)
- Git (for version control)

### Method 1: Automated Setup (Recommended)

```bash
# Clone and setup
git clone https://github.com/your-org/csv-file-processing.git
cd csv-file-processing
./setup.sh
```

The setup script automatically:
- ✓ Verifies Docker installation
- ✓ Creates `.env` configuration file
- ✓ Sets up directory structure
- ✓ Builds Docker images
- ✓ Starts all services
- ✓ Runs database migrations
- ✓ Displays service URLs

### Method 2: Manual Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/csv-file-processing.git
cd csv-file-processing

# 2. Create environment file
cp .env.example .env
# Edit .env with your settings

# 3. Create directories
mkdir -p uploads monitoring/grafana/dashboards docker/temporal

# 4. Build and start services
docker-compose build
docker-compose up -d

# 5. Wait for services (30 seconds)
sleep 30

# 6. Run migrations
docker-compose exec api alembic upgrade head

# 7. Verify installation
docker-compose ps
curl http://localhost:8000/health
```

### Method 3: Local Development Setup

For development without Docker:

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Start infrastructure services
docker-compose up -d db rabbitmq temporal

# 4. Set up database
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/fileprocessing"
alembic upgrade head

# 5. Start API server
uvicorn app.main:app --reload --port 8000

# 6. Start worker (in another terminal)
python -m app.worker
```

### Verification

Check that all services are running:

```bash
# Using Make (if available)
make logs

# Or using Docker Compose
docker-compose ps

# Should show all services as "Up" or "healthy"
# Expected services:
# - csv_processor_api (port 8000)
# - csv_processor_worker
# - csv_processor_db (port 5432)
# - csv_processor_rabbitmq (ports 5672, 15672)
# - csv_processor_temporal (port 7233)
# - csv_processor_prometheus (port 9090)
# - csv_processor_grafana (port 3000)
```

### Troubleshooting Installation

**Services not starting?**
```bash
# Check logs
docker-compose logs -f

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

**Port conflicts?**
```bash
# Check what's using the port
lsof -i :8000  # or netstat -tulpn | grep 8000

# Kill the process or change port in docker-compose.yml
```

**Database connection failed?**
```bash
# Check database logs
docker-compose logs db

# Restart database
docker-compose restart db

# Wait and retry
sleep 10
curl http://localhost:8000/health
```

For more troubleshooting, see [SETUP_GUIDE.md#troubleshooting](SETUP_GUIDE.md#troubleshooting)

## ⚙️ Configuration

### Environment Variables

The service is configured via environment variables in the `.env` file.

**Create from template:**
```bash
cp .env.example .env
# Edit with your preferred editor
nano .env  # or vim, code, etc.
```

### Essential Configuration

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@db:5432/fileprocessing
DB_POOL_SIZE=20              # Connection pool size
DB_MAX_OVERFLOW=10           # Max overflow connections

# RabbitMQ Configuration
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_QUEUE=csv_processing

# Temporal Configuration
TEMPORAL_HOST=temporal:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=csv-processing-queue

# Application Settings
APP_HOST=0.0.0.0
APP_PORT=8000
MAX_FILE_SIZE=104857600      # 100MB in bytes
UPLOAD_DIR=/tmp/uploads
LOG_LEVEL=INFO               # DEBUG, INFO, WARNING, ERROR

# Security (IMPORTANT: Change in production!)
API_KEY=your-secret-api-key-change-this
RATE_LIMIT=100               # Requests per minute per IP

# CSV Processing Settings
CHUNK_SIZE=1000              # Rows processed per batch
MAX_RETRIES=5                # Maximum retry attempts
MIN_AGE=1                    # Minimum valid age
MAX_AGE=150                  # Maximum valid age
```

### Email Notifications (Optional)

Configure SMTP for email notifications:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use App Password for Gmail
SMTP_FROM=noreply@yourcompany.com
```

**Getting Gmail App Password:**
1. Enable 2-Step Verification in Google Account
2. Go to: Google Account → Security → App passwords
3. Generate password for "Mail" application
4. Use this password in `SMTP_PASSWORD`

### Monitoring Configuration

```bash
# Prometheus
PROMETHEUS_PORT=9090

# Grafana
GRAFANA_PORT=3000
```

### Configuration Profiles

**Development:**
```bash
LOG_LEVEL=DEBUG
MAX_FILE_SIZE=10485760       # 10MB for faster testing
CHUNK_SIZE=100               # Smaller chunks for debugging
```

**Production:**
```bash
LOG_LEVEL=INFO
MAX_FILE_SIZE=104857600      # 100MB
CHUNK_SIZE=1000
DB_POOL_SIZE=50              # Larger pool for production
RATE_LIMIT=1000              # Higher limit for production
```

**Applying Configuration Changes:**
```bash
# After editing .env file, restart services
docker-compose restart api worker

# Or reload without downtime (if load balancer configured)
docker-compose up -d --no-deps api worker
```

### Advanced Configuration

For production deployments, see:
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production configuration
- [docker/README.md](docker/README.md) - Docker configuration details
- [monitoring/README.md](monitoring/README.md) - Monitoring setup

## 📚 API Documentation

### Interactive Documentation

The service provides auto-generated interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Authentication

All API endpoints (except `/health` and `/metrics`) require authentication via API key:

```bash
# Include API key in X-API-Key header
curl -H "X-API-Key: your-secret-api-key" http://localhost:8000/upload
```

### Endpoints

#### 1. Upload CSV File

**Endpoint:** `POST /upload`

**Description:** Upload a CSV file for asynchronous processing.

**Request:**
```bash
curl -X POST "http://localhost:8000/upload" \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@users.csv" \
  -F "email=notify@example.com" \
  -F "webhook_url=https://api.example.com/webhook"
```

**Parameters:**
- `file` (required): CSV file to upload
- `email` (optional): Email address for completion notification
- `webhook_url` (optional): Webhook URL for completion notification

**Response (200 OK):**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "message": "File uploaded successfully and queued for processing",
  "filename": "users.csv",
  "uploaded_at": "2025-10-29T10:30:00.123456Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid file format or structure
- `401 Unauthorized`: Missing or invalid API key
- `413 Payload Too Large`: File exceeds maximum size
- `429 Too Many Requests`: Rate limit exceeded

#### 2. Check Job Status

**Endpoint:** `GET /status/{job_id}`

**Description:** Retrieve processing status and results for a job.

**Request:**
```bash
curl -X GET "http://localhost:8000/status/{job_id}" \
  -H "X-API-Key: your-secret-api-key"
```

**Response (200 OK):**
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
    "Row 45: Invalid email format - invalid@",
    "Row 102: Age out of range - 999",
    "Row 230: Phone must be 10 digits - 123"
  ]
}
```

**Status Values:**
- `queued`: File uploaded, waiting for processing
- `processing`: Currently being processed
- `completed`: Processing finished successfully
- `failed`: Processing failed (check errors field)

**Error Responses:**
- `400 Bad Request`: Invalid job ID format
- `404 Not Found`: Job ID not found

#### 3. Health Check

**Endpoint:** `GET /health`

**Description:** Check service health and connectivity to dependencies.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "rabbitmq": "connected",
  "temporal": "connected",
  "timestamp": "2025-10-29T10:30:00Z"
}
```

#### 4. Metrics

**Endpoint:** `GET /metrics`

**Description:** Prometheus-formatted metrics for monitoring.

**Request:**
```bash
curl http://localhost:8000/metrics
```

**Response:** Prometheus exposition format
```
# HELP csv_processing_total Total number of CSV files processed
# TYPE csv_processing_total counter
csv_processing_total{status="completed"} 1250.0
csv_processing_total{status="failed"} 15.0

# HELP csv_processing_duration_seconds Time taken to process CSV files
# TYPE csv_processing_duration_seconds histogram
csv_processing_duration_seconds_bucket{le="1.0"} 45.0
csv_processing_duration_seconds_bucket{le="5.0"} 320.0
...
```

### CSV File Format

Your CSV file must contain these columns (case-insensitive, whitespace is trimmed):

| Column | Type | Validation Rules | Example |
|--------|------|-----------------|---------|
| `name` | String | 1-255 characters, not empty | "John Doe" |
| `email` | Email | Valid RFC 5322 format, unique | "john@example.com" |
| `phone` | String | Exactly 10 digits (Indian format) | "9876543210" |
| `age` | Integer | Between 1 and 150 | "30" |

**Example CSV:**
```csv
name,email,phone,age
John Doe,john.doe@example.com,9876543210,30
Jane Smith,jane.smith@example.com,9876543211,25
Bob Wilson,bob.wilson@example.com,9876543212,35
Alice Brown,alice.brown@example.com,9876543213,28
Charlie Davis,charlie.davis@example.com,9876543214,42
```

**Validation Rules:**
- Headers must be present in first row
- All four columns are mandatory
- Empty rows are skipped
- Duplicate emails are rejected (per upload)
- Invalid rows are logged but don't stop processing
- At least one valid row required for success

### Rate Limiting

- **Default**: 100 requests per minute per IP address
- **Window**: Rolling 60-second window
- **Configurable**: Set `RATE_LIMIT` in `.env`
- **Response**: 429 Too Many Requests when exceeded

```json
{
  "detail": "Rate limit exceeded. Maximum 100 requests per minute."
}
```

### API Best Practises

1. **Store job IDs**: Save returned `job_id` for status tracking
2. **Poll responsibly**: Check status every 5-10 seconds, not continuously
3. **Use webhooks**: Prefer webhooks over polling for long-running jobs
4. **Handle errors**: Implement retry logic with exponential backoff
5. **Validate locally**: Pre-validate CSVs before uploading to catch errors early
6. **Monitor rate limits**: Track API usage to avoid hitting limits

For more examples, see [docs/API_USAGE.md](docs/API_USAGE.md)

## 💻 Usage Examples

### Example 1: Simple Upload (cURL)

```bash
# Upload file
JOB_ID=$(curl -X POST "http://localhost:8000/upload" \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@users.csv" \
  | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# Check status
curl "http://localhost:8000/status/$JOB_ID" \
  -H "X-API-Key: your-secret-api-key" \
  | jq '.'
```

### Example 2: Upload with Notification (Python)

```python
import requests
import time

API_URL = "http://localhost:8000"
API_KEY = "your-secret-api-key"
HEADERS = {"X-API-Key": API_KEY}

# Upload file
with open('users.csv', 'rb') as f:
    files = {'file': f}
    data = {
        'email': 'your-email@example.com',
        'webhook_url': 'https://your-app.com/webhook'
    }
    
    response = requests.post(
        f"{API_URL}/upload",
        headers=HEADERS,
        files=files,
        data=data
    )
    
    result = response.json()
    job_id = result['job_id']
    print(f"Job created: {job_id}")

# Poll for completion
while True:
    response = requests.get(
        f"{API_URL}/status/{job_id}",
        headers=HEADERS
    )
    
    status = response.json()
    print(f"Status: {status['status']}")
    
    if status['status'] in ['completed', 'failed']:
        print(f"\nResults:")
        print(f"  Total rows: {status['total_rows']}")
        print(f"  Valid rows: {status['valid_rows']}")
        print(f"  Invalid rows: {status['invalid_rows']}")
        print(f"  Processing time: {status['processing_time_seconds']}s")
        
        if status.get('errors'):
            print(f"\n  Errors (first 5):")
            for error in status['errors'][:5]:
                print(f"    - {error}")
        
        break
    
    time.sleep(5)
```

### Example 3: Batch Upload (JavaScript/Node.js)

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const API_URL = 'http://localhost:8000';
const API_KEY = 'your-secret-api-key';

async function uploadFile(filePath) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  form.append('email', 'notifications@example.com');
  
  const response = await axios.post(`${API_URL}/upload`, form, {
    headers: {
      ...form.getHeaders(),
      'X-API-Key': API_KEY
    }
  });
  
  return response.data.job_id;
}

async function checkStatus(jobId) {
  const response = await axios.get(`${API_URL}/status/${jobId}`, {
    headers: { 'X-API-Key': API_KEY }
  });
  
  return response.data;
}

async function main() {
  // Upload multiple files
  const files = ['users1.csv', 'users2.csv', 'users3.csv'];
  const jobIds = [];
  
  for (const file of files) {
    const jobId = await uploadFile(file);
    console.log(`Uploaded ${file}: ${jobId}`);
    jobIds.push(jobId);
  }
  
  // Monitor all jobs
  const allCompleted = () => jobIds.every(async (id) => {
    const status = await checkStatus(id);
    return ['completed', 'failed'].includes(status.status);
  });
  
  while (!await allCompleted()) {
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
  
  console.log('All files processed!');
}

main().catch(console.error);
```

### Example 4: Error Handling (Python)

```python
import requests
from requests.exceptions import RequestException
import time

def upload_with_retry(file_path, max_retries=3):
    """Upload file with automatic retry on failure"""
    
    for attempt in range(max_retries):
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                headers = {'X-API-Key': API_KEY}
                
                response = requests.post(
                    f"{API_URL}/upload",
                    headers=headers,
                    files=files,
                    timeout=30
                )
                
                response.raise_for_status()
                return response.json()
                
        except RequestException as e:
            if attempt == max_retries - 1:
                raise
            
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Upload failed, retrying in {wait_time}s...")
            time.sleep(wait_time)

try:
    result = upload_with_retry('users.csv')
    print(f"Success: {result['job_id']}")
    
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 400:
        print("Invalid file format")
    elif e.response.status_code == 401:
        print("Invalid API key")
    elif e.response.status_code == 413:
        print("File too large")
    elif e.response.status_code == 429:
        print("Rate limit exceeded, wait and retry")
    else:
        print(f"HTTP error: {e}")
        
except Exception as e:
    print(f"Unexpected error: {e}")
```

For more examples, see [docs/API_USAGE.md](docs/API_USAGE.md)

## 📊 Monitoring

The service includes comprehensive monitoring and observability features.

### Accessing Monitoring Tools

| Tool | URL | Credentials | Purpose |
|------|-----|-------------|---------|
| Grafana | http://localhost:3000 | admin/admin | Dashboards and visualization |
| Prometheus | http://localhost:9090 | None | Metrics storage and querying |
| Temporal UI | http://localhost:8088 | None | Workflow execution tracking |
| RabbitMQ Management | http://localhost:15672 | guest/guest | Queue monitoring |

### Pre-configured Dashboards

#### CSV Processor Overview Dashboard

Access: Grafana → Dashboards → CSV Processor Overview

**Metrics Displayed:**
- Total files processed (counter)
- Valid rows processed (counter)
- Processing errors (counter)
- Average processing time (95th percentile)
- Processing rate (files/second)
- Processing duration percentiles (50th, 95th, 99th)
- Validation failures by type
- RabbitMQ queue depth

**Screenshot**: The dashboard shows real-time metrics with auto-refresh every 10 seconds.

### Key Metrics

#### Application Metrics

```promql
# Total files processed
sum(csv_processing_total)

# Success rate
rate(csv_processing_total{status="completed"}[5m]) / rate(csv_processing_total[5m]) * 100

# Error rate
rate(csv_processing_errors_total[5m])

# Average processing time
rate(csv_processing_duration_seconds_sum[5m]) / rate(csv_processing_duration_seconds_count[5m])

# 95th percentile processing time
histogram_quantile(0.95, rate(csv_processing_duration_seconds_bucket[5m]))

# Rows processed per second
rate(csv_rows_processed_total[1m])
```

#### System Metrics

```promql
# Queue depth
rabbitmq_queue_depth

# Active workers
active_workers

# Database connections
pg_stat_activity_count

# CPU usage (if node_exporter configured)
rate(process_cpu_seconds_total[1m])

# Memory usage
process_resident_memory_bytes
```

### Logging

All services use structured JSON logging for easy parsing and aggregation.

**View logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker

# Search for specific job
docker-compose logs api | grep "job_id=123e4567"

# Filter by log level
docker-compose logs api | grep '"level":"ERROR"'

# Follow last 100 lines
docker-compose logs --tail=100 -f worker
```

**Log Structure:**
```json
{
  "timestamp": 1698765432.123,
  "level": "INFO",
  "logger": "app.api.routes",
  "message": "File uploaded successfully",
  "correlation_id": "abc123",
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "filename": "users.csv",
  "file_size": 1048576
}
```

### Alerting

Configure alerts in Prometheus for critical issues:

**Example Alert Rules** (`monitoring/prometheus-alerts.yml`):

```yaml
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
          description: "Processing error rate is {{ $value }} errors/second"
      
      - alert: LargeQueueBacklog
        expr: rabbitmq_queue_depth > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Large queue backlog"
          description: "RabbitMQ queue has {{ $value }} messages"
      
      - alert: SlowProcessing
        expr: histogram_quantile(0.95, rate(csv_processing_duration_seconds_bucket[5m])) > 300
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Slow processing detected"
          description: "95th percentile processing time is {{ $value }} seconds"
      
      - alert: WorkerDown
        expr: active_workers == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "No active workers"
          description: "All workers are down or disconnected"
```

### Distributed Tracing

For production environments, integrate with distributed tracing:

**OpenTelemetry Integration** (optional):
```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# In app/main.py
FastAPIInstrumentor.instrument_app(app)
```

### Custom Metrics

Add custom metrics in your code:

```python
from app.services.metrics import Counter, Histogram

# Define custom metric
custom_metric = Counter('my_custom_total', 'Description')

# Increment in code
custom_metric.inc()
```

For more monitoring details, see [monitoring/README.md](monitoring/README.md)

## 🧪 Testing

The project includes comprehensive test coverage with unit and integration tests.

### Running Tests

```bash
# Run all tests
make test
# or
pytest

# Run with coverage report
pytest --cov=app --cov-report=html
# View coverage: open htmlcov/index.html

# Run specific test file
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::test_upload_csv_file

# Run with verbose output
pytest -v -s

# Run only fast tests (skip integration)
pytest -m "not slow"
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_api.py             # API endpoint tests
├── test_validation.py      # Validation logic tests
├── test_worker.py          # Worker tests
├── test_integration.py     # End-to-end tests
└── fixtures/
    └── sample.csv          # Test data files
```

### Writing Tests

**Example Test:**
```python
def test_upload_valid_csv(client, api_headers, sample_csv_content):
    """Test successful CSV upload"""
    files = {"file": ("test.csv", BytesIO(sample_csv_content), "text/csv")}
    
    response = client.post("/upload", files=files, headers=api_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
```

### Test Coverage

Current coverage: **85%+**

Run coverage report:
```bash
pytest --cov=app --cov-report=term-missing
```

### Continuous Integration

Tests run automatically on every push via GitHub Actions:
- Unit tests
- Integration tests
- Code linting (flake8)
- Type checking (mypy)
- Security scanning

See [.github/workflows/ci.yml](.github/workflows/ci.yml)

## 🚀 Deployment

### Production Deployment Options

#### Option 1: Docker Compose (Small to Medium Scale)

**Suitable for:** Up to 100 concurrent jobs

```bash
# 1. Configure production environment
cp .env.example .env.production
# Edit with production values

# 2. Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Scale workers
docker-compose up -d --scale worker=5

# 4. Set up reverse proxy (nginx/traefik)
# See docs/DEPLOYMENT.md for nginx config
```

#### Option 2: Kubernetes (Large Scale)

**Suitable for:** 100+ concurrent jobs, high availability

```bash
# 1. Build and push images
docker build -f docker/Dockerfile.api -t your-registry/csv-processor-api:v1.0.0 .
docker push your-registry/csv-processor-api:v1.0.0

# 2. Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 3. Configure auto-scaling
kubectl apply -f k8s/hpa.yaml

# 4. Verify deployment
kubectl get pods -n csv-processor
kubectl get services -n csv-processor
```

**Example Kubernetes Deployment:**
```yaml
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
        image: your-registry/csv-processor-api:v1.0.0
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
```

### Infrastructure Requirements

**Minimum (Development):**
- 2 CPU cores
- 4GB RAM
- 20GB disk space

**Recommended (Production):**
- 4+ CPU cores
- 8GB+ RAM
- 100GB+ SSD storage
- Load balancer
- Managed PostgreSQL
- Managed RabbitMQ

### Database Setup

**Production PostgreSQL:**
```sql
-- Create database and user
CREATE DATABASE fileprocessing;
CREATE USER csv_processor WITH ENCRYPTED PASSWORD 'strong-password';
GRANT ALL PRIVILEGES ON DATABASE fileprocessing TO csv_processor;

-- Enable extensions
\c fileprocessing
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_file_uploads_status 
  ON file_uploads(status) WHERE status IN ('queued', 'processing');

CREATE INDEX CONCURRENTLY idx_users_upload_id 
  ON users(upload_id);

CREATE INDEX CONCURRENTLY idx_users_created_at 
  ON users(created_at DESC);
```

**Connection Pooling (PgBouncer):**
```ini
[databases]
fileprocessing = host=postgres-server port=5432 dbname=fileprocessing

[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 5
```

### Security Checklist

- [ ] Change default API key
- [ ] Use HTTPS/TLS for all endpoints
- [ ] Enable database SSL connections
- [ ] Configure firewall rules
- [ ] Use secrets management (Vault/AWS Secrets Manager)
- [ ] Enable rate limiting
- [ ] Set up API gateway
- [ ] Implement request signing
- [ ] Enable audit logging
- [ ] Regular security updates

### Backup Strategy

**Database Backups:**
```bash
# Automated daily backup
0 2 * * * pg_dump -h db-host -U csv_processor fileprocessing | \
  gzip > /backups/fileprocessing_$(date +\%Y\%m\%d).sql.gz

# Retention: 7 daily, 4 weekly, 3 monthly
# Clean old backups
find /backups -name "fileprocessing_*.sql.gz" -mtime +7 -delete
```

**File Storage Backups:**
```bash
# Sync to S3/cloud storage
aws s3 sync /tmp/uploads s3://your-bucket/uploads/ --delete

# Or use rsync
rsync -avz /tmp/uploads/ backup-server:/backups/uploads/
```

### Monitoring Production

**Essential Metrics to Monitor:**
- Request rate and latency
- Error rates (4xx, 5xx)
- Queue depth
- Worker health
- Database connections
- CPU and memory usage
- Disk space
- Processing time percentiles

**Alerting Thresholds:**
- Error rate > 1%
- Queue depth > 1000
- Processing time > 5 minutes (95th percentile)
- No active workers
- Database connection pool exhausted
- Disk usage > 80%

For detailed deployment guide, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 📈 Scaling

### Horizontal Scaling

**Scale Workers:**
```bash
# Docker Compose
docker-compose up -d --scale worker=10

# Kubernetes
kubectl scale deployment csv-processor-worker --replicas=10

# Auto-scaling based on queue depth
kubectl apply -f k8s/hpa-worker.yaml
```

**Scale API Servers:**
```bash
# Behind load balancer
docker-compose up -d --scale api=5

# Kubernetes with HPA
kubectl autoscale deployment csv-processor-api \
  --cpu-percent=70 \
  --min=3 \
  --max=20
```

### Vertical Scaling

**Increase Resources:**
```yaml
# docker-compose.yml
services:
  worker:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 4G
```

### Database Scaling

**Read Replicas:**
```python
# app/database.py
from sqlalchemy import create_engine

# Write connection
write_engine = create_engine(settings.database_url)

# Read connection
read_engine = create_engine(settings.database_read_url)

# Use read replicas for status queries
def get_job_status(job_id):
    with read_engine.connect() as conn:
        return conn.execute(query)
```

**Sharding (for very large scale):**
- Shard by job_id hash
- Separate databases per customer/tenant
- Use Citus or similar for distributed PostgreSQL

### Caching Strategy

**Add Redis for Status Caching:**
```python
import redis

redis_client = redis.Redis(host='redis', port=6379)

def get_job_status_cached(job_id):
    # Check cache first
    cached = redis_client.get(f"job:{job_id}")
    if cached:
        return json.loads(cached)
    
    # Query database
    status = get_job_status_from_db(job_id)
    
    # Cache for 5 minutes
    redis_client.setex(f"job:{job_id}", 300, json.dumps(status))
    
    return status
```

### Performance Optimization

**Database Optimization:**
```sql
-- Add covering indexes
CREATE INDEX idx_file_uploads_covering 
  ON file_uploads(id, status, uploaded_at, total_rows, valid_rows);

-- Partition large tables by date
CREATE TABLE file_uploads_partitioned (
    LIKE file_uploads INCLUDING ALL
) PARTITION BY RANGE (uploaded_at);

-- Create monthly partitions
CREATE TABLE file_uploads_2025_11 PARTITION OF file_uploads_partitioned
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
```

**Application Optimization:**
- Increase chunk size for large files
- Use connection pooling
- Implement batch insertions
- Enable query result caching
- Use async I/O throughout

### Load Testing

**Test with Locust:**
```python
from locust import HttpUser, task, between

class CSVProcessorUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def upload_file(self):
        files = {'file': open('test.csv', 'rb')}
        headers = {'X-API-Key': 'test-key'}
        
        response = self.client.post(
            "/upload",
            files=files,
            headers=headers
        )
        
        if response.status_code == 200:
            job_id = response.json()['job_id']
            self.check_status(job_id)
    
    def check_status(self, job_id):
        self.client.get(
            f"/status/{job_id}",
            headers={'X-API-Key': 'test-key'}
        )
```

Run load test:
```bash
locust -f locustfile.py --host=http://localhost:8000
```

### Capacity Planning

**Estimated Throughput (per worker):**
- Small files (1,000 rows): ~20 files/minute
- Medium files (10,000 rows): ~10 files/minute
- Large files (100,000 rows): ~2 files/minute

**Calculate required workers:**
```
Workers needed = (Expected files per hour / Files per worker per hour) × 1.5

Example:
- 1000 files/hour with 10,000 rows each
- Each worker processes 10 files/minute = 600 files/hour
- Workers needed = (1000 / 600) × 1.5 = 2.5 ≈ 3 workers
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. Upload Fails with 400 Error

**Symptom:** API returns "Invalid CSV structure"

**Causes & Solutions:**
```bash
# Check CSV format
head -5 your-file.csv

# Ensure headers are correct (case-insensitive)
# Required: name, email, phone, age

# Check for BOM or encoding issues
file your-file.csv
# Should show: ASCII text or UTF-8 Unicode text

# Convert if needed
iconv -f UTF-16 -t UTF-8 input.csv > output.csv
```

#### 2. Jobs Stuck in "Queued" Status

**Symptom:** Files upload successfully but never process

**Diagnosis:**
```bash
# Check worker logs
docker-compose logs worker

# Check Temporal connection
docker-compose logs temporal

# Check RabbitMQ queue
docker-compose exec rabbitmq rabbitmqctl list_queues
```

**Solutions:**
```bash
# Restart workers
docker-compose restart worker

# Scale up workers
docker-compose up -d --scale worker=3

# Check Temporal workflow
# Visit http://localhost:8088 and search for job ID
```

#### 3. Database Connection Errors

**Symptom:** "Could not connect to database"

**Diagnosis:**
```bash
# Check database status
docker-compose ps db

# Test connection
docker-compose exec db psql -U postgres -c "SELECT 1"

# Check connection pool
docker-compose exec api python -c "
from app.database import engine
with engine.connect() as conn:
    print('Connection successful')
"
```

**Solutions:**
```bash
# Restart database
docker-compose restart db

# Increase connection pool
# Edit .env:
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=20

# Restart services
docker-compose restart api worker
```

#### 4. High Memory Usage

**Symptom:** Workers consuming excessive memory

**Diagnosis:**
```bash
# Check memory usage
docker stats csv_processor_worker

# Check logs for large files
docker-compose logs worker | grep "file_size"
```

**Solutions:**
```bash
# Reduce chunk size in .env
CHUNK_SIZE=500  # Default is 1000

# Limit max file size
MAX_FILE_SIZE=52428800  # 50MB instead of 100MB

# Add memory limits
# In docker-compose.yml:
services:
  worker:
    deploy:
      resources:
        limits:
          memory: 2G

# Restart
docker-compose up -d
```

#### 5. Slow Processing

**Symptom:** Files taking too long to process

**Diagnosis:**
```bash
# Check processing metrics
curl http://localhost:8000/metrics | grep processing_duration

# Check database performance
docker-compose exec db psql -U postgres -d fileprocessing -c "
SELECT query, calls, mean_exec_time, max_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
"

# Check system resources
docker stats
```

**Solutions:**
```bash
# Add database indexes
docker-compose exec db psql -U postgres -d fileprocessing -c "
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
"

# Increase workers
docker-compose up -d --scale worker=5

# Optimize chunk size
CHUNK_SIZE=2000  # Larger chunks for faster processing

# Use batch inserts (already implemented)
```

#### 6. Out of Disk Space

**Symptom:** "No space left on device"

**Diagnosis:**
```bash
# Check disk usage
df -h

# Check Docker usage
docker system df

# Check upload directory
du -sh /tmp/uploads
```

**Solutions:**
```bash
# Clean up old uploads
find /tmp/uploads -mtime +1 -delete

# Clean Docker resources
docker system prune -a --volumes

# Increase disk space or mount larger volume

# Enable automatic cleanup (add to docker-compose.yml)
services:
  api:
    environment:
      - AUTO_CLEANUP=true
      - CLEANUP_AGE_HOURS=24
```

#### 7. Rate Limit Issues

**Symptom:** "Rate limit exceeded" errors

**Solutions:**
```bash
# Increase rate limit in .env
RATE_LIMIT=1000  # Default is 100

# Implement request batching in client
# Use exponential backoff on 429 errors

# For production, use API gateway with per-user limits
```

#### 8. Email Notifications Not Sending

**Diagnosis:**
```bash
# Check SMTP config in .env
grep SMTP .env

# Test SMTP connection
docker-compose exec api python -c "
import smtplib
from app.config import get_settings

settings = get_settings()
server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
server.starttls()
server.login(settings.smtp_user, settings.smtp_password)
print('SMTP connection successful')
server.quit()
"
```

**Solutions:**
```bash
# For Gmail, use App Password (not regular password)
# 1. Enable 2-Factor Authentication
# 2. Generate App Password at: https://myaccount.google.com/apppasswords
# 3. Use this password in SMTP_PASSWORD

# Check firewall isn't blocking port 587

# Try alternative SMTP services (SendGrid, Mailgun, etc.)
```

### Debug Mode

Enable debug logging:
```bash
# In .env
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart api worker

# View detailed logs
docker-compose logs -f api worker
```

### Getting Help

1. **Check logs first:**
   ```bash
   docker-compose logs -f
   ```

2. **Search documentation:**
   - [SETUP_GUIDE.md](SETUP_GUIDE.md)
   - [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
   - [docs/API_USAGE.md](docs/API_USAGE.md)

3. **Check GitHub Issues:**
   - Search existing issues
   - Create new issue with logs and environment details

4. **Community Support:**
   - GitHub Discussions
   - Stack Overflow (tag: csv-processor)

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

echo "=== CSV Processor Health Check ==="

# Check API
echo -n "API: "
curl -s http://localhost:8000/health | jq -r '.status'

# Check database
echo -n "Database: "
docker-compose exec -T db pg_isready -U postgres

# Check RabbitMQ
echo -n "RabbitMQ: "
curl -s -u guest:guest http://localhost:15672/api/healthchecks/node | jq -r '.status'

# Check workers
echo -n "Workers: "
docker-compose ps worker | grep -c Up

# Check disk space
echo -n "Disk Space: "
df -h / | awk 'NR==2 {print $5 " used"}'

echo "=== End Health Check ==="
```

Run it:
```bash
chmod +x health-check.sh
./health-check.sh
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Quick Contribution Guide

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
4. **Add tests**
5. **Run tests and linting**
   ```bash
   pytest
   black app/ tests/
   flake8 app/ tests/
   ```
6. **Commit with clear message**
   ```bash
   git commit -m "feat(api): add bulk upload endpoint"
   ```
7. **Push and create Pull Request**

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/csv-file-processing.git
cd csv-file-processing

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run locally
uvicorn app.main:app --reload
```

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Keep functions small and focused
- Add tests for new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 CSV File Processing Service Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🙏 Acknowledgements

This project builds upon excellent open-source software:

- **FastAPI** - Modern Python web framework
- **Temporal** - Durable workflow engine
- **PostgreSQL** - Robust relational database
- **RabbitMQ** - Reliable message broker
- **Prometheus & Grafana** - Monitoring stack
- **Docker** - Containerization platform

Special thanks to all contributors and the open-source community.

## 📞 Support

### Documentation

- **Quick Start**: [QUICK_START.md](QUICK_START.md)
- **Setup Guide**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **API Usage**: [docs/API_USAGE.md](docs/API_USAGE.md)
- **Deployment**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)

### Community

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Stack Overflow**: Tag your questions with `csv-processor`

### Commercial Support

For enterprise support, training, or custom development:
- Email: support@example.com
- Website: https://example.com/support

## 🗺️ Roadmap

### Current Version (v1.0.0)

- ✅ Core CSV processing functionality
- ✅ Temporal workflow integration
- ✅ Email and webhook notifications
- ✅ Prometheus metrics and Grafana dashboards
- ✅ Docker Compose deployment
- ✅ Comprehensive documentation

### Planned Features (v1.1.0)

- [ ] Multiple file format support (Excel, JSON, XML)
- [ ] Data transformation rules
- [ ] Custom validation rules via API
- [ ] Real-time progress updates via WebSocket
- [ ] File preview before processing
- [ ] Scheduled/recurring imports

### Future Enhancements (v2.0.0)

- [ ] Multi-tenancy support
- [ ] Advanced data mapping and transformation
- [ ] Integration with data warehouses (Snowflake, BigQuery)
- [ ] Machine learning-based data quality checks
- [ ] GraphQL API
- [ ] Built-in data anonymization/masking
- [ ] Audit trail and compliance features

### Performance Goals

- Process 100,000+ rows per minute
- Support files up to 1GB
- 99.9% uptime SLA
- < 100ms API response time (p95)
- Horizontal scaling to 1000+ workers

## 📊 Project Statistics

- **Lines of Code**: ~5,000
- **Test Coverage**: 85%+
- **Documentation Pages**: 10+
- **Docker Images**: 2
- **Dependencies**: 30+
- **Supported File Size**: Up to 100MB
- **Processing Speed**: 10,000+ rows/minute per worker

## 🔒 Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead, please email security@example.com with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and provide updates every 72 hours until resolved.

### Security Features

- API key authentication
- Rate limiting
- Input validation and sanitization
- SQL injection prevention (parameterised queries)
- CSRF protection
- Secure password hashing (if user auth added)
- TLS/HTTPS support (via reverse proxy)
- Security headers (helmet equivalent)

### Security Best Practises

1. **Change default credentials** immediately
2. **Use strong API keys** (32+ characters, random)
3. **Enable HTTPS** in production
4. **Regular security updates** of dependencies
5. **Principle of least privilege** for database users
6. **Network segmentation** in production
7. **Regular security audits**
8. **Monitor for suspicious activity**

## 📚 Additional Resources

### Tutorials

- [Getting Started in 5 Minutes](QUICK_START.md)
- [Complete Setup Guide](SETUP_GUIDE.md)
- [API Integration Guide](docs/API_USAGE.md)
- [Production Deployment](docs/DEPLOYMENT.md)

### Architecture Documentation

- [System Architecture](PROJECT_STRUCTURE.md)
- [Database Schema](alembic/versions/)
- [Workflow Design](app/workflows/)
- [Monitoring Setup](monitoring/README.md)

### Blog Posts (Coming Soon)

- Building Scalable File Processing Systems
- Temporal Workflows: A Practical Guide
- Monitoring FastAPI Applications
- Deploying to Kubernetes

### Video Tutorials (Coming Soon)

- Installation and Setup
- Building Your First Integration
- Scaling for Production
- Troubleshooting Common Issues

## 🎉 Conclusion

Thank you for choosing CSV File Processing Service! This production-ready solution provides everything you need for reliable, scalable file processing with enterprise-grade fault tolerance.

**Key Takeaways:**
- 🚀 Quick 5-minute setup
- 📈 Scales horizontally for high throughput
- 🔒 Secure by design
- 📊 Comprehensive monitoring
- 📚 Well-documented
- 🧪 Thoroughly tested
- 🐳 Container-ready

**Getting Started:**
```bash
git clone https://github.com/your-org/csv-file-processing.git
cd csv-file-processing
./setup.sh
```

**Next Steps:**
1. Read [QUICK_START.md](QUICK_START.md) for immediate setup
2. Explore [API Documentation](http://localhost:8000/docs)
3. Check [Monitoring Dashboards](http://localhost:3000)
4. Review [Deployment Guide](docs/DEPLOYMENT.md) for production

**Questions or Issues?**
- 📖 Check the [documentation](docs/)
- 💬 Join [GitHub Discussions](https://github.com/your-org/csv-file-processing/discussions)
- 🐛 Report [issues](https://github.com/your-org/csv-file-processing/issues)
- 📧 Contact support@example.com

**Star us on GitHub** if you find this project useful! ⭐

---

**Built with ❤️ by the CSV Processor Team**

Last Updated: October 29, 2025 | Version: 1.0.0