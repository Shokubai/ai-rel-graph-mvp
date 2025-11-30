.PHONY: help install setup dev test clean docker-up docker-down docker-logs docker-rebuild db-migrate db-rollback backend-test frontend-test format lint

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(CYAN)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# === Setup Commands ===

install: ## Install all dependencies (backend + frontend)
	@echo "$(CYAN)Installing backend dependencies...$(NC)"
	cd backend && poetry install
	@echo "$(GREEN)✓ Backend dependencies installed$(NC)"
	@echo "$(CYAN)Installing frontend dependencies...$(NC)"
	cd frontend && pnpm install
	@echo "$(GREEN)✓ Frontend dependencies installed$(NC)"

setup: ## Initial project setup (copy env files, install deps)
	@echo "$(CYAN)Setting up project...$(NC)"
	@if [ ! -f backend/.env ]; then \
		cp backend/.env.example backend/.env; \
		echo "$(GREEN)✓ Created backend/.env$(NC)"; \
	fi
	@if [ ! -f frontend/.env.local ]; then \
		cp frontend/.env.local.example frontend/.env.local; \
		echo "$(GREEN)✓ Created frontend/.env.local$(NC)"; \
	fi
	@$(MAKE) install
	@echo "$(GREEN)✓ Project setup complete!$(NC)"

# === Development Commands ===

dev-backend: ## Run backend in development mode (local, no Docker)
	cd backend && poetry run uvicorn app.main:app --reload

dev-frontend: ## Run frontend in development mode (local, no Docker)
	cd frontend && pnpm dev

# === Docker Commands ===

docker-up: ## Start all Docker services (development)
	@echo "$(CYAN)Starting Docker services (development)...$(NC)"
	docker compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@$(MAKE) docker-status

docker-down: ## Stop all Docker services
	@echo "$(CYAN)Stopping Docker services...$(NC)"
	docker compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

docker-up-prod: ## Start all Docker services (production)
	@echo "$(CYAN)Starting Docker services (production)...$(NC)"
	docker compose -f docker-compose.prod.yml up -d --build
	@echo "$(GREEN)✓ Production services started$(NC)"
	@$(MAKE) docker-status-prod

docker-down-prod: ## Stop production Docker services
	@echo "$(CYAN)Stopping production Docker services...$(NC)"
	docker compose -f docker-compose.prod.yml down
	@echo "$(GREEN)✓ Production services stopped$(NC)"

docker-status-prod: ## Check status of production Docker services
	@echo "$(CYAN)Production Docker Services Status:$(NC)"
	@docker compose -f docker-compose.prod.yml ps

docker-logs-prod: ## Show logs from production services
	docker compose -f docker-compose.prod.yml logs -f

docker-logs-backend-prod: ## Show production backend logs
	docker compose -f docker-compose.prod.yml logs -f backend

docker-restart-prod: ## Restart production services
	@echo "$(CYAN)Restarting production services...$(NC)"
	docker compose -f docker-compose.prod.yml restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

docker-logs: ## Show logs from all services
	docker compose logs -f

docker-logs-backend: ## Show backend logs
	docker compose logs -f backend

docker-logs-frontend: ## Show frontend logs
	docker compose logs -f frontend

docker-rebuild: ## Rebuild and restart all Docker services
	@echo "$(CYAN)Rebuilding Docker services...$(NC)"
	docker compose up -d --build
	@echo "$(GREEN)✓ Services rebuilt$(NC)"

docker-clean: ## Remove all Docker containers, volumes, and images
	@echo "$(YELLOW)WARNING: This will remove all containers, volumes, and images$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		docker system prune -af; \
		echo "$(GREEN)✓ Docker cleaned$(NC)"; \
	fi

docker-status: ## Check status of Docker services
	@echo "$(CYAN)Docker Services Status:$(NC)"
	@docker compose ps

docker-shell-backend: ## Open shell in backend container
	docker compose exec backend /bin/bash

docker-shell-frontend: ## Open shell in frontend container
	docker compose exec frontend /bin/sh

