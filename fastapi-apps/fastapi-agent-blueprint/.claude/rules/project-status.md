# Project Status

> Last synced: 2026-05-27 via #195 (centralized admin error handling)

## Current Version Context
- Latest release: v0.6.0 (2026-05-07)
- Active domains: auth (JWT access/refresh token API, #4), user (reference domain — `User.role` + page-level `User.permissions` for admin RBAC, #154/#194), classification (prototype), docs (RAG consumer example, #80), ai_usage (usage ledger, #75)
- Contributor examples: `examples/todo/` (minimal CRUD, mirrors `src/user/` layout — see [`examples/README.md`](../../examples/README.md))
- Infrastructure: RDB (PostgreSQL/MySQL/SQLite), DynamoDB, Storage (S3/MinIO), S3 Vectors, InMemory Vectors (quickstart), Embedding (PydanticAI + StubEmbedder fallback), LLM (PydanticAI Agent + TestModel stub fallback via `build_stub_llm_model`), RagPipeline (+ StubAnswerAgent), Broker (SQS/RabbitMQ/InMemory), Structured logging (structlog + asgi-correlation-id), JWT auth (HS256 v1). All non-DB infras optional via `providers.Selector` + lazy factories (ADR 042). `nicegui` in `admin` extra, `boto3`/`aioboto3` in `aws` extra (#104). NiceGUI admin login backed by auth-domain credential check + DB-backed `User.role` + page-level `User.permissions` RBAC (#154/#194).

## Recent Major Changes (since v0.5.0)

> History: [v0.4.0→v0.5.0 archive](../../docs/history/archive/project-status/project-status-v0.4.0-v0.5.0.md) (18 rows) · [pre-v0.4.0 archive](../../docs/history/archive/project-status/project-status-pre-v0.4.0.md) (26 rows).

| Feature | Issue | Impact |
|---------|-------|--------|
| JWT Authentication Domain | #4 | Adds `src/auth/` with HS256 access/refresh tokens, DB-backed refresh-token rotation/revocation, `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/auth/me`, and Bearer protection for existing `user` API routes. NiceGUI admin auth was env-var based at #4 landing time; superseded by #154 (PR #155). |
| NiceGUI Admin JWT + Minimal RBAC | #154 (PR #155) | Migrates NiceGUI admin login from `ADMIN_ID`/`ADMIN_PASSWORD` to auth-domain credential check + DB-backed admin role checks. Adds `user.role` field (`UserRole` enum, default `USER_ROLE_USER`) and idempotent `ADMIN_BOOTSTRAP_*` admin seeding. Token-free NiceGUI session metadata preserves #4 JWT claim shape. |
| /docs Selector Revamp + Frontend Handoff | #156 | Replaces purple AI-styled selector with GitHub-flavoured Minimal layout + light/dark toggle. Adds `GET /openapi-download.json` and `docs/frontend-handoff.md` (camelCase serialization, `SuccessResponse` envelope, RDB/cursor pagination shapes, JWT auth flow, CORS, breaking-change signals, Postman/Bruno/Hey API/Orval recipes). |
| Governor-Review Provenance Consolidation | #157 (ADR 047) | Folds per-PR `governor-review-log/` archive into PR-description `## Governor Footer` block (CI-linted by `tools/check_governor_footer.py`). Adds IC durability taxonomy. Promotes durable-governance ICs into ADR 047 Consequences (ADR047-G1~G27). Adds `/sync-guidelines` cosmetic carve-out to governor-paths.md Exclusions. |
| Independent Review Generalization | ADR 048 (PR #187) | Replaces "cross-tool only" mandatory sub-step with three-mode **independent review**: `cross-tool` (another AI tool), `self-structured` (single-tool structured checklist), `human` (non-author reviewer). `[skip-governor-footer]` restricted to non-governor-changing PRs in CI mode — governor-changing PRs cannot escape the requirement (ADR048-G1). Self-Structured Review Checklist added to all four review/sync skill docs. |
| Context Budget Reduction | #186 (PR #187) | Archives 18 v0.4.0→v0.5.0 project-status rows to `docs/history/archive/project-status/`. Updates Current Version Context from v0.4.0 → v0.6.0. Defers AGENTS.md structural split to a follow-up issue (target: always-loaded context below ~600 lines; current after this PR: see issue #186). |
| Admin Setup Wizard + Page-Level Permissions | #194 | Adds `User.permissions` (JSON), `User.password_temporary`, `User.is_bootstrap_admin` fields + migration 0006. Bootstrap one-time setup wizard (`/admin/setup`) creates first real admin; bootstrap credential permanently disabled afterward. `AdminAccountUseCase` + `AdminPermissionRegistry` for account lifecycle. `require_auth(page_key=...)` mandatory per-route gate enforced by AST test. `/admin/accounts` UI for account create/delete/permission-edit with last-accounts guard. Forced password change flow + refresh token revocation. |
| Server-Route RBAC for /v1/user | #199 | Adds the `require_admin` interface dependency (`role == admin` and not `is_bootstrap_admin` → `403 FORBIDDEN`) plus a dedicated API `ForbiddenException`. All `/v1/user` routes (reads + CUD) become admin-only via a single router-level gate (default-deny for new routes); non-admin self-service stays on `/v1/auth/me`. Role is read live from the DB per request, and unauthenticated calls still resolve to 401 before the role check. Non-user `/v1/*` route-level gating remains a follow-up. |
| Centralized Admin Error Handling | #195 | Adds `AdminErrorHandler` + `@admin_error_boundary`, a global `app.on_exception` safety net, and an unauthenticated `/admin/error` page (`src/_core/infrastructure/admin/error_handler.py`). Admin errors route centrally across page boundary / event callbacks / global handler: only 4xx `BaseCustomException.message` is shown (warning), `>=500`/generic show a generic message (negative), and raw `str(exc)` never reaches the UI — full detail goes to the structured log with `context`/`admin_user`/`error_type`/`error_code`. `BaseAdminPage.render_*` delegate to the handler; `str(exc)` leaks removed from docs/ai_usage/accounts/setup/change_password. AST tests enforce the no-leak rule and `/admin/error` gate-exemption (IC-195-1). |

## Architecture Violation Status
- Domain → Infrastructure import: CLEAN
- Mapper class: CLEAN
- Entity pattern: CLEAN

## Not Yet Implemented
- Server-route RBAC for non-user `/v1/*` routes (per-endpoint role gating; `/v1/user` reads + CUD landed in #199 and admin page-level RBAC in #194, but role enforcement for other domains' `/v1/*` routes is still pending)
- File Upload (UploadFile)
- Rate Limiting (slowapi)
- WebSocket
