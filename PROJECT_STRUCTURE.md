# Project Structure

Complete directory structure of the CSV File Processing Service.

```
csv-file-processing/
│
├── README.md                          # Main project documentation
├── PROJECT_STRUCTURE.md               # This file
├── requirements.txt                   # Python dependencies
├── .env.example                       # Example environment variables
├── .env                              # Actual environment variables (gitignored)
├── .gitignore                        # Git ignore rules
├── Makefile                          # Convenient commands
├── setup.sh                          # Setup script
├── alembic.ini                       # Alembic configuration
│
├── app/                              # Main application code
│   ├── __init__.py                   # Package initialiser
│   ├── main.py                       # FastAPI application entry point
│   ├── config.py                     # Configuration management
│   ├── database.py                   # Database connection & session
│   ├── models.py                     # SQLAlchemy database models
│   ├── schemas.py                    # Pydantic schemas for validation
│   ├── worker.py                     # Temporal worker
│   │
│   ├── api/                          # API layer
│   │   ├── __init__.py
│   │   ├── routes.py                 # API route handlers
│   │   └── dependencies.py           # FastAPI dependencies
│   │
│   ├── services/                     # Business logic services
│   │   ├── __init__.py
│   │   ├── file_service.py           # File handling
│   │   ├── validation.py             # CSV validation
│   │   ├── notification.py           # Email/webhook notifications
│   │   └── metrics.py                # Prometheus metrics
│   │
│   ├── workflows/                    # Temporal workflows
│   │   ├── __init__.py
│   │   ├── csv_workflow.py           # Main processing workflow
│   │   └── activities.py             # Temporal activities
│   │
│   └── utils/                        # Utility functions
│       ├── __init__.py
│       ├── logger.py                 # Logging configuration
│       └── helpers.py                # Helper functions
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures
│   ├── test_api.py                   # API endpoint tests
│   ├── test_validation.py            # Validation logic tests
│   ├── test_worker.py                # Worker tests
│   ├── test_integration.py           # Integration tests
│   └── fixtures/                     # Test data
│       └── sample.csv                # Sample CSV for testing
│
├── alembic/                          # Database migrations
│   ├── env.py                        # Alembic environment
│   ├── script.py.mako                # Migration template
│   └── versions/                     # Migration versions
│       └── 001_initial_tables.py     # Initial schema
│
├── docker/                           # Docker configuration
│   ├── Dockerfile.api                # API container
│   ├── Dockerfile.worker             # Worker container
│   └── temporal/                     # Temporal config
│       └── development-sql.yaml
│
├── monitoring/                       # Monitoring configuration
│   ├── prometheus.yml                # Prometheus config
│   └── grafana/                      # Grafana dashboards
│       └── dashboards/
│
├── docs/                             # Additional documentation
│   ├── API_USAGE.md                  # API usage guide
│   └── DEPLOYMENT.md                 # Deployment guide
│
├── .github/                          # GitHub configuration
│   └── workflows/                    # CI/CD pipelines
│       └── ci.yml                    # GitHub Actions workflow
│
├── docker-compose.yml                # Docker Compose configuration
│
└── uploads/                          # Temporary file storage (gitignored)
```

## Key Files Explained

### Configuration Files

- **`.env.example`**: Template for environment variables
- **`alembic.ini`**: Database migration configuration
- **`docker-compose.yml`**: Multi-container Docker application
- **`requirements.txt`**: Python package dependencies
- **`Makefile`**: Build and deployment shortcuts

### Application Core

- **`app/main.py`**: FastAPI application with middleware and routes
- **`app/config.py`**: Centralised configuration using Pydantic
- **`app/database.py`**: SQLAlchemy setup and session management
- **`app/models.py`**: Database table definitions
- **`app/schemas.py`**: Request/response validation schemas

### API Layer

- **`app/api/routes.py`**: REST endpoint implementations
- **`app/api/dependencies.py`**: Reusable dependency injection

### Business Logic

- **`app/services/file_service.py`**: File upload and storage
- **`app/services/validation.py`**: CSV validation logic
- **`app/services/notification.py`**: Email and webhook sending
- **`app/services/metrics.py`**: Prometheus metrics collection

### Workflow Engine

- **`app/workflows/csv_workflow.py`**: Temporal workflow definition
- **`app/workflows/activities.py`**: Individual workflow activities
- **`app/worker.py`**: Temporal worker process

### Testing

- **`tests/conftest.py`**: Shared test fixtures
- **`tests/test_*.py`**: Unit and integration tests

### Infrastructure

- **`docker/Dockerfile.api`**: API service container
- **`docker/Dockerfile.worker`**: Worker service container
- **`monitoring/prometheus.yml`**: Metrics collection config

## File Responsibilities

### Request Flow

1. **Client → `app/main.py`**: Request received by FastAPI
2. **`app/main.py` → `app/api/routes.py`**: Routed to handler
3. **`app/api/routes.py` → `app/services/`**: Business logic called
4. **`app/services/` → `app/database.py`**: Database operations
5. **`app/api/routes.py` → `app/workflows/`**: Temporal workflow started

### Processing Flow

1. **`app/worker.py`**: Worker polls Temporal
2. **`app/workflows/csv_workflow.py`**: Workflow orchestrates
3. **`app/workflows/activities.py`**: Activities execute
4. **`app/services/validation.py`**: CSV validated
5. **`app/models.py`**: Data persisted
6. **`app/services/notification.py`**: User notified

## Module Dependencies

```
app/main.py
├── app/api/routes.py
│   ├── app/services/file_service.py
│   ├── app/services/validation.py
│   └── app/workflows/csv_workflow.py
├── app/database.py
│   └── app/models.py
└── app/services/metrics.py

app/worker.py
├── app/workflows/csv_workflow.py
│   └── app/workflows/activities.py
│       ├── app/services/validation.py
│       ├── app/services/notification.py
│       ├── app/services/file_service.py
│       ├── app/database.py
│       └── app/models.py
└── app/config.py
```

## Adding New Features

### Adding a New API Endpoint

1. Define schema in `app/schemas.py`
2. Add route in `app/api/routes.py`
3. Add tests in `tests/test_api.py`

### Adding a New Workflow Activity

1. Define activity in `app/workflows/activities.py`
2. Use in workflow `app/workflows/csv_workflow.py`
3. Add tests in `tests/test_worker.py`

### Adding a New Service

1. Create file in `app/services/`
2. Import in relevant modules
3. Add unit tests in `tests/`

## Configuration Files Location

- **Application config**: `app/config.py`
- **Database config**: `app/database.py` + `alembic.ini`
- **Docker config**: `docker-compose.yml` + `docker/`
- **Monitoring config**: `monitoring/`
- **Environment variables**: `.env`

## Generated/Runtime Files (Not in Git)

```
uploads/                    # Uploaded CSV files
__pycache__/               # Python bytecode
*.pyc                      # Compiled Python
.pytest_cache/             # Pytest cache
htmlcov/                   # Coverage reports
.coverage                  # Coverage data
*.log                      # Log files
```

## Important Directories

- **`app/`**: All application code lives here
- **`tests/`**: All tests live here
- **`docker/`**: Docker build contexts
- **`monitoring/`**: Observability configuration
- **`docs/`**: User-facing documentation

## Entry Points

- **API Server**: `python -m app.main` or `uvicorn app.main:app`
- **Worker**: `python -m app.worker`
- **Tests**: `pytest`
- **Migrations**: `alembic upgrade head`

This structure follows best practises for Python applications with clear separation of concerns, easy testing, and scalable architecture.
