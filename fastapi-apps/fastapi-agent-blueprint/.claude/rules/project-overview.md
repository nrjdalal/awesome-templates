# Project Overview

> Last synced: 2026-08-12 via #380 (PR #389) — the admin dashboard is now **two columns** (`col-12 col-md-8` main + `col-12 col-md-4` aside), and the infrastructure panel is a compact status list rather than an AG Grid: `c.data_grid` is the list-page builder and brought `selection="single"`, i.e. row-selection radios on a panel with no row action. New tokens: `--admin-stat-card-min-width` (stat tiles sized to their own text came out ragged) and `.admin-status-dot` with two state hues. The onboarding view got the same two columns. Type checking is unrelated to this file's surface but see project-status for #381 / #375 / #387. Prior: 2026-08-12 via #368 (PRs #369, #370, #371, #373) — admin dashboard rework: new `DailyCount` VO added below; the dashboard's audit sections were removed in favour of what-is-wired-up / agent-call / growth sections, with a distinct onboarding view for the zero-data state and the infrastructure panel gated on the `accounts` permission. Prior: 2026-08-11 via #365/PR #366 (admin restyled to a **single neutral-mono theme** — a desaturated Tailwind zinc ramp, one blue accent `#2563eb` for interactive/active state, three status hues for outcomes, `8px`/`6px` rounding, hairline borders instead of elevation, flat login backdrop, `36px` grid rows, zebra striping off, and a system font stack replacing the bundled Wanted Sans woff2 — which also removed the `/admin-static` mount that existed only to serve it. Third token dict `_BRAND_TOKENS` added: the Quasar `--q-*` group must be emitted under `body` with `!important`, because NiceGUI writes that palette as an **inline body style** that outranks any `:root` rule — so from #193 until #365 the entire brand half of the palette was inert and every button/badge rendered NiceGUI's defaults. `--admin-login-gradient` renamed `--admin-login-bg`.) Prior: 2026-06-10 (admin theme reworked to a **single Toss-style theme** — the multi-preset machinery `ADMIN_THEME_PALETTE`/`_PALETTES`/`palette_primary` was removed; the look is now token dicts `_ROOT_TOKENS`/`_DARK_TOKENS` in `theme.py`. TDS grey palette + blue/green/red, light-mode chrome flip, 20px/pill rounding, dark-mode elevation ladder, per-mode login backdrop + login dark-mode toggle, global micro-interactions; plus an AG Grid `ag-delay-render` visibility fix). Prior: 2026-06-02 via #193 (admin UI/UX + design system). Admin shell is token-driven: `src/_core/infrastructure/admin/theme.py` (single theme + dark mode) + a `components/` builder library; pages compose builders (see `docs/ai/shared/admin-design-system.md`). Admin-shell settings in `config.py`: `ADMIN_DARK_MODE_DEFAULT` (None=follow OS), `ADMIN_BRAND_NAME`. Entrypoints unchanged.
> Prior: 2026-08-01 via #286/PR #313 + #315/PR #319 (Error Notification — severity channel routing added to Infrastructure Options, and the `Notification/Routing` group added to partial config group validation). Prior: 2026-07-28 via #310 (Error Notification — worker task-failure dispatch added; the server-only scope from PR #311 is superseded). Prior: 2026-07-27 via #307/PR #311 (Error Notification — runbook pointer + server-only dispatch scope added to Infrastructure Options). Prior: 2026-07-23 via #17/PR #304 (Error Notification optional infra — Slack/Discord webhook adapters + `NoopNotificationClient` fallback added to Infrastructure Options; `Notification (Slack/Discord)` added to partial config group validation).
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
- Error Notification: Optional (NOTIFICATION_PROVIDER env var, Slack/Discord webhook adapters via providers.Selector + NoopNotificationClient fallback; #17). Fired from the global exception handlers **and** from Taskiq worker task failures via `TaskFailureNotificationMiddleware` (#310); admin exceptions stay log-only by decision. Optional severity channel routing (#286): `NOTIFICATION_WARNING_THRESHOLD` — the sole switch — lowers the alerting floor to `min(severity, warning)` and routes that band to a second webhook, with `NOTIFICATION_CRITICAL_WEBHOOK_URL` / `NOTIFICATION_WARNING_WEBHOOK_URL` as per-tier overrides that fall back to the single target and are rejected at boot without the threshold (#315). Runbook: [`docs/operations/error-notifications.md`](../../docs/operations/error-notifications.md)
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
