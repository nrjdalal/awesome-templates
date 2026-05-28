.PHONY: help setup quickstart demo demo-rag dev worker langfuse-env observability-langfuse observability-langfuse-down test lint format check check-core check-full check-minimal clean diagrams

LANGFUSE_ENV_FILE := _env/langfuse.env
MINIMAL_UV_ENV := /tmp/fastapi-agent-blueprint-minimal-venv

## Show available commands
help:
	@echo "Usage: make <command>"
	@echo ""
	@awk '/^## /{desc=substr($$0,4)} /^[a-zA-Z_-]+:/{if(desc){printf "  \033[36m%-32s\033[0m %s\n", $$1, desc; desc=""}}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help

## Setup development environment (includes admin + aws extras for full dev coverage)
setup:
	uv venv && uv sync --group dev --extra admin --extra aws && uv run pre-commit install && uv run pre-commit install --hook-type commit-msg

## Zero-config quickstart: SQLite + InMemory broker, no external infra
quickstart:
	@if [ ! -f _env/quickstart.env ]; then \
		echo "→ Creating _env/quickstart.env from template"; \
		cp _env/quickstart.env.example _env/quickstart.env; \
	fi
	@echo "→ Syncing dependencies (includes admin extra for the dashboard)"
	@uv sync --extra admin
	@echo "→ Starting FastAPI server on http://127.0.0.1:8001"
	@echo "  API docs:   http://127.0.0.1:8001/docs"
	@echo "  Admin:      http://127.0.0.1:8001/admin (admin / admin)"
	@echo "  Run demo:   make demo  (in another terminal)"
	@uv run python run_server_local.py --env quickstart

## Hit the running quickstart server with sample user requests
demo:
	@bash scripts/demo.sh

## End-to-end RAG showcase: seed 3 docs, list, run a query (needs quickstart server)
demo-rag:
	@bash scripts/demo-rag.sh

## Render architecture-diagrams.md Mermaid blocks to SVG (needs npx)
diagrams:
	@bash scripts/render-diagrams.sh

## Start local development (postgres + server)
dev:
	docker compose -f docker-compose.local.yml up -d postgres && \
	sleep 2 && \
	uv run alembic upgrade head && \
	uv run python run_server_local.py

## Start worker locally
worker:
	uv run python run_worker_local.py

## Start Taskiq scheduler locally — separate process from the worker; enqueues
## @broker.task schedule labels. Skip in deployments that prefer external cron.
scheduler:
	uv run python run_scheduler_local.py --env local

## Create local Langfuse env file with random secrets
langfuse-env: $(LANGFUSE_ENV_FILE)

$(LANGFUSE_ENV_FILE):
	@echo "→ Creating $(LANGFUSE_ENV_FILE) with local random secrets"
	@set -e; \
		mkdir -p "$(dir $(LANGFUSE_ENV_FILE))"; \
		tmp="$(LANGFUSE_ENV_FILE).tmp"; \
		trap 'rm -f "$$tmp"' 0; \
		rm -f "$$tmp"; \
		umask 077; \
		bash scripts/create-langfuse-env.sh > "$$tmp"; \
		chmod 600 "$$tmp"; \
		mv "$$tmp" "$(LANGFUSE_ENV_FILE)"

## Start the opt-in Langfuse observability stack
observability-langfuse: $(LANGFUSE_ENV_FILE)
	docker compose --env-file $(LANGFUSE_ENV_FILE) -f docker-compose.langfuse.yml up -d

## Stop the opt-in Langfuse observability stack
observability-langfuse-down: $(LANGFUSE_ENV_FILE)
	docker compose --env-file $(LANGFUSE_ENV_FILE) -f docker-compose.langfuse.yml down

## Run all tests (SQLite in-memory by default)
test:
	uv run pytest tests/ -v

## Run all tests against the local docker PostgreSQL (test_db -> postgresql)
test-pg:
	docker compose -f docker-compose.local.yml up -d postgres && \
	sleep 2 && \
	set -a && . _env/local.env && set +a && \
	TEST_DB_ENGINE=postgresql \
	TEST_DB_USER=postgres \
	TEST_DB_PASSWORD=postgres \
	TEST_DB_HOST=localhost \
	TEST_DB_PORT=5432 \
	TEST_DB_NAME=postgres \
	uv run pytest tests/ -v

## Run DynamoDB integration tests against local dynamodb-local
test-dynamo:
	docker compose -f docker-compose.local.yml up -d dynamodb-local && \
	sleep 2 && \
	set -a && . _env/local.env && set +a && \
	uv run pytest tests/integration/_core/infrastructure/persistence/nosql/dynamodb/ -v

## Run tests with coverage
test-cov:
	uv run pytest tests/ -v --cov=src --cov-report=term-missing

## Run linter
lint:
	uv run ruff check src/

## Run formatter
format:
	uv run ruff format src/

## Run fast local checks (lint + format check + core tests)
check-core:
	uv run ruff check src/ && \
	uv run ruff format --check src/ && \
	uv run pytest tests/ -v \
		--ignore=tests/unit/_core/infrastructure/persistence/nosql \
		--ignore=tests/integration

## Alias for fast local checks
check: check-core

## Run CI-parity checks (requires admin + aws extras and dynamodb-local)
check-full:
	uv sync --group dev --extra admin --extra aws && \
	docker compose -f docker-compose.local.yml up -d dynamodb-local && \
	sleep 2 && \
	uv run ruff check src/ && \
	uv run ruff format --check src/ && \
	uv run pytest tests/ -v

## Run no-extra minimal-install regression in an isolated uv environment
check-minimal:
	UV_PROJECT_ENVIRONMENT=$(MINIMAL_UV_ENV) uv sync --group dev && \
	UV_PROJECT_ENVIRONMENT=$(MINIMAL_UV_ENV) uv run pytest tests/integration/_core/test_minimal_install.py -v

## Run pre-commit on all files
pre-commit:
	uv run pre-commit run --all-files

## Run database migrations
migrate:
	uv run alembic upgrade head

## Generate new migration
migration:
	@read -p "Migration message: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"

## Clean up
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null; \
	rm -rf .coverage htmlcov/
