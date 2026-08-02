# Project Overview

> Last synced: 2026-08-01 via #286/PR #313 + #315/PR #319 (Error Notification — severity channel routing added to Infrastructure Options, and the `Notification/Routing` group added to partial config group validation). Prior: 2026-07-28 via #310 (Error Notification — worker task-failure dispatch added; the server-only scope from PR #311 is superseded). Prior: 2026-07-27 via #307/PR #311 (Error Notification — runbook pointer + server-only dispatch scope added to Infrastructure Options). Prior: 2026-07-23 via #17/PR #304 (Error Notification optional infra — Slack/Discord webhook adapters + `NoopNotificationClient` fallback added to Infrastructure Options; `Notification (Slack/Discord)` added to partial config group validation).
> Prior: 2026-06-10 (admin theme reworked to a **single Toss-style theme** — the multi-preset machinery `ADMIN_THEME_PALETTE`/`_PALETTES`/`palette_primary` was removed; the look is now two token dicts `_ROOT_TOKENS`/`_DARK_TOKENS` in `theme.py`. TDS grey palette + blue/green/red, light-mode chrome flip, 20px/pill rounding, dark-mode elevation ladder, per-mode login backdrop + login dark-mode toggle, global micro-interactions; plus an AG Grid `ag-delay-render` visibility fix). Prior: 2026-06-02 via #193 (admin UI/UX + design system). Admin shell is token-driven: `src/_core/infrastructure/admin/theme.py` (single theme + dark mode + Wanted Sans) + a `components/` builder library; pages compose builders (see `docs/ai/shared/admin-design-system.md`). Admin-shell settings in `config.py`: `ADMIN_DARK_MODE_DEFAULT` (None=follow OS), `ADMIN_BRAND_NAME`. Entrypoints unchanged.
> Prior: 2026-06-01 via #218 (admin-identity realm separation; `ADMIN_JWT_*` settings + realm-collapse validation; admin login backed by `admin_identity`).
> For tech stack, refer to project-dna.md §8; for layer structure, refer to §1.
> For the Optional infra toggle surface (env var → disabled behavior per infra), see AGENTS.md "Optional Infrastructure Toggles" + [ADR 042](../../docs/history/042-optional-infrastructure-di-pattern.md).
> This file only contains **project-level context** not covered in project-dna.md.

## Purpose
AI Agent Backend Platform built on FastAPI with DDD modular layered architecture

## App Entrypoints
- Server: `src/_apps/server/` — FastAPI (uvicorn)
- Worker: `src/_apps/worker/` — Taskiq (broker abstraction: SQS/RabbitMQ/InMemory)
- Admin: `src/_apps/admin/` — NiceGUI (mounted on server via ui.run_with) — **mounted only when the `admin` extra is installed**; otherwise the server boots normally and emits only an `admin_mount_skipped` structured log line (#104). UI follows the admin design system (token theme + `components/` builders, #193).
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
- Error Notification: Optional (NOTIFICATION_PROVIDER env var, Slack/Discord webhook adapters via providers.Selector + NoopNotificationClient fallback; #17). Fired from the global exception handlers **and** from Taskiq worker task failures via `TaskFailureNotificationMiddleware` (#310); admin exceptions stay log-only by decision. Optional severity channel routing (#286): `NOTIFICATION_WARNING_THRESHOLD` — the sole switch — lowers the alerting floor to `min(severity, warning)` and routes that band to a second webhook, with `NOTIFICATION_CRITICAL_WEBHOOK_URL` / `NOTIFICATION_WARNING_WEBHOOK_URL` as per-tier overrides that fall back to the single target and are rejected at boot without the threshold (#315). Runbook: [`docs/operations/error-notifications.md`](../../docs/operations/error-notifications.md)
- Logging: structlog + asgi-correlation-id; default level INFO; controlled via `LOG_LEVEL` / `LOG_JSON_FORMAT` env vars (dev/local/quickstart → console, stg/prod → JSON, #9)

## Environment Config Validation
- Settings (pydantic-settings) with model_validator
- stg/prod: unsafe defaults blocked, broker required, partial config groups rejected
- STORAGE_TYPE-driven validation: S3/MinIO config group required when set
- Partial config group validation: S3, MinIO, DynamoDB, S3Vectors, SQS, Embedding (OpenAI/Bedrock), LLM (OpenAI/Anthropic/Bedrock), Notification (Slack/Discord), Notification/Routing (warning threshold below severity; per-tier webhook URL requires both a provider and the warning threshold)
- Logging: `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR), `LOG_JSON_FORMAT` (None → derive from ENV; True/False to force-override)

## Key Value Objects
- QueryFilter: Immutable filter for paginated queries (sort/search). Used in BaseRepository.select_datas_with_count() and BaseService.get_datas().
- DynamoKey: Composite key for DynamoDB (partition_key + optional sort_key). Used in BaseDynamoRepository operations.
- VectorQuery: Immutable vector similarity search query (vector, top_k, filters). Used in BaseS3VectorStore.search().
- VectorSearchResult: Vector search result container (items, distances, count). CursorPage counterpart for vector search.
- EmbeddingConfig: Immutable embedding configuration (model_name, dimension, credentials). Domain-layer VO for PydanticAI Embedder.
- LLMConfig: Immutable LLM configuration (model_name, credentials). Domain-layer VO for PydanticAI Agent.
