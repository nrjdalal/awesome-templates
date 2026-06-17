# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.0] - 2026-06-17

This release simplifies admin theming down to a single Toss-style theme — a
breaking change that removes the multi-preset machinery — lands two new
contributor examples, and clears a batch of trust-signal fixes around the
worker/broker docs and fork-PR CI.

> Spans every change merged since v0.7.2 (2026-06-04).

### Added

- **`blog` example** (`examples/blog/`) — two domains wired through Protocol-based cross-domain DIP, the canonical pattern for one domain depending on another ([#237](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/237))
- **`webhook_receiver` example** (`examples/webhook_receiver/`) — a fast HTTP accept that enqueues a background Taskiq task to process the payload asynchronously, then a status-polling read ([#240](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/240))

### Changed

- **BREAKING — single Toss-style admin theme.** The multi-preset theming system is removed: the `ADMIN_THEME_PALETTE` setting/env var, the `_PALETTES` registry, the `palette_primary` helper, and the `default`/`linear`/`shadcn`/`supabase` presets are gone. The admin look is now two token dicts (`_ROOT_TOKENS` / `_DARK_TOKENS`) in `src/_core/infrastructure/admin/theme.py` — rebrand by editing those dicts. Ships the Toss Design System grey palette + blue/green/red semantics, a light-mode chrome flip, 20px/pill rounding, a dark-mode elevation ladder, a per-mode login backdrop + dark-mode toggle, and global micro-interactions ([#235](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/235))
- `make worker` and `make dev` now pass `--env local` — both previously invoked their launchers without the required `--env` and exited immediately ([#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))
- `run_server_local.py` honors a `PORT` env override (default `8001`), so a second instance can run alongside the primary dev server ([#235](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/235))
- The `Governor Footer Lint` CI comment steps are now best-effort (`continue-on-error`), so a fork PR's read-only `GITHUB_TOKEN` can no longer turn an otherwise-passing check red ([#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))

### Fixed

- **AG Grid empty admin list rendered blank** — a stuck `ag-delay-render` on the grid root left rows permanently `visibility:hidden` in the NiceGUI embed (data present but invisible); `_HELPER_CSS` now forces `.admin-grid` cells visible ([#234](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/234))
- **InMemory broker documented as a standalone-worker default** — `commands.md` and `canonical-demo.md` told readers to run a standalone worker on `BROKER_TYPE=inmemory`, which crash-loops (`InMemoryBroker.listen()` raises). The docs now explain InMemory runs tasks inline in the producer and point to the RabbitMQ/SQS recipe, and a new fast-fail guard (`src/_apps/worker/guards.py`) exits `run_worker_local.py` with an actionable message instead of crash-looping ([#241](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/241), [#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))
- `TaskiqManager.send_task` now logs `SendTaskError` via structlog before re-raising ([#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))
- Examples catalog refreshed (`todo` / `blog` marked landed) and the now-vestigial `examples/**/tests/**` ruff ignore removed ([#242](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/242))

### Docs

- Worker-environment args and InMemory broker limits clarified across the example READMEs and the external-broker recipe ([#96](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/96))

### Upgrading

No database migration. One breaking change to act on when upgrading a derived codebase:

- **`ADMIN_THEME_PALETTE` is removed.** Drop the variable if you set it — the admin now ships a single Toss-style theme. To rebrand, edit the `_ROOT_TOKENS` / `_DARK_TOKENS` dicts in `src/_core/infrastructure/admin/theme.py`; `ADMIN_BRAND_NAME` and `ADMIN_DARK_MODE_DEFAULT` still apply.

## [0.7.2] - 2026-06-04

An admin code-cleanup patch on top of 0.7.1.

### Fixed

- **Admin authorization redirect** — an operator hitting a page they lack permission for was redirected to `/admin/dashboard`, a non-existent route (blank page); now redirects to the real `/admin/` dashboard landing ([#229](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/229))

### Changed

- Internal admin tidy-ups (no user-facing behavior change) — renamed the `theme.palette_accent` helper to `palette_primary` (matches its `--q-primary` return value), simplified the drawer mini-rail nav state, removed a dead `app_username` alias, and stripped dev-process comments from shipped source ([#229](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/229))

## [0.7.1] - 2026-06-04

A security-hardening patch on top of 0.7.0, closing findings from a security
review. Both fixes are behavior-affecting — see **Upgrading** in the release
notes before deploying a derived codebase.

### Security

- **Broken access control on document reads** — `GET /v1/docs/documents` and `/v1/docs/documents/{id}` were public while `DocumentResponse` returns the raw `content`, letting any unauthenticated caller enumerate and exfiltrate every stored document. Both reads now require `Depends(get_current_user)`, matching the existing write/query gates; the e2e 401 test is extended to cover them ([#227](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/227))
- **Credentialed CORS reflection in strict environments** — `ALLOW_ORIGINS` defaulted to `["*"]` while the CORS middleware uses `allow_credentials=True`, so a `stg`/`prod` deploy that forgot an explicit allowlist would reflect any `Origin` with `Access-Control-Allow-Credentials` (exploitable against the cookie-backed admin session). A strict-env validator now **rejects `*` in `allow_origins` for `stg`/`prod`** at boot; `dev`/`local`/`quickstart` keep the wildcard for convenience ([#227](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/227))

### Changed

- Security-reference sync — `project-dna.md` §8 and `security-checklist.md` §2 corrected to the `admin_identity` realm model (#218 / ADR 049), and a new admin session-cookie hardening item (`https_only` / `SameSite` in `stg`/`prod`) added to the checklist ([#227](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/227))

### Upgrading

No database migration. Two behavior changes to act on when upgrading a derived codebase:

- **`stg`/`prod` must set an explicit `ALLOW_ORIGINS` allowlist** — the `*` dev default is now rejected at boot in strict environments.
- **`GET /v1/docs/documents` and `/v1/docs/documents/{id}` now require a Bearer token** — unauthenticated callers receive `401`; update derived clients that read documents without auth.

## [0.7.0] - 2026-06-02

This release hardens the admin and AI-agent surfaces and reworks the admin UI.
Four threads: **(1) Admin security** — a separate admin-identity bounded context
with its own JWT realm, server-route RBAC, a setup wizard with page-level
permissions, and an audit log with a retention pipeline; **(2) AI guardrails** —
OWASP LLM01 / LLM07 prompt-injection defenses across the PydanticAI call sites
(structural → runtime → observability); **(3) Admin UX** — a token-driven design
system, a data-dashboard landing, centralized error handling, and loading
states; **(4) Release hygiene** — version, CHANGELOG, and project-status sync.

> Spans every change merged since v0.6.0 (2026-05-07); no interim release was tagged.

### Added

- **Admin identity bounded context** (`src/admin_identity/`, ADR 049) — admin/operator identity separated from customer identity, with its own credential store (`admin_identity` + `admin_refresh_token` tables) **and** its own JWT realm (distinct `ADMIN_JWT_SECRET_KEY` / issuer / audience; a config validator rejects realm collapse). Adds `/v1/admin/login|refresh|logout`; the shared `JwtTokenCodec` is extracted to `src/_core/common/` ([#218](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/218))
- **Server-route RBAC for `/v1/user`** — a `require_admin` interface dependency (admin-realm token required; a customer token resolves to `401 INVALID_TOKEN`, the trust boundary) gates all `/v1/user` reads + writes at the router level (default-deny); non-admin self-service stays on `/v1/auth/me` ([#199](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/199))
- **Admin setup wizard + page-level permissions** — a one-time `/admin/setup` creates the first real admin (the bootstrap credential is permanently disabled afterward), backed by `AdminAccountUseCase` + `AdminPermissionRegistry`; `/admin/accounts` UI for account create/delete/permission-edit with a last-admin guard, a forced password-change flow, and a mandatory `require_auth(page_key=...)` per-route gate (AST-enforced) ([#194](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/194))
- **Admin audit log** — `src/_core/infrastructure/admin/audit/` (model + `AdminAuditLogRepository` + `AuditLogger` facade + `@audit_action` decorator) records login/logout, account/permission/password, and first-admin events as `SUCCESS`/`FAILURE` with an `error_code` (never raw `str(exc)`, no password hashes). Adds the `/admin/audit-log` operator UI, a per-domain read-event opt-in (`BaseAdminPage.log_reads`), and a `TaskiqScheduler` retention-cleanup job (`make scheduler`, `audit_log_retention_days`) ([#196](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/196), [#206](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/206))
- **Prompt-injection guardrails (OWASP LLM01 / LLM07)** across the PydanticAI RAG + classifier call sites:
  - *Structural* — `instructions=` slot migration + `Final[LiteralString]` persona; retrieved documents and user input wrapped in boundary XML and escaped via `escape_for_prompt_xml` ([#197](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/197))
  - *Runtime* — `src/_core/infrastructure/llm/guardrails.py`: input injection detection (block), output PII-fabrication diff (block), prompt-leak (log-only); a `GUARDRAILS_ENABLED` DI kill-switch ([#209](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/209))
  - *Observability* — an `ai_usage.guardrail_triggered` flag through the usage ledger, a `/v1/usage?guardrailTriggered=` filter, standardized telemetry, and a red-team regression corpus ([#211](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/211))
- **Admin design system** — a token-driven theme (`theme.py`: 4 style presets via `ADMIN_THEME_PALETTE`, dark mode, self-hosted Wanted Sans) and a `components/` builder library, with the `docs/ai/shared/admin-design-system.md` catalog ([#193](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/193))
- **Admin data dashboard** — the `/admin/` landing rebuilt around a `dashboard_metrics` read facade (per-source isolation; audit read gated on the `audit_log` permission): domain record-count stat cards, the first ECharts builder `c.bar_chart()`, a recent-activity table, and quick-action nav ([#223](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/223))

### Changed

- **Admin authentication re-homed to `admin_identity`** — the interim single-table admin model (`User.role` / `permissions` / `password_temporary` / `is_bootstrap_admin`, introduced by #154/#194) is removed; the `user` table is now pure customer identity and existing admins are migrated into `admin_identity`. NiceGUI admin login + bootstrap seed are re-pointed accordingly (token-less session shape preserved) ([#218](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/218), supersedes [#154](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/154) / [#194](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/194))
- **Centralized admin error handling** — `AdminErrorHandler` + `@admin_error_boundary` + a global `app.on_exception` net + an unauthenticated `/admin/error` page; only 4xx `BaseCustomException.message` surfaces (warning), `>=500`/generic show a generic message, and raw `str(exc)` never reaches the UI (full detail goes to the structured log) ([#195](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/195))
- **Admin loading states** — a `button_loading` context manager on every admin write button + structure-mirroring skeletons on list/detail loads ([#198](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/198))
- **Admin shell look & feel** — the dark content palette retuned from blue-navy to a neutral charcoal/zinc cohesive with the shadcn/supabase/linear chrome (lifted off near-OLED black; page < chrome < card elevation; `.q-card` bound to `--admin-surface`), and the sidebar now collapses to an icon-only **mini rail** with a top-of-drawer collapse control (nav tooltips + `aria-label`; header hamburger mobile-only) ([#223](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/223))

### Fixed

- Guardrail PII scan no longer false-positives on reformatted phone numbers (regex normalization) ([#214](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/214))

## [0.6.0] - 2026-05-07

This release completes the production feature surface and prepares the project
for OSS launch. Three themes: **(1) Production feature completion** — JWT
authentication domain with refresh-token rotation, NiceGUI admin JWT + minimal
RBAC, and `/docs` selector revamp with `frontend-handoff.md`; **(2) Governance
maturity** — ADR 047 full rollout (governor-review-log folded into PR Footer
blocks), harness sync advisory SOT migration across both tools; **(3) OSS
launch readiness** — `docs/adoption.md`, `docs/comparison.md`,
`docs/compatibility.md`, `SUPPORT.md`, expanded `CONTRIBUTING.md`,
`docs/README.md` index, terminal demo GIFs, and truthfulness fixes across
README / SECURITY.md / examples / tutorial.

### Added

- JWT authentication domain (`src/auth/`) — HS256 access/refresh tokens, DB-backed rotation/revocation, `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/auth/me`, Bearer protection for user API routes ([#4](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/4))
- NiceGUI admin JWT login + minimal RBAC — credential check via auth-domain, `User.role` DB field (`UserRole` enum), `ADMIN_BOOTSTRAP_*` idempotent seeding; legacy env-var auth provider removed ([#154](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/154), [PR #155](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/155))
- `/docs` selector revamp — GitHub-flavoured layout, built-in light/dark toggle with `localStorage` persistence, `GET /openapi-download.json` (Content-Disposition: attachment); `docs/frontend-handoff.md` covering OpenAPI contract, camelCase serialisation, JWT flow, CORS, and Bruno/Postman/Hey API/Orval recipes ([#156](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/156))
- `docs/adoption.md` — greenfield and partial-import adoption paths for teams onboarding from an existing FastAPI project
- `docs/comparison.md` — standalone deep-dive comparison including Litestar, Robyn, cookiecutter, and full-stack-fastapi-template with per-claim evidence links
- `docs/compatibility.md` — Python / FastAPI / Pydantic / SQLAlchemy / Claude Code / Codex CLI / OS compatibility matrix
- `SUPPORT.md` — in-scope / out-of-scope / breaking-change policy / response SLA / single-maintainer statement
- `CONTRIBUTING.md` expanded — first-PR-friendly areas, test execution guide, architecture guardrails, review expectations, skill harness change policy
- `docs/README.md` — docs folder index providing entry points for all reference documents
- Terminal demo GIFs (`docs/assets/cast/demo.gif`, `docs/assets/cast/new-domain.gif`) demonstrating end-to-end API flow and `/new-domain` domain scaffolding
- `docs/canonical-demo.md` — full integration walkthrough (auth · RBAC · worker · admin · RAG · OTEL · tests)
- `/sync-guidelines` project-status.md table hygiene check — step 3 extended to verify row-count consistency between the status table and archived rows ([#176](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/176))

### Changed

- README restructured — hero tagline `Production FastAPI architecture, with AI-assisted domain scaffolding built in.`, 60/40 two-column Why section (Production rigor primary / AI-assisted acceleration first-class amplifier), Quickstart → Canonical demo → Why → Compare section order; ADR/governance mentions moved to deeper sections
- Governor-Review Provenance Consolidation full rollout (ADR 047) — per-PR `governor-review-log/` archive folded into PR-description `## Governor Footer` block; durable ICs promoted into ADR 047 Consequences (`ADR047-G1 ~ ADR047-G27`) or `project-dna.md`; historical archive at `docs/history/archive/governor-review-log/` ([#157](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/157))
- Harness governance improvements — sync advisory SOT migrated to `governor.sync_advisory` module for both Claude bash hook and Codex stop hook; completion-gate fossil sweep; lifecycle invariant tests; shared changed-files delegation; override de-recommendation in `/plan-feature` ([#162](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/162)–[#182](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/182))
- pyproject.toml `keywords` and `classifiers` moved to correct `[project]` table; 12 discovery keywords added (`fastapi`, `ddd`, `agent`, `llm`, `rag`, `template`, `boilerplate`, `claude-code`, `codex-cli`, `taskiq`, `nicegui`, `pydantic-ai`)

### Fixed

- Stale claims corrected: ADR count `40` → `18 active · 30 archived`; CRUD method count `7` → `8`; `examples/todo/` port `8000` → `8001`; `docs/tutorial/first-domain.md` Step 4 self-contradiction resolved to single-restart flow; `SECURITY.md` supported versions updated to `0.4.x` / `0.5.x`
- Demo script (`scripts/demo.sh`) JWT token fallback field corrected

### Removed

- `governor-review-log/` working directory — migrated to `docs/history/archive/governor-review-log/` as closed historical archive ([#157](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/157))

## [0.5.0] - 2026-04-29

This release hardens the AI agent workflow governance and delivers production
infrastructure across three themes: **(1) AI workflow governance** — Hybrid
Harness v1 (7-step Default Coding Flow, shared governor module, localized
reminders), Tier 1 Language Policy, Reasoning-Level Consistency Guards,
Governor Footer CI; **(2) Production infrastructure** — AI Usage Ledger
(`ai_usage` domain), Taskiq smart retry with task-scoped structured logging,
optional OpenTelemetry tracing; **(3) Contributor experience** — unified
Quality Gate review contract, `/plan-feature` Approach Options stage,
`examples/todo/` reference domain.

### Added

- Hybrid Harness v1 — 7-step Default Coding Flow (`framing → approach options → plan → implement → verify → self-review → completion gate`), exception-token parser ([PR #126](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/126)), verify-first adapters ([PR #127](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/127)), completion-gate Stop adapter with governor sync advisory ([PR #128](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/128)), shared governor module eliminating four hook duplicates ([PR #130](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/130)); ADR 045 ([#117](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/117))
- AGENT_LOCALE localized hook reminders — `governor/locale.py` canonical locale module (18 keys, ko/en), `python -m governor.locale` CLI, IC-19 always-fallback enforcement at every emit callsite ([#133](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/133), [PR #134](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/134))
- Tier 1 Language Policy — `AGENTS.md § Language Policy` enforcing English-only prose on governance/harness/contributor-facing paths; `tools/check_language_policy.py`, pre-commit hook, CI enforcement, bilingual escape-token vocabulary + `LOCALE_DATA_FILES` as two narrowly-scoped exceptions ([#131](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/131), [PR #132](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/132))
- Reasoning-Level Consistency Guards (Layer 2 Governor) — four guards: F (volatile workspace facts re-verification), G (R-point closure completeness), H (effect vs. process question discrimination), I (self-licensing detection); IC-RG-1 through IC-RG-5; canonical in `AGENTS.md` ([PR #143](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/143))
- Cross-tool prompt template standardisation — canonical cross-review prompt templates for `/review-pr`, `/review-architecture`, `/security-review`, `/sync-guidelines` with R-point closure categories and `Sync Required` field ([#144](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/144), [PR #147](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/147))
- Governor Footer CI — `tools/check_governor_footer.py` + `Governor Footer Lint` GitHub Actions workflow; PR-description `## Governor Footer` block as canonical G-closure record; ADR 047 ([#145](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/145), [PR #148](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/148))
- AI Usage Ledger — `ai_usage` domain with `AgentUsageRecord` / `PromptSnapshot` value objects, RDB migrations, admin and API surfaces for per-call usage accounting ([#75](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/75), [PR #149](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/149))
- Taskiq smart retry middleware — task-scoped structlog context binding, structured task failure logging, permanent-aware retry strategy wired through worker bootstrap ([#120](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/120), [PR #150](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/150))
- Optional OpenTelemetry tracing — `[otel]` extra (`opentelemetry-api/sdk/exporter-otlp-proto-grpc`), `OTEL_ENABLED` + `OTEL_EXPORTER_OTLP_ENDPOINT` settings, `_maybe_configure_otel` at server/worker bootstrap, Jaeger/Tempo/Phoenix recipe at `docs/operations/observability-otel.md`; ADR 046 Pillar 1 ([#136](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/136))
- `/plan-feature` Approach Options stage — Phase 1 now presents 2–3 candidate approaches with trade-offs and a recommendation before architecture analysis ([#116](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/116))
- Quality Gate Skill unified review contract — `/review-pr`, `/review-architecture`, `/security-review` emit a consistent `Scope / Sources Loaded / Findings / Drift Candidates / Next Actions / Completion State / Sync Required` output shape; `/sync-guidelines` documented as the closure step ([#113](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/113))
- `examples/todo/` contributor reference — minimal CRUD example mirroring `src/user/` layout, not subject to auto-discovery (copy to `src/todo/` to run); `/review-architecture` recognises the `examples` profile and relaxes §5 Test Coverage and §2 Auth requirements ([#112](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/112), [#119](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/119))

### Changed

- Responsibility-Driven Refactor (ADR 043) — `error_mapper.py` promoted to the infra ACL (domain services raise domain exceptions only); `ClassifierProtocol` / `PydanticAIClassifier` / `StubClassifier` align with the ADR 040 consumer pattern; `_core/infrastructure/ai/providers.py` unifies `parse_model_name` and provider builder; `AdminCrudServiceProtocol` + `extra_services_config` give admin layer type stability; bootstrap conductor decomposed into private functions; `BaseEmbeddingProtocol` / `BaseVectorStoreProtocol` switch to `typing.Protocol`
- **BREAKING** — `boto3` and `aioboto3` moved from core `[project.dependencies]` to `[project.optional-dependencies].aws` extra; four AWS-backed clients now lazy-import `aioboto3`/`boto3`/`botocore`; non-AWS deployments no longer pay the boto3 install cost. Migration: add `--extra aws` to your `uv sync` command if you use S3/MinIO, DynamoDB, or S3 Vectors ([#104](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/104))

### Removed

- `tools/check_g_closure.py` + legacy `check-g-closure` pre-commit hook — superseded by `tools/check_governor_footer.py` + `Governor Footer Lint` CI ([#145](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/145), ADR 047)

## [0.4.0] - 2026-04-21

### Added

- Zero-config quickstart (`make quickstart` / `make demo` / `ENV=quickstart` with SQLite + InMemory broker + auto create_all) so the blueprint can boot in under 60 seconds with no external infra ([#78](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/78))
- End-to-end RAG example as a reusable `_core` pattern (`RagPipeline`, `BaseChunkDTO` / `CitationDTO` / `QueryAnswerDTO`, `AnswerAgentProtocol`, `StubEmbedder` / `StubAnswerAgent` / `PydanticAIAnswerAgent`, `BaseInMemoryVectorStore`) with `src/docs/` consumer domain, `make demo-rag`, and `VECTOR_STORE_TYPE` env var ([#80](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/80))
- Optional Infrastructure pattern in CoreContainer — `providers.Selector` + lazy factories for all 5 non-broker optional infras (storage, DynamoDB, S3 Vectors, embedding, LLM); disabled branches return `providers.Object(None)` for data stores or `StubEmbedder` / PydanticAI `TestModel` for AI infras so apps boot with only `DATABASE_ENGINE=sqlite` set and optional extras uninstalled ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- `build_stub_llm_model()` factory — returns PydanticAI `TestModel` when `pydantic-ai` is installed, `None` otherwise, so `ClassificationService` and future LLM-consuming domains degrade gracefully when `LLM_*` env vars are unset ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- Structured logging via `structlog` + `asgi-correlation-id` — one `ProcessorFormatter` pipeline bridges structlog-native records and every existing `logging.getLogger(__name__)` call site. Dual renderer (JSON in stg/prod, coloured console in dev), `LOG_LEVEL` / `LOG_JSON_FORMAT` env vars with independent override, per-request `X-Request-ID` correlation bound into `contextvars` and surfaced on every record, `http_request` access-log middleware (method / path / status / duration_ms), Taskiq `StructlogContextMiddleware` binding task IDs + lifting `correlation_id` labels from the dispatcher side, and a `sqlalchemy.engine` double-emit fix that translates `DATABASE_ECHO` into a logger level ([#9](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/9))
- AGENTS.md "Optional Infrastructure Toggles" reference section (formerly "Optional Infrastructure" — renamed in PR-B.4a) and `docs/ai/shared/scaffolding-layers.md` "Optional AI Infra Variant" section for `/new-domain` scaffolding ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- README restructure (633 → 260 lines), `docs/reference.md`, and `docs/README.ko.md` Korean mirror ([#79](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/79))
- Visual architecture diagrams (Mermaid + SVG exports) with canonical `docs/ai/shared/architecture-diagrams.md` and `make diagrams` target ([#81](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/81), [#89](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/89))
- "Your first domain in 10 minutes" tutorial ([#84](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/84))
- Contributor funnel — good-first-issues audit, `examples/` seed, five seed issues for contributors ([#85](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/85))
- Secret hygiene — gitleaks pre-commit hook, history scan, `SECURITY.md` expansion ([#87](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/87))
- CI `minimal-install` job — runs `uv sync --group dev` alone (no extras) and asserts the app boots, `/api/health` serves, no `/admin` routes are mounted. This is the regression guard for the "extras-uninstall → still boots" promise ([#104](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/104))
- ADR 040 (RAG as reusable `_core` pattern), ADR 041 (Multi-backend infrastructure layout — persistence umbrella + vector backend subfolders), ADR 042 (Optional Infrastructure — Selector + lazy factory)

### Changed

- ADR curation — 40 ADRs consolidated down to 14 core + 29 archived under `docs/history/archive/`, with `docs/history/README.md` providing a core-reading-order guide for onboarding ([#83](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/83))
- `CoreContainer.llm_config` and `CoreContainer.embedding_config` are no longer public providers — both VOs are now constructed inside the lazy factory functions, reducing the container's surface area without changing the VO classes themselves ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- `src/_core/infrastructure/` reorganised under the `persistence/` umbrella (RDB at `persistence/rdb/`, DynamoDB at `persistence/nosql/dynamodb/`) with vector backends split into `vectors/s3/` and `vectors/in_memory/` sharing a root `vector_model.py` ([#80](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/80), ADR 041)
- RAG DTOs relocated from `_core/domain/value_objects/rag/` to `_core/domain/dtos/rag.py` and renamed `QueryAnswer` → `QueryAnswerDTO` for consistency with the ADR 004 DTO suffix convention ([#80](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/80))
- **BREAKING** — `nicegui` moved from core `[project.dependencies]` to a new `[project.optional-dependencies].admin` extra. API-only deployments no longer pay the nicegui install cost; the NiceGUI admin dashboard now requires `uv sync --extra admin`. Contributors running `make setup` / `make quickstart` get the extra automatically. The server bootstrap emits a structured `admin_mount_skipped` record (via the #9 logging pipeline) when nicegui is not installed. This is a SemVer-minor breaking change permitted under the project's `0.x` contract; a deprecation-warning phase was considered but rejected given the small current user base and the cleaner migration story ([#104](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/104))
- `Database.__init__` no longer passes `echo=True` to SQLAlchemy's `create_engine` (which would install a parallel `StreamHandler` on `sqlalchemy.engine` and double-emit every query alongside the structlog root handler). `DATABASE_ECHO=true` now translates to `logging.getLogger("sqlalchemy.engine").setLevel(INFO)` — same user-visible semantics, records flow through the structlog pipeline exactly once ([#9](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/9))

### Fixed

- `generic_exception_handler` replaced the stray `print(error_trace)` with a structured `logger.exception("unhandled_exception", exc_info=exc, exception_type=...)` — traceback renders inline in both console and JSON modes ([#9](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/9))

## [0.3.0] - 2026-04-09

### Added

- NiceGUI admin dashboard with auto-discovery, env-var auth, AG Grid CRUD, and field masking ([#14](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/14))
- DynamoDB support with `BaseDynamoRepository`, `DynamoModel`, and `DynamoDBClient` ([#13](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/13))
- Broker abstraction with `providers.Selector` for SQS/RabbitMQ/InMemory multi-backend ([#8](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/8))
- Flexible RDB configuration with multi-engine and per-environment support ([#7](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/7))
- Environment-aware config validation in Settings — strict mode for stg/prod ([#53](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/53))
- Password hashing (`hash_password`, `verify_password`) and input validation in `_core.common.security`
- `QueryFilter` value object for paginated query params with sort/search
- DynamoDB Local service in CI for integration tests ([#13](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/13))
- Branch name validation in CI for pull requests (`{type}/{description}` format enforcement)
- `/add-admin-page` skill for NiceGUI admin page scaffolding
- ADR 026 (NiceGUI Admin), ADR 027 (Flexible RDB), ADR 028 (Config Validation), ADR 029 (Broker Abstraction)

### Changed

- Replace SQLAdmin with NiceGUI for admin interface ([#14](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/14))
- Restore `CreateDTO`/`UpdateDTO` generics to `BaseService` (3 TypeVars) — reverts prior simplification (ADR 011 post-decision update)
- Rename Serena memory `refactoring_status` → `project_status` for clarity ([#60](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/60))
- Expand `sync-guidelines` to update all 4 Serena memories (was only 1) ([#60](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/60))
- Make `taskiq-aws` an optional dependency with lazy import ([#8](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/8))
- Admin views moved from `interface/admin/views/` to `interface/admin/pages/`

### Removed

- `/create-pr` skill — branch name validation moved to CI; PR creation handled by Claude Code built-in capability

### Fixed

- Add missing `__init__.py` in `_core/domain/protocols/` and `_core/domain/value_objects/` ([#60](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/60))
- Mount NiceGUI directly on main app instead of sub-app
- Harden admin security with server-side masking and timing-safe auth
- Skip SQS broker test when `taskiq-aws` not installed ([#8](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/8))

## [0.2.0] - 2026-04-07

### Added

- Worker Payload Schema: `BasePayload` and `PayloadConfig` for worker message contract validation ([#45](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/45))
- Database health check endpoint with `HealthService` ([#19](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/19))
- `/create-pr` and `/review-pr` GitHub collaboration skills ([#31](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/31))
- Conventional commit message validation hook ([#31](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/31))
- `make help` as default Makefile target ([#31](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/31))
- 9 missing ADRs (017-025) from full commit history analysis
- ADR 014 (OMC vs Native decision) and ADR 015 (rebranding) and ADR 016 (Worker Payload Schema)

### Changed

- Rebrand project to **AI Agent Backend Platform** (`fastapi-agent-blueprint`) ([#43](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/43))
- Rename `interface/dtos/` to `interface/schemas/` for terminology consistency ([#38](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/38))
- Unify exception handling with `app.add_exception_handler` ([#35](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/35))
- Consolidate sync hook to single git-diff-based Stop hook ([#40](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/40))
- Strengthen harness hook security checks and expand detection scope ([#47](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/47))
- Extract `HealthService` to follow Router -> Service pattern ([#19](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/19))
- Move health check logic into `Database.check_connection()` ([#29](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/29))
- Translate all documentation to English (ADRs, skills, references, config, code comments) ([#25](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/25))
- Improve ADR template with anti-rationalization principles ([#48](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/48))
- Align all 17 existing ADRs with improved template structure ([#48](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/48))

### Removed

- Domain Event infrastructure (unused) ([#38](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/38))

### Fixed

- Correct `error_code` attribute in `ExceptionMiddleware` ([#26](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/26))
- Sync flag file path for sandbox compatibility ([#38](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/38))

## [0.1.0] - 2026-03-26

### Added

- Initial project structure with 3-tier hybrid layer architecture
- Domain auto-discovery system (`DynamicContainer` + factory function)
- `BaseService` and `BaseRepository` with generic CRUD operations
- User domain as reference implementation
- Alembic migration support
- Taskiq worker integration with RabbitMQ broker
- SQLAdmin dashboard
- Docker Compose for local development
- GitHub Actions CI workflow
- Ruff for unified linting and formatting
- Claude Code skills: `/new-domain`, `/add-api`, `/add-worker-task`, `/add-cross-domain`, `/review-architecture`, `/security-review`, `/test-domain`, `/fix-bug`, `/onboard`
- ADR documentation (001-013)
- CONTRIBUTING guide and issue templates

[Unreleased]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.7.2...v0.8.0
[0.7.2]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/releases/tag/v0.1.0