# === Database Commands ===

db-migrate: ## Create a new database migration
	@read -p "Migration message: " msg; \
	cd backend && poetry run alembic revision --autogenerate -m "$$msg"

db-upgrade: ## Run database migrations
	cd backend && poetry run alembic upgrade head

db-downgrade: ## Rollback last migration
	cd backend && poetry run alembic downgrade -1

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "$(RED)WARNING: This will destroy all data in the database$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v postgres; \
		docker compose up -d postgres; \
		sleep 5; \
		$(MAKE) db-upgrade; \
		echo "$(GREEN)✓ Database reset$(NC)"; \
	fi

db-shell: ## Open PostgreSQL shell (development)
	docker compose exec postgres psql -U postgres -d semantic_graph

db-shell-prod: ## Open PostgreSQL shell (production)
	docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d semantic_graph

db-upgrade-prod: ## Run database migrations in production
	@echo "$(CYAN)Running production database migrations...$(NC)"
	docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
	@echo "$(GREEN)✓ Migrations complete$(NC)"

# === Testing Commands ===

test: ## Run all tests
	@echo "$(CYAN)Running all tests...$(NC)"
	@$(MAKE) backend-test || echo "$(RED)Backend tests failed$(NC)"
	@$(MAKE) frontend-test || echo "$(RED)Frontend tests failed$(NC)"

backend-test: ## Run backend tests
	@echo "$(CYAN)Running backend tests...$(NC)"
	cd backend && poetry run pytest
	@echo "$(GREEN)✓ Backend tests complete$(NC)"

backend-test-cov: ## Run backend tests with coverage report
	@echo "$(CYAN)Running backend tests with coverage...$(NC)"
	cd backend && poetry run pytest --cov=app --cov-report=html
	@echo "$(GREEN)✓ Coverage report generated at backend/htmlcov/index.html$(NC)"

frontend-test: ## Run frontend tests
	@echo "$(CYAN)Running frontend tests...$(NC)"
	cd frontend && pnpm test
	@echo "$(GREEN)✓ Frontend tests complete$(NC)"

# === Code Quality Commands ===

format: ## Format all code (black, prettier)
	@echo "$(CYAN)Formatting backend code...$(NC)"
	cd backend && poetry run black .
	@echo "$(CYAN)Formatting frontend code...$(NC)"
	cd frontend && pnpm exec prettier --write .
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint: ## Lint all code (ruff, eslint)
	@echo "$(CYAN)Linting backend...$(NC)"
	cd backend && poetry run ruff check .
	@echo "$(CYAN)Linting frontend...$(NC)"
	cd frontend && pnpm lint
	@echo "$(GREEN)✓ Linting complete$(NC)"

typecheck: ## Run type checking
	@echo "$(CYAN)Type checking backend...$(NC)"
	cd backend && poetry run mypy app
	@echo "$(CYAN)Type checking frontend...$(NC)"
	cd frontend && pnpm exec tsc --noEmit
	@echo "$(GREEN)✓ Type checking complete$(NC)"

check: format lint typecheck test ## Run all quality checks

# === Utility Commands ===

clean: ## Clean temporary files and caches
	@echo "$(CYAN)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	cd frontend && rm -rf .next 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

health-check: ## Check if all services are healthy (development)
	@echo "$(CYAN)Checking service health...$(NC)"
	@echo -n "Backend API: "
	@curl -s http://localhost:8000/health > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "Frontend: "
	@curl -s http://localhost:80 > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "PostgreSQL: "
	@docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "Redis: "
	@docker compose exec -T redis redis-cli ping > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"

health-check-prod: ## Check if production services are healthy
	@echo "$(CYAN)Checking production service health...$(NC)"
	@echo -n "Backend API: "
	@curl -s http://localhost:8000/health > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "Frontend: "
	@curl -s http://localhost:80 > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "PostgreSQL: "
	@docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"
	@echo -n "Redis: "
	@docker compose -f docker-compose.prod.yml exec -T redis redis-cli ping > /dev/null 2>&1 && echo "$(GREEN)✓$(NC)" || echo "$(RED)✗$(NC)"

