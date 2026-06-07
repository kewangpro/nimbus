.PHONY: help infra infra-down docker-up docker-down docker-logs migrate backend worker frontend run stop ports clean-logs

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
	@echo "  make run            - Run API + Worker + Frontend locally in parallel with logging"
	@echo "  make stop           - Stop all local services and backend containers"
	@echo "  make clean-logs     - Remove all local log files"
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
		cd backend && while true; do ./venv/bin/python -m app.worker; echo "Worker exited. Restarting in 5 seconds..."; sleep 5; done; \
	else \
		cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt && while true; do ./venv/bin/python -m app.worker; echo "Worker exited. Restarting in 5 seconds..."; sleep 5; done; \
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
	@mkdir -p logs
	@echo "📋 Logs are being written to the 'logs/' directory."
	@make -j 3 backend-live worker-live frontend-live

backend-live:
	@make backend 2>&1 | tee logs/backend.log

worker-live:
	@make worker 2>&1 | tee logs/worker.log

frontend-live:
	@make frontend 2>&1 | tee logs/frontend.log

clean-logs:
	@echo "🧹 Cleaning up log files..."
	rm -rf logs/
	@echo "✅ Logs cleared."

stop:
	@echo "🛑 Stopping all running Nimbus services..."
	@make infra-down
	@port_8100_pid=$$(lsof -t -i:8100 2>/dev/null); \
	if [ -n "$$port_8100_pid" ]; then \
		echo "Killing FastAPI Backend (PID: $$port_8100_pid)..."; \
		kill -9 $$port_8100_pid 2>/dev/null || true; \
	fi
	@port_3100_pid=$$(lsof -t -i:3100 2>/dev/null); \
	if [ -n "$$port_3100_pid" ]; then \
		echo "Killing Next.js Frontend (PID: $$port_3100_pid)..."; \
		kill -9 $$port_3100_pid 2>/dev/null || true; \
	fi
	@worker_pids=$$(pgrep -f "app.worker" 2>/dev/null); \
	if [ -n "$$worker_pids" ]; then \
		echo "Killing Background Worker process(es)..."; \
		kill -9 $$worker_pids 2>/dev/null || true; \
	fi
	@echo "✅ All Nimbus services stopped."

ports:
	@echo "🔍 Nimbus Port Status:"
	@echo "------------------------------------------------"
	@printf "%-18s %-6s %-10s %s\n" "SERVICE" "PORT" "STATUS" "PROCESS/PID"
	@echo "------------------------------------------------"
	@for service in "Client Portal:3100" "FastAPI & MCP:8100" "PostgreSQL DB:5432" "Redis Cache:6379" "MinIO S3 API:9000" "MinIO Console:9001"; do \
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
