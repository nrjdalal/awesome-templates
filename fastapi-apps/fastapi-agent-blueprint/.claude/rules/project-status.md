# Project Status

> Last synced: 2026-11-07 via v0.12.0 release

## Current Version Context
- Latest release: v0.12.0 (2026-11-07)
- Active domains: auth (customer JWT access/refresh token API, #4), user (reference domain — pure customer identity after #218; admin fields removed), admin_identity (admin/operator identity + separate JWT realm,
  #218/ADR 049), classification (prototype), docs (RAG consumer example, #80), ai_usage (usage ledger, #75)
- Contributor examples: `examples/todo/` (minimal CRUD, mirrors `src/user/` layout), `examples/blog/` (Protocol-based cross-domain DIP, #237), `examples/webhook_receiver/` (background worker task, #240),
  `examples/url_shortener/` (CRUD `link` domain + Taskiq cleanup worker sharing one `LinkService`, #239), `examples/simple_chatbot/` (first real-LLM example — stateless PydanticAI Agent, `StubChatbot` fallback, #249),
  `examples/chatbot_with_memory/` (multi-turn session memory replayed via PydanticAI `message_history`, `StubChatbotMemory` fallback, #255), `examples/chatbot_with_guardrails/` (shared runtime guardrails around a
  PydanticAI Agent — prompt-injection input block, #256), `examples/web_search_chatbot/` (real web search via PydanticAI `duckduckgo_search_tool()` + keyless `StubChatbot` fallback; new `pydantic-ai-duckduckgo` extra; DI
  selector keys off `settings.llm_model_name` alone, #259) — see [`examples/README.md`](../../examples/README.md)
- Infrastructure: RDB (PostgreSQL/MySQL/SQLite), DynamoDB, Storage (S3/MinIO), S3 Vectors, InMemory Vectors (quickstart; selected by `VECTOR_STORE_TYPE`, boot-validated since #328 — its filter support is a strict subset
  of the S3 syntax and raises rather than ignoring the rest), Embedding (PydanticAI + StubEmbedder fallback), LLM (PydanticAI Agent + TestModel stub fallback via `build_stub_llm_model`), RagPipeline (+ StubAnswerAgent),
  Broker (SQS/RabbitMQ/InMemory), Structured logging (structlog + asgi-correlation-id), JWT auth (HS256 v1), Error Notification (Slack/Discord webhook alerts from the HTTP exception handlers and Taskiq worker task
  failures + NoopNotificationClient fallback, #17/#310; optional severity channel routing via `NOTIFICATION_WARNING_THRESHOLD`, #286). All non-DB infras optional via `providers.Selector` + lazy factories (ADR 042).
  `nicegui` in `admin` extra, `boto3`/`aioboto3` in `aws` extra (#104). Admin identity is a separate bounded context with its own credential store + JWT realm (distinct secret/issuer/audience); NiceGUI admin login +
  page-level permissions backed by `admin_identity` (#218/ADR 049, supersedes the #154/#194 single-table model).

## Recent Major Changes (since v0.12.0)

> History:
> - [v0.11.2→v0.12.0 archive](../../docs/history/archive/project-status/project-status-v0.11.2-v0.12.0.md) (4 rows)
> - [through v0.11.2 archive](../../docs/history/archive/project-status/project-status-since-v0.11.1.md) (6 rows).
> - [v0.9.0→v0.11.0 archive](../../docs/history/archive/project-status/project-status-v0.9.0-v0.11.0.md) (13 rows)
> - [v0.8.0→v0.9.0 archive](../../docs/history/archive/project-status/project-status-v0.8.0-v0.9.0.md) (15 rows)
> - [v0.6.0→v0.8.0 archive](../../docs/history/archive/project-status/project-status-v0.6.0-v0.8.0.md) (14 rows)
> - [v0.5.0→v0.6.0 archive](../../docs/history/archive/project-status/project-status-v0.5.0-v0.6.0.md) (6 rows)
> - [v0.4.0→v0.5.0 archive](../../docs/history/archive/project-status/project-status-v0.4.0-v0.5.0.md) (18 rows)
> - [pre-v0.4.0 archive](../../docs/history/archive/project-status/project-status-pre-v0.4.0.md) (26 rows)

Narrative belongs in
`CHANGELOG.md [Unreleased]` and the PR body; this table is a <= 300 B row index.

| Feature | Issue | Impact |
|---------|-------|--------|

## Architecture Violation Status
- Domain → Infrastructure import: CLEAN
- Mapper class: CLEAN
- Entity pattern: CLEAN

## Not Yet Implemented
- Server-route RBAC for non-user `/v1/*` routes (admin-realm `require_admin` gates `/v1/user` reads + CUD via #199, re-pointed to the admin token realm in #218; admin-realm gating for other domains' `/v1/*` routes is still a follow-up)
- External admin IdP / SSO / MFA / SCIM and a physically separate admin database (documented extension point in ADR 049 / project-dna §17 IC-218-7, not implemented)
- File Upload (UploadFile)
- Rate Limiting (slowapi)
- WebSocket
