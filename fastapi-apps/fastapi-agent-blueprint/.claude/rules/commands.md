# Suggested Commands

> Last synced: 2026-07-20 via #293 (added `make perf-test` — Locust performance-test harness; requires a running server, see `docs/operations/performance-locust.md` — to the Test section). Prior: 2026-07-02 via #260 (added `make smoke-examples` — per-example cp→src boot smoke — and the `examples-copyflow` checker to Architecture Verification).
> Purpose: Quick reference for Claude Code when executing shell commands.
> Also referenced when running Skills.
> Default Flow context: see [`AGENTS.md` § Default Coding Flow](../../AGENTS.md#default-coding-flow). The commands below are consulted by the `implement` and `verify` steps; this file is **not** a primary entry point in the Default Flow.
> Makefile targets (`make dev`, `make test`, etc.) are available as shortcuts — see `AGENTS.md` Common Commands.

## Run
```bash
# Dev environment setup (includes admin + aws extras — #104)
make setup

# Zero-config quickstart (SQLite + InMemory broker, no external infra)
make quickstart
make demo            # in a second terminal — runs curl CRUD walkthrough
make demo-rag        # RAG end-to-end (seed 3 docs → list → query, #80)

# Local development (PostgreSQL via docker-compose.local.yml)
make dev
make worker

# Direct invocation (reference only)
uvicorn src._apps.server.app:app --reload --host 127.0.0.1 --port 8001
python run_server_local.py --env local
python run_worker_local.py --env local
```

## Test
```bash
pytest tests/ -v                          # SQLite in-memory (default, no infra)
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v
pytest tests/integration/ -v -k "dynamo"  # DynamoDB tests only (requires docker dynamodb-local)

# Local verification target split
make check         # fast local alias for check-core
make check-core    # lint + format check + core tests
make check-full    # CI-parity checks; requires admin + aws extras and dynamodb-local
make check-minimal # no-extra minimal-install regression
make smoke-examples # copy-flow smoke: every example boots after cp-to-src (#260)

# Locust performance-test harness (#3) — headless run against a LOCAL server.
# Start `make quickstart` first; overridable via PERF_HOST / PERF_USERS /
# PERF_SPAWN_RATE / PERF_RUN_TIME. Illustrative only, not wired into CI.
# See docs/operations/performance-locust.md.
make perf-test

# Run against real PostgreSQL (docker-compose.local.yml postgres service)
make test-pg
# or manually:
TEST_DB_ENGINE=postgresql \
  TEST_DB_USER=postgres TEST_DB_PASSWORD=postgres \
  TEST_DB_HOST=localhost TEST_DB_PORT=5432 TEST_DB_NAME=postgres \
  pytest tests/ -v

# Run DynamoDB integration tests against docker dynamodb-local
make test-dynamo
```

- `tests/conftest.py::test_db` switches engine via `TEST_DB_ENGINE` (default `sqlite`)
- `tests/e2e/conftest.py::_override_app_database` (autouse) swaps the running app's `CoreContainer.database` to `test_db` via `src._apps.server.testing.override_database()`, so e2e tests do not need real PostgreSQL
- `app.state.container` exposes the wired `DynamicContainer` for fixture overrides
- Test DI override public API: `from src._apps.server.testing import override_database, reset_database_override`

## Lint / Format
```bash
# pre-commit (ruff + mypy)
pre-commit run --all-files
```

## DB Migrations
```bash
alembic revision --autogenerate -m "{domain}: {description}"
alembic upgrade head
alembic downgrade -1
alembic current
alembic history
```

## Package Management (uv)
```bash
uv add <package>
uv sync                                          # core only
uv sync --group dev --extra admin --extra aws    # Dev default (same as make setup, #104)
uv sync --extra admin                            # NiceGUI admin dashboard only
uv sync --extra aws                              # S3/MinIO/DynamoDB/S3Vectors
uv sync --extra pydantic-ai --extra aws          # Bedrock LLM/Embedding (includes aioboto3)
```

## Architecture Diagrams
```bash
# Regenerate SVG exports under docs/assets/architecture/ from the
# Mermaid blocks in docs/ai/shared/architecture-diagrams.md. Required
# whenever that file is edited so CLI/non-Mermaid viewers stay in sync.
make diagrams
```

## Logging (structlog, #9)
```bash
# Log level / format tuning — shared by server and worker
LOG_LEVEL=DEBUG make dev
LOG_JSON_FORMAT=true make dev   # Force JSON renderer in dev too (for pipeline inspection)
LOG_JSON_FORMAT=false make dev  # Temporary console renderer in stg/prod for debugging
```

- Default: dev/local/quickstart → console, stg/prod → JSON (`settings.effective_log_json`)
- All new code uses `structlog.stdlib.get_logger(__name__)`
- `DATABASE_ECHO=true` is mapped to `logging.getLogger("sqlalchemy.engine").setLevel(INFO)` so the structlog pipeline emits each query exactly once

## Architecture Verification
```bash
# Verify no Domain → Infrastructure imports (should return nothing)
grep -r "from src._core.infrastructure" src/_core/domain/
grep -r "from src.*.infrastructure" src/*/domain/ --include="*.py"

# Verify no Entity pattern remnants (should return nothing)
grep -r "class.*Entity" src/ --include="*.py"

# Verify no Mapper classes (should return nothing)
grep -r "class.*Mapper" src/ --include="*.py"

# Verify examples have no absolute examples.* imports (copy-flow guard, #260)
uv run python tools/check_examples_copyflow.py
```

## DynamoDB Local
```bash
docker run -d -p 8000:8000 amazon/dynamodb-local
pytest tests/integration/ -v -k "dynamo"
```

## Broker
```bash
# A standalone worker requires a cross-process broker (RabbitMQ or SQS).
BROKER_TYPE=rabbitmq RABBITMQ_URL=amqp://guest:guest@localhost:5672/ python run_worker_local.py --env local
```

> `BROKER_TYPE=inmemory` (the dev/quickstart default) executes tasks **inline in the producer
> process**; `InMemoryBroker.listen()` raises, so it cannot back a standalone
> `run_worker_local.py`. Use RabbitMQ or SQS to run a separate worker process.

## Storage
```bash
STORAGE_TYPE=minio python run_server_local.py --env local
STORAGE_TYPE=s3 python run_server_local.py --env local
```

## Admin Dashboard
```bash
uv sync --extra admin   # install; → http://127.0.0.1:8001/admin
# Login: admin_identity-realm credential check (#218/ADR 049; separate from customer auth)
# Seed admin: ADMIN_BOOTSTRAP_USERNAME/EMAIL/PASSWORD env vars (idempotent on boot, into admin_identity)
# If not installed: server boots normally, emits admin_mount_skipped log

# UI theming (#193): single Toss-style theme — rebrand by editing token dicts in
# src/_core/infrastructure/admin/theme.py (no ADMIN_THEME_PALETTE setting).
ADMIN_BRAND_NAME="Acme Admin" uv run python run_server_local.py --env local  # header/login brand text
ADMIN_DARK_MODE_DEFAULT=true ...       # unset=follow OS; true/false to force initial light/dark
```
