# Suggested Commands

> Last synced: 2026-08-01 via #286/PR #313 + #315/PR #319 (Error Notification — severity channel routing section and example added; `:159` corrected, it had contradicted the Coverage bullet in the same block since #310). Prior: 2026-07-28 via #310 (Error Notification — dispatch extended to Taskiq worker task failures; the server-only scope note from PR #311 is superseded). Prior: 2026-07-27 via #307/PR #311 (Error Notification section — runbook pointer, server-only dispatch scope, first-dispatch disabled warning). Prior: 2026-07-23 via #17/PR #304 (added the Error Notification section — `NOTIFICATION_*` env vars for Slack/Discord webhook alerts fired from the exception handlers). Prior: 2026-07-20 via ADR 056 (added `tools/check_migration_safety.py` — advisory unsafe-DDL scan for zero-downtime migrations — to Architecture Verification + DB Migrations). Prior: 2026-07-20 via #293 (added `make perf-test` — Locust performance-test harness — to the Test section).
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

# Taskiq scheduler — a FOURTH process, separate from the worker. Enqueues tasks
# carrying a `schedule=[{"cron": ...}]` label; today that is audit_cleanup_task
# (`0 3 * * *`), whose job is an irreversible DELETE bounded only by
# AUDIT_LOG_RETENTION_DAYS. Optional: the same @broker.task is also reachable
# from external cron, a k8s CronJob, or a one-off REPL call.
make scheduler

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

# After autogenerate, scan the new revision for unsafe (non-zero-downtime) DDL.
# Advisory only (ADR 056) — see docs/operations/rdb-migrations.md.
uv run python tools/check_migration_safety.py migrations/versions/<rev>.py
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

# Scan Alembic revisions for unsafe (non-zero-downtime) DDL — advisory (ADR 056)
uv run python tools/check_migration_safety.py
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

## Error Notification (#17, #310, #286)
```bash
# Slack/Discord webhook alerts fired from the HTTP exception handlers and Taskiq worker task failures (optional infra, ADR 042)
NOTIFICATION_PROVIDER=slack SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T/B/X python run_server_local.py --env local
NOTIFICATION_PROVIDER=discord DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/<id>/<token> python run_server_local.py --env local

# Severity channel routing (#286) — the threshold is the switch; the two URLs alone are rejected at boot
NOTIFICATION_PROVIDER=slack SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T/B/BASE \
  NOTIFICATION_WARNING_THRESHOLD=400 \
  NOTIFICATION_CRITICAL_WEBHOOK_URL=https://hooks.slack.com/services/T/B/ALERTS \
  NOTIFICATION_WARNING_WEBHOOK_URL=https://hooks.slack.com/services/T/B/MONITORING \
  python run_server_local.py --env local
```

- Tuning: `NOTIFICATION_SEVERITY_THRESHOLD` (default 500 — 5xx only, and the critical-tier boundary once routing is on), `NOTIFICATION_COOLDOWN_SECONDS` (default 60; per-process, keyed on `error_code` — `{tier}:{error_code}` under routing, `{tier}:{task_name}:{error_code}` on the worker)
- Channel routing (#286): `NOTIFICATION_WARNING_THRESHOLD` (unset by default) is the **sole switch** — it lowers the alerting floor to `min(severity, warning)` and routes that band to `NOTIFICATION_WARNING_WEBHOOK_URL`. Each per-tier URL falls back to the single provider webhook when unset, and setting one *without* the threshold fails at boot (#315)
- Unset provider → `NoopNotificationClient` (one-time `notification_client_disabled` warning, logged at the first dispatch attempt rather than at boot; no alerts delivered)
- Webhook URLs are credentials — keep them in gitignored env files only
- Coverage: HTTP exception handlers + Taskiq worker task failures (#310). Worker alerts fire once per incident on the terminal failure — permanent errors immediately, retryable ones after the last attempt
- Not alerted: `validation_exception_handler` (422), `http_exception_handler` (incl. a hand-raised 500), and NiceGUI admin exceptions (log-only, stated non-goal in AGENTS.md)
- Operator runbook (setup, coverage limits, cooldown/payload caveats, local-sink verification): [`docs/operations/error-notifications.md`](../../docs/operations/error-notifications.md)

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
