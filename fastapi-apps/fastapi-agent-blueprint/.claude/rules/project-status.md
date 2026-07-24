# Project Status

> Last synced: 2026-07-23 via /sync-guidelines after #17 (PR #304 — Error Notification webhooks, external contributor; first post-v0.9.0 feature. Review-detected drift closed: AGENTS.md Optional Infrastructure Toggles row, project-dna §8 row, `.claude/rules` files, `_env/*.example` NOTIFICATION_* blocks, `docs/reference.md` checkbox). Also reflects **v0.9.0 released** (2026-07-21 — Antigravity 2.0 harness, governance frameworks ADR 054/055/056, `web_search_chatbot` example, Locust perf harness; see CHANGELOG); the 15 pre-v0.9.0 rows are archived per the PR-B.1 pattern. Prior: 2026-07-20 via ADR 056 (Zero-Downtime Migration Safety). Prior: 2026-07-20 via #292 (Summary Finding Ledger).

## Current Version Context
- Latest release: v0.9.0 (2026-07-21)
- Active domains: auth (customer JWT access/refresh token API, #4), user (reference domain — pure customer identity after #218; admin fields removed), admin_identity (admin/operator identity + separate JWT realm, #218/ADR 049), classification (prototype), docs (RAG consumer example, #80), ai_usage (usage ledger, #75)
- Contributor examples: `examples/todo/` (minimal CRUD, mirrors `src/user/` layout), `examples/blog/` (Protocol-based cross-domain DIP, #237), `examples/webhook_receiver/` (background worker task, #240), `examples/url_shortener/` (CRUD `link` domain + Taskiq cleanup worker sharing one `LinkService`, #239), `examples/simple_chatbot/` (first real-LLM example — stateless PydanticAI Agent, `StubChatbot` fallback, #249), `examples/chatbot_with_memory/` (multi-turn session memory replayed via PydanticAI `message_history`, `StubChatbotMemory` fallback, #255), `examples/chatbot_with_guardrails/` (shared runtime guardrails around a PydanticAI Agent — prompt-injection input block, #256), `examples/web_search_chatbot/` (real web search via PydanticAI `duckduckgo_search_tool()` + keyless `StubChatbot` fallback; new `pydantic-ai-duckduckgo` extra; DI selector keys off `settings.llm_model_name` alone, #259) — see [`examples/README.md`](../../examples/README.md)
- Infrastructure: RDB (PostgreSQL/MySQL/SQLite), DynamoDB, Storage (S3/MinIO), S3 Vectors, InMemory Vectors (quickstart), Embedding (PydanticAI + StubEmbedder fallback), LLM (PydanticAI Agent + TestModel stub fallback via `build_stub_llm_model`), RagPipeline (+ StubAnswerAgent), Broker (SQS/RabbitMQ/InMemory), Structured logging (structlog + asgi-correlation-id), JWT auth (HS256 v1), Error Notification (Slack/Discord webhook alerts from the exception handlers + NoopNotificationClient fallback, #17). All non-DB infras optional via `providers.Selector` + lazy factories (ADR 042). `nicegui` in `admin` extra, `boto3`/`aioboto3` in `aws` extra (#104). Admin identity is a separate bounded context with its own credential store + JWT realm (distinct secret/issuer/audience); NiceGUI admin login + page-level permissions backed by `admin_identity` (#218/ADR 049, supersedes the #154/#194 single-table model).

## Recent Major Changes (since v0.9.0)

> History: [v0.8.0→v0.9.0 archive](../../docs/history/archive/project-status/project-status-v0.8.0-v0.9.0.md) (15 rows) · [v0.6.0→v0.8.0 archive](../../docs/history/archive/project-status/project-status-v0.6.0-v0.8.0.md) (14 rows) · [v0.5.0→v0.6.0 archive](../../docs/history/archive/project-status/project-status-v0.5.0-v0.6.0.md) (6 rows) · [v0.4.0→v0.5.0 archive](../../docs/history/archive/project-status/project-status-v0.4.0-v0.5.0.md) (18 rows) · [pre-v0.4.0 archive](../../docs/history/archive/project-status/project-status-pre-v0.4.0.md) (26 rows).

| Feature | Issue | Impact |
|---------|-------|--------|
| Error Notification Webhooks (contributor) | #17 (PR #304) | Adds optional error-notification core infra — the **first `src/` runtime feature after v0.9.0**. Slack/Discord webhook adapters + `NoopNotificationClient` fallback behind the ADR 042 Protocol + Selector pattern (`NOTIFICATION_PROVIDER` + matching webhook URL enable it; `BaseNotificationProtocol` in `_core/domain/protocols/`). `ErrorNotifier` gates by `NOTIFICATION_SEVERITY_THRESHOLD` (default 500) + a per-process, per-error_code `NOTIFICATION_COOLDOWN_SECONDS` (default 60) and dispatches fire-and-forget (`asyncio.create_task` — never awaited in the request path; send failures logged `exc_type`-only so the secret webhook URL never reaches logs). Hooked into `custom_exception_handler` + `generic_exception_handler` via `app.state.container` at runtime (no infra import in the exceptions module; dispatch never raises into the response path). Adapters POST via the shared `HttpClient` and never JSON-parse webhook responses (Slack success body is plain-text `ok`, Discord returns `204`). Settings validation follows the existing partial-config-group pattern (unknown provider / missing webhook URL rejected at boot, tested). Channel routing deferred to #286. 3-round review (Codex bot + 2 protocol rounds; all finding keys FIXED at merge). |

## Architecture Violation Status
- Domain → Infrastructure import: CLEAN
- Mapper class: CLEAN
- Entity pattern: CLEAN

## Not Yet Implemented
- Server-route RBAC for non-user `/v1/*` routes (admin-realm `require_admin` gates `/v1/user` reads + CUD via #199, re-pointed to the admin token realm in #218; admin-realm gating for other domains' `/v1/*` routes is still a follow-up)
- External admin IdP / SSO / MFA / SCIM and a physically separate admin database (documented extension point in ADR 049 / project-dna §17 IC-218-7, not implemented)
- Notification channel routing by severity — critical → #alerts, warnings → #monitoring (#286, follow-up split from #17)
- File Upload (UploadFile)
- Rate Limiting (slowapi)
- WebSocket
