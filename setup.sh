#!/bin/bash

# CSV File Processing Service Setup Script
# This script helps set up the development environment

set -e

echo "=========================================="
echo "CSV File Processing Service Setup"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✓ Docker and Docker Compose are installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✓ .env file created"
    echo "⚠ Please update the .env file with your actual configuration"
    echo ""
else
    echo "✓ .env file already exists"
    echo ""
fi

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p uploads
mkdir -p monitoring/grafana/dashboards
mkdir -p docker/temporal
mkdir -p alembic/versions
echo "✓ Directories created"
echo ""

# Create Temporal dynamic config file
echo "Creating Temporal configuration..."
mkdir -p docker/temporal
cat > docker/temporal/development-sql.yaml <<EOF
# Temporal dynamic configuration for development
EOF
echo "✓ Temporal configuration created"
echo ""

# Build Docker images
echo "Building Docker images..."
docker-compose build
echo "✓ Docker images built"
echo ""

# Start services
echo "Starting services..."
docker-compose up -d
echo "✓ Services started"
echo ""

# Wait for services to be ready
echo "Waiting for services to be ready (this may take a minute)..."
sleep 30

# Check if database is ready
echo "Checking database connection..."
max_attempts=10
attempt=0
until docker-compose exec -T db pg_isready -U postgres &> /dev/null || [ $attempt -eq $max_attempts ]; do
    attempt=$((attempt+1))
    echo "  Waiting for database... (attempt $attempt/$max_attempts)"
    sleep 5
done

if [ $attempt -eq $max_attempts ]; then
    echo "✗ Database failed to start"
    exit 1
fi
echo "✓ Database is ready"
echo ""

# Run migrations
echo "Running database migrations..."
docker-compose exec -T api alembic upgrade head
echo "✓ Migrations completed"
echo ""

# Display service URLs
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Service URLs:"
echo "  • API:                 http://localhost:8000"
echo "  • API Documentation:   http://localhost:8000/docs"
echo "  • Temporal UI:         http://localhost:8088"
echo "  • RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "  • Prometheus:          http://localhost:9090"
echo "  • Grafana:             http://localhost:3000 (admin/admin)"
echo ""
echo "Useful commands:"
echo "  • View logs:           docker-compose logs -f"
echo "  • Run tests:           make test"
echo "  • Stop services:       make down"
echo "  • Restart services:    make restart"
echo ""
echo "For more commands, run: make help"
echo ""