.PHONY: help infra infra-down docker-up docker-down docker-logs migrate backend worker frontend run ports

# Default target when just running 'make'
.DEFAULT_GOAL := help

help:
	@echo " Nimbus Developer Workspace Helper"
	@echo "=========================================================="
	@echo "Available commands:"
	@echo "  make ports          - View active/free ports diagnostic dashboard"
	@echo "  make infra          - Start core services (DB, Redis, MinIO) in background"
	@echo "  make infra-down     - Stop core services"
	@echo "  make docker-up      - Rebuild and start all containers in Docker"
	@echo "  make docker-down    - Stop and remove all Docker containers"
	@echo "  make docker-logs    - Stream logs from all running Docker containers"
	@echo "  make migrate        - Run database migrations inside backend container"
	@echo "  make backend        - Launch the FastAPI API server locally"
	@echo "  make worker         - Launch the local background worker process"
	@echo "  make frontend       - Launch the Next.js frontend locally"
	@echo "  make run            - Run API + Worker + Frontend locally in parallel"
	@echo "=========================================================="

infra:
	@echo "🚀 Starting core infrastructure services..."
	docker compose up -d db redis minio

infra-down:
	@echo "🛑 Stopping core infrastructure services..."
	docker compose stop db redis minio

docker-up:
	@echo "⚡ Building and starting entire Nimbus app in Docker..."
	docker compose up -d --build

docker-down:
	@echo "🛑 Stopping all Nimbus Docker containers..."
	docker compose down

docker-logs:
	@echo "📋 Streaming Docker logs (press Ctrl+C to exit)..."
	docker compose logs -f --tail=100

migrate:
	@echo "🗄️ Running database migrations..."
	docker compose exec backend alembic upgrade head

backend:
	@echo "🐍 Starting FastAPI Backend locally on port 8100..."
	@if [ -d "backend/venv" ]; then \
		cd backend && ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload; \
	else \
		cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt && ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload; \
	fi

worker:
	@echo "⚙️ Starting Background Worker locally..."
	@if [ -d "backend/venv" ]; then \
		cd backend && ./venv/bin/python -m app.worker; \
	else \
		cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt && ./venv/bin/python -m app.worker; \
	fi

frontend:
	@echo "📦 Starting Next.js Frontend locally on port 3100..."
	@if [ -d "frontend/node_modules" ]; then \
		cd frontend && PORT=3100 npm run dev; \
	else \
		cd frontend && npm install && PORT=3100 npm run dev; \
	fi

run:
	@echo "🔥 Starting complete Nimbus app locally..."
	@make -j 3 backend worker frontend

ports:
	@echo "🔍 Nimbus Port Status:"
	@echo "------------------------------------------------"
	@printf "%-18s %-6s %-10s %s\n" "SERVICE" "PORT" "STATUS" "PROCESS/PID"
	@echo "------------------------------------------------"
	@for service in "Client Portal:3100" "FastAPI API:8100" "PostgreSQL DB:5432" "Redis Cache:6379" "MinIO S3 API:9000" "MinIO Console:9001"; do \
		name=$${service%%:*}; \
		port=$${service##*:}; \
		pid=$$(lsof -t -sTCP:LISTEN -i:$$port 2>/dev/null | head -n 1); \
		if [ -n "$$pid" ]; then \
			proc_path=$$(ps -p $$pid -o comm= 2>/dev/null || echo "Unknown"); \
			proc=$$(basename "$$proc_path" 2>/dev/null || echo "Unknown"); \
			printf "\033[32m%-18s %-6s %-10s\033[0m %s (PID: %s)\n" "$$name" "$$port" "ACTIVE" "$$proc" "$$pid"; \
		else \
			printf "\033[31m%-18s %-6s %-10s\033[0m -\n" "$$name" "$$port" "FREE"; \
		fi \
	done
	@# Check background worker separately since it does not listen on a port
	@worker_pid=$$(pgrep -f "app.worker" | head -n 1); \
	if [ -n "$$worker_pid" ]; then \
		proc_path=$$(ps -p $$worker_pid -o comm= 2>/dev/null || echo "Unknown"); \
		proc=$$(basename "$$proc_path" 2>/dev/null || echo "Unknown"); \
		printf "\033[32m%-18s %-6s %-10s\033[0m %s (PID: %s)\n" "Async Worker" "N/A" "ACTIVE" "$$proc" "$$worker_pid"; \
	else \
		printf "\033[31m%-18s %-6s %-10s\033[0m -\n" "Async Worker" "N/A" "OFFLINE"; \
	fi
	@echo "------------------------------------------------"