urls: ## Show all service URLs
	@echo "$(CYAN)Service URLs:$(NC)"
	@echo "  Frontend:        $(GREEN)http://localhost$(NC)"
	@echo "  Backend API:     $(GREEN)http://localhost:8000$(NC)"
	@echo "  API Docs:        $(GREEN)http://localhost:8000/docs$(NC)"
	@echo "  PostgreSQL:      $(GREEN)localhost:5432$(NC)"
	@echo "  Redis:           $(GREEN)localhost:6379$(NC)"

# === Demo Commands ===

demo: ## Run demo with 11 realistic documents
	@echo "$(CYAN)Running demo with 11 realistic documents...$(NC)"
	docker exec ai-rel-graph-backend python demo.py

demo-large: ## Run demo with 100 synthetic documents
	@echo "$(CYAN)Running demo with 100 synthetic documents...$(NC)"
	docker exec ai-rel-graph-backend python demo.py --large

demo-kaggle: ## Run demo with 50 real Kaggle PDFs
	@echo "$(CYAN)Running demo with 50 Kaggle PDFs...$(NC)"
	@echo "$(YELLOW)No credentials needed - downloads public PDFs automatically$(NC)"
	docker exec ai-rel-graph-backend python demo.py --kaggle 50

demo-kaggle-large: ## Run demo with 500 Kaggle PDFs
	@echo "$(CYAN)Running demo with 500 Kaggle PDFs...$(NC)"
	docker exec ai-rel-graph-backend python demo.py --kaggle 500

demo-custom: ## Run demo with custom number of Kaggle PDFs (usage: make demo-custom NUM=75)
	@if [ -z "$(NUM)" ]; then \
		echo "$(RED)Error: NUM not specified$(NC)"; \
		echo "Usage: make demo-custom NUM=75"; \
		exit 1; \
	fi
	@echo "$(CYAN)Running demo with $(NUM) Kaggle PDFs...$(NC)"
	docker exec ai-rel-graph-backend python demo.py --kaggle $(NUM)

demo-min-tags: ## Run demo with custom threshold (usage: make demo-threshold TAGS=0.6)
	@if [ -z "$(TAGS)" ]; then \
		echo "$(RED)Error: TAGS not specified$(NC)"; \
		echo "Usage: make demo-threshold TAGS=0.6"; \
		exit 1; \
	fi
	@echo "$(CYAN)Running demo with threshold $(TAGS)...$(NC)"
	docker exec ai-rel-graph-backend python demo.py --kaggle 50 --min-tags $(TAGS)
# === Visualization Commands ===

visualize: ## Visualize graph with spring layout
	@echo "$(CYAN)Generating spring layout visualization...$(NC)"
	docker exec ai-rel-graph-backend python visualize_graph.py --layout spring --save graph_spring.png
	@echo "$(GREEN)✓ Created graph_spring.png$(NC)"

visualize-circular: ## Visualize graph with circular cluster layout
	@echo "$(CYAN)Generating circular cluster layout...$(NC)"
	docker exec ai-rel-graph-backend python visualize_graph.py --layout circular --save graph_circular.png
	@echo "$(GREEN)✓ Created graph_circular.png$(NC)"

visualize-stats: ## Show graph statistics
	@echo "$(CYAN)Generating statistics visualization...$(NC)"
	docker exec ai-rel-graph-backend python visualize_graph.py --stats --save graph_stats.png
	@echo "$(GREEN)✓ Created graph_stats.png$(NC)"

visualize-all: ## Generate all visualizations (spring, circular, stats)
	@echo "$(CYAN)Generating all visualizations...$(NC)"
	docker exec ai-rel-graph-backend python visualize_graph.py --all
	@echo "$(GREEN)✓ Created graph_spring.png, graph_circular.png, graph_stats.png$(NC)"
