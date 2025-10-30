.PHONY: help build up down restart logs test clean migrate shell

help:
	@echo "Available commands:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs"
	@echo "  make test        - Run tests"
	@echo "  make migrate     - Run database migrations"
	@echo "  make shell       - Open API container shell"
	@echo "  make clean       - Clean up containers and volumes"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "Services started! Access points:"
	@echo "  API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"
	@echo "  Temporal UI: http://localhost:8088"
	@echo "  RabbitMQ Management: http://localhost:15672"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3000"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker

test:
	docker-compose exec api pytest -v

test-coverage:
	docker-compose exec api pytest --cov=app --cov-report=html

migrate:
	docker-compose exec api alembic upgrade head

migrate-create:
	docker-compose exec api alembic revision --autogenerate -m "$(message)"

shell:
	docker-compose exec api /bin/bash

shell-db:
	docker-compose exec db psql -U postgres -d fileprocessing

clean:
	docker-compose down -v
	docker system prune -f

scale-workers:
	docker-compose up -d --scale worker=$(n)

install:
	pip install -r requirements.txt

lint:
	docker-compose exec api flake8 app/

format:
	docker-compose exec api black app/

dev:
	uvicorn app.main:app --reload --port 8000