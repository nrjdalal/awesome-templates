# Suggested Commands

> Last synced: 2026-11-06 via #414 B1/B4/B5
> Purpose: Consulted shell-command reference for Claude, Codex, and Antigravity; load when needed.
> Also referenced when running Skills.
> Default Flow context: see [`AGENTS.md` § Default Coding Flow](../../../AGENTS.md#default-coding-flow). The commands below are consulted by the `implement` and `verify` steps; this file is **not** a primary entry point in the Default Flow.
> Makefile targets are shortcuts; shared policy remains in [AGENTS.md](../../../AGENTS.md).

## Run
```bash
# Dev environment setup (includes admin + aws extras — #104)
make setup

# Bootstrap a fresh git worktree — copies gitignored _env/*.env from the main
# checkout and installs the admin/aws extras (not in uv's default sync).
# Idempotent and agent-agnostic. `paseo.json` calls it from its post-create
# hook; tools that read `.worktreeinclude` (Claude Code, Conductor, Roo Code,
# CodeBuddy) copy the env files themselves but still need the extras.
make worktree-setup

# Zero-config quickstart (SQLite + InMemory broker, no external infra).
# NOTE: this runs `uv sync --extra admin`, so every *other* extra is uninstalled
# (aws, otel, pydantic-ai, sqs, rabbitmq). The `dev` group survives — uv syncs
# default groups regardless of `--extra` — so the damage is not to test tooling
# but to what it can import: `pytest tests/` aborts during collection (two modules
# import `aioboto3`) and `uv run pyright` reports 47 unresolved imports. The target
# prints a restore hint when it detects a dev environment; re-run `make setup`.
make quickstart
make demo            # in a second terminal — curl CRUD walkthrough
make demo-rag        # RAG end-to-end (seed 3 docs → list → query, #80)
# demo.sh cannot reach /v1/user* with a curl-obtained token: those routes are
# admin-realm (#199/#218), and the ADMIN_BOOTSTRAP_* credential is setup-only.
# It shells out to `scripts/seed_demo_admin.py` first, which creates a real
# admin the way the NiceGUI setup wizard would, then POSTs /v1/admin/login.
# That script refuses to run outside quickstart/local.
# Both scripts assert every response envelope and exit non-zero on the first
# response that is not `success: true` — do not convert a `check` call back to
# a bare `run "curl ... | pretty"`, which is what let them pass while broken.
# CI job `demo-smoke` boots quickstart and runs both on every PR.

# Local development (PostgreSQL via docker-compose.local.yml)
make dev
make worker

# Taskiq scheduler — a FOURTH process, separate from the worker. Actually runs
# since #375: `run_scheduler` is a coroutine function and the call was not
# awaited, so this target used to exit 0 having scheduled nothing. Enqueues tasks
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

# Run against real PostgreSQL (docker-compose.local.yml postgres service).
# Works against a database that already holds the schema since #374 — before that
# fix, a partial `Base.metadata` (whatever the selected tests happened to import)
# made the fixture's drop_all die on the refresh_token -> user FK, and every test
# errored at setup. `tests/conftest.py` now calls `load_models()` so metadata is
# complete regardless of test selection; do not remove that call.
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
# pre-commit (ruff check --fix + ruff format + the local policy hooks)
pre-commit run --all-files

# Type check — pyright is the single authority, blocking in CI. This is exactly
# what the `typecheck` job runs; scope is [tool.pyright] include in pyproject.toml.
# There is no mypy hook: the manual-stage one was retired in #375 because it
# aborted on a duplicate module name and inspected no source at all.
uv run pyright
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

## Demo Recording
```bash
# Re-record docs/assets/cast/demo.gif from docs/assets/cast/demo.tape.
# Required whenever scripts/demo.sh changes — the GIF is a build artefact of
# the tape, and it silently outlived the API it depicted once already.
# Needs `vhs` (brew install vhs) + `ffmpeg`. Stop any server on :8001 first:
# the tape boots its own quickstart server and resets ./quickstart.db.
# Do NOT run bare `vhs` — the raw output is ~1.7MB, over the pre-commit asset
# ceiling; the target palette-re-encodes it and fails if it misses budget.
make demo-gif
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

# Verify every relative markdown link and #anchor resolves (#408). Blocking on
# every commit via the `doc-links` pre-commit hook, so the reason to run it by
# hand is to check inbound pointers BEFORE moving a file or renaming a heading —
# the failure it exists for is silent, and both halves of it shipped undetected
# (eight links in #405, two anchors orphaned by a README restructure in #79).
# No argv = full repo; pass paths to check only those files.
uv run python tools/check_doc_links.py

# Sensitive logging production-source lexical gate (ADR 061).
# Review false positives before a deliberate SKIP=sensitive-logging bypass;
# skipping is not a passing logging check. See CONTRIBUTING.md.
uv run pre-commit run sensitive-logging --all-files

# Check tracked harness byte budgets (blocking context-budget hook, ADR 059)
uv run python tools/check_context_budget.py

# Check generated harness inventory and reviewed buckets (blocking, ADR 062)
uv run python tools/generate_harness_inventory.py --check

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
Error Notification: see [AGENTS.md § Optional Infrastructure Toggles](../../../AGENTS.md#optional-infrastructure-toggles) + [runbook](../../operations/error-notifications.md).

## Admin Dashboard
```bash
uv sync --extra admin   # install; → http://127.0.0.1:8001/admin
# Login: admin_identity-realm credential check (#218/ADR 049; separate from customer auth)
# Seed admin: ADMIN_BOOTSTRAP_USERNAME/EMAIL/PASSWORD env vars (idempotent on boot, into admin_identity)
# If not installed: server boots normally, emits admin_mount_skipped log

# UI theming (#193, restyled in #365): single neutral-mono theme — a desaturated
# Tailwind zinc ramp with one blue accent. Rebrand by editing the token dicts in
# src/_core/infrastructure/admin/theme.py (no ADMIN_THEME_PALETTE setting);
# changing AdminColors.PRIMARY is usually enough. Note the `--q-*` brand group
# must stay under `body` with `!important` — NiceGUI sets it as an inline body
# style, so a `:root` declaration is inert (that was the pre-#365 state).
ADMIN_BRAND_NAME="Acme Admin" uv run python run_server_local.py --env local  # header/login brand text
ADMIN_DARK_MODE_DEFAULT=true ...       # unset=follow OS; true/false to force initial light/dark
```

## Codex Healthcheck

Run from a trusted checkout. The default 32 KiB project-doc cap truncates silently;
assert the final section instead of a head marker. The explicit default cap tests
the lean constitution, while project config provides a 64 KiB fallback.

```bash
codex mcp list
codex mcp get context7
codex debug prompt-input -c 'project_doc_max_bytes=32768' "healthcheck" | rg -o '## Drift Management'
codex execpolicy check --rules .codex/rules/fastapi-agent-blueprint.rules git push origin main
```

Context7 setup / trust troubleshooting: [CONTRIBUTING.md](../../../CONTRIBUTING.md#codex-minimum-setup).
