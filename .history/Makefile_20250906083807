# Makefile
.PHONY: build up down train test agent sample-data gradio clean logs help

# Default target
help:
	@echo "Available targets:"
	@echo "  build        - Build all Docker images"
	@echo "  up           - Start all services"
	@echo "  down         - Stop all services"
	@echo "  train        - Train ML model"
	@echo "  test         - Run tests"
	@echo "  agent        - Run email agent"
	@echo "  sample-data  - Generate sample email events"
	@echo "  gradio       - Start Gradio demo (dev mode)"
	@echo "  clean        - Clean up containers and volumes"
	@echo "  logs         - Show logs for all services"

# Build all images
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d
	@echo "Waiting for Elasticsearch to be ready..."
	@sleep 30
	@echo "Importing Kibana saved objects..."
	@bash scripts/bootstrap_kibana.sh

# Stop all services
down:
	docker-compose down

# Train ML model
train:
	docker-compose run --rm ml_train

# Run tests
test:
	docker-compose run --rm ml_train python -m pytest tests/ -v
	docker-compose run --rm agent python -m pytest tests/ -v

# Run email agent
agent:
	docker-compose run --rm agent python email_agent.py

# Generate sample data
sample-data:
	python scripts/generate_sample_logs.py

# Start Gradio demo
gradio:
	docker-compose --profile dev up gradio_demo

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# Show logs
logs:
	docker-compose logs -f

# Quick setup for development
dev-setup: build train up
	@echo "Development environment ready!"
	@echo "Kibana: http://localhost:5601"
	@echo "Elasticsearch: http://localhost:9200"
	@echo "API: http://localhost:8000"

# Production setup
prod-setup: build train
	docker-compose up -d elasticsearch kibana logstash filebeat elastalert
	@echo "Production services started!"

# Restart specific service
restart-%:
	docker-compose restart $*

# View service logs
logs-%:
	docker-compose logs -f $*
