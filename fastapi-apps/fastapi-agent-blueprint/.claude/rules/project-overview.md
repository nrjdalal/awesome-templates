---
paths:
  - "src/_apps/**"
  - "src/_core/config.py"
  - "src/_core/infrastructure/di/**"
  - "_env/**"
  - "pyproject.toml"
  - "docker-compose*.yml"
  - "Makefile"
  - "run_*_local.py"
---

# Project Overview

> Last synced: 2026-11-06 via #414 B1/B4/B5
> For tech stack, refer to project-dna.md §8; for layer structure, refer to §1.
> For the Optional infra toggle surface (env var → disabled behavior per infra), see AGENTS.md "Optional Infrastructure Toggles" + [ADR 042](../../docs/history/042-optional-infrastructure-di-pattern.md).
> This file only contains **project-level context** not covered in project-dna.md.

## Purpose
AI Agent Backend Platform built on FastAPI with DDD modular layered architecture

## App Entrypoints
- Server: `src/_apps/server/` — FastAPI (uvicorn)
- Worker: `src/_apps/worker/` — Taskiq (broker abstraction: SQS/RabbitMQ/InMemory)
- Admin: `src/_apps/admin/` — NiceGUI (mounted on server via ui.run_with) — **mounted only when the `admin` extra is installed**; otherwise the server boots normally and emits only an `admin_mount_skipped` structured log line (#104). UI follows the admin design system (token theme + `components/` builders, #193).
- Scheduler: `src/_apps/worker/scheduler.py` — Taskiq `TaskiqScheduler` (`make scheduler` → `run_scheduler_local.py`). A **fourth runtime process**, not a fourth app package: it imports `worker.app` so `bootstrap_app` runs (middlewares + domain wiring) on the scheduler too, then enqueues tasks carrying a `schedule=[{"cron": ...}]` label. Today that is `audit_cleanup_task` (`0 3 * * *`), whose job is an **irreversible `DELETE`** bounded only by `AUDIT_LOG_RETENTION_DAYS`. The same `@broker.task` is also reachable from external cron / a k8s `CronJob` / a one-off REPL call, so the scheduler is optional rather than the only trigger
- AWS infrastructure (ObjectStorage/DynamoDB/S3Vectors) requires the `aws` extra. If the relevant env vars are unset, the lazy import never fires, so boot succeeds without the extra (#104 Part 2)

## Dependency Direction
Interface → Application → Domain ← Infrastructure

## Infrastructure Options
- RDB: PostgreSQL, MySQL, SQLite (DATABASE_ENGINE env var)
- DynamoDB: Optional (DYNAMODB_* env vars, BaseDynamoRepository)
- Object Storage: S3/MinIO (STORAGE_TYPE env var, parameter switching)
- S3 Vectors: Optional (S3VECTORS_* env vars, BaseS3VectorStore)
- Embedding: Optional (EMBEDDING_PROVIDER env var, PydanticAIEmbeddingAdapter — OpenAI/Bedrock/Google/Ollama)
- LLM: Optional (LLM_PROVIDER env var, build_llm_model() — OpenAI/Anthropic/Bedrock)
- Message Broker: SQS/RabbitMQ/InMemory (BROKER_TYPE env var)
- Error Notification: see [AGENTS.md § Optional Infrastructure Toggles](../../AGENTS.md#optional-infrastructure-toggles) + [runbook](../../docs/operations/error-notifications.md).
- Logging: structlog + asgi-correlation-id; default level INFO; controlled via `LOG_LEVEL` / `LOG_JSON_FORMAT` env vars (dev/local/quickstart → console, stg/prod → JSON, #9)

## Environment Config Validation
- Settings (pydantic-settings) with model_validator
- stg/prod: unsafe defaults blocked, broker required, partial config groups rejected
- STORAGE_TYPE-driven validation: S3/MinIO config group required when set
- VECTOR_STORE_TYPE-driven validation: unknown value rejected against `KNOWN_VECTOR_STORE_TYPES` (`inmemory`, `s3vectors`); `s3vectors` requires the full S3Vectors config group. Unset → `inmemory`, whose filter support is a strict subset of the S3 syntax (#328)
- Partial config group validation: S3, MinIO, DynamoDB, S3Vectors, SQS, Embedding (OpenAI/Bedrock), LLM (OpenAI/Anthropic/Bedrock), Notification (Slack/Discord), Notification/Routing (warning threshold below severity; per-tier webhook URL requires both a provider and the warning threshold)
- Logging: `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR), `LOG_JSON_FORMAT` (None → derive from ENV; True/False to force-override)

## Key Value Objects
- QueryFilter: Immutable filter for paginated queries (sort/search). Used in BaseRepository.select_datas_with_count() and BaseService.get_datas().
- DynamoKey: Composite key for DynamoDB (partition_key + optional sort_key). Used in BaseDynamoRepository operations.
- VectorQuery: Immutable vector similarity search query (vector, top_k, filters). Used in BaseS3VectorStore.search().
- VectorSearchResult: Vector search result container (items, distances, count). CursorPage counterpart for vector search.
- EmbeddingConfig: Immutable embedding configuration (model_name, dimension, credentials). Domain-layer VO for PydanticAI Embedder.
- LLMConfig: Immutable LLM configuration (model_name, credentials). Domain-layer VO for PydanticAI Agent.
- DailyCount: One day's record count from a date-grouped aggregate (#368). Returned by `BaseRepository.count_datas_by_day` / `BaseService.count_datas_by_day`. Days with no rows are **absent**, not zero-filled — gap-filling is a caller policy, so a chart fills them and an alerting consumer need not.
