# Project DNA - Shared Pattern Reference Extracted from Code

> Shared canonical reference for Claude, Codex, and Antigravity workflow assets.
> Update this file when shared architecture patterns change, then sync the harness docs that point to it.

> This file is auto-extracted/updated from `src/user/` (reference domain) and `src/_core/` (Base classes)
> when `/sync-guidelines` is run. **Run `/sync-guidelines` instead of editing manually.**
> Derivable facts link to their source; preserve non-derivable policy and durable invariants.
> Historical examples: [pre-lightweighting snapshot](../../history/archive/harness-context/project-dna.md).
>
> Last synced: 2026-11-06 via #414 B1/B4/B5

## Section Index
§0 Project Scale and Design Philosophy |
§1 Directory Structure | §2 Base Class Path | §3 Generic Type Signatures | §4 CRUD Methods
§5 DI Pattern | §6 Conversion Patterns | §7 Security Tools | §8 Active Features
§9 Router Pattern | §10 Exception Pattern | §11 Admin Page Pattern
§12 S3 Vector Store Pattern | §13 Embedding Pattern | §14 LLM Pattern
§15 Auth Domain Pattern | §16 Docs Frontend Contract | §17 Admin Identity Realm

> **Visual summary:** see [`architecture-diagrams.md`](architecture-diagrams.md)
> for the layer dependency graph, Write/Read data flow (RDB), and the
> RDB / DynamoDB / S3 Vectors variant table. The sections below are the
> policy and source-navigation reference; the diagrams exist to orient new readers
> before they dig into §1–§14.

---

## §0. Project Scale and Design Philosophy

### Scale
Design for enterprise use with 10+ domains / 5+ team members, including scalability, maintainability and collaboration.

### Enterprise Practice Criteria for Proposals

Apply these criteria in code generation, design and review:

- **Scalability:** paginate list APIs; propose Worker tasks for large processing; use joinedload/selectinload where relationships risk N+1 queries.
- **Team collaboration:** cross-domain dependencies use Protocol DIP, never direct implementation imports; assess every consumer before shared DTO changes; propose backward-compatible API signatures by default.
- **Operations:** assess audit needs for CUD; consider timeout/retry/circuit breakers for external calls; return actionable error_codes.
- **Security:** exclude PII from Responses and logs; explicitly mark authenticated endpoints; manage secrets, DB URLs and environment-specific config via env vars only.

### Direction & Non-goals (ADR 050)

**Direction** — the alignment reference for plan-feature and reviews:

- A production DDD/FastAPI foundation with optional, stub-degradable AI hooks.
- Every non-DB infra remains optional (ADR 042); zero-config quickstart must boot and serve.
- New AI capability is a reusable `_core/infrastructure/` pattern plus a thin consumer domain/example, following RAG.
- Serve both OSS copy-flow adopters and a service with 10+ domains / 5+ team members; state audience trade-offs explicitly.
- Shared governor policy keeps Claude/Codex/Antigravity aligned; process automation starts advisory and grows only with demonstrated need.

**Non-goals** — proposals matching these are rejected by default (revisiting one requires an ADR):

- A general-purpose web framework or an admin-panel product — the NiceGUI admin remains an optional extra.
- A hosted platform/SaaS or provider lock-in — provider abstraction stays behind PydanticAI / env-driven selection.
- Features that break the zero-config quickstart or make optional infra mandatory.
- Framework-breadth chasing — file upload, WebSocket, rate limiting, and similar items ship on demonstrated demand, not as roadmap commitments.
- Hard-blocking automation gates — the harness nudges; humans and CI decide.

---

## §1. Layer Directory Structure

Reference domain: [src/user/](../../../src/user). Use [scaffolding-layers.md](../../../docs/ai/shared/scaffolding-layers.md) for the ordered file list. Domain owns DTOs/protocols/services; infrastructure owns models/repositories/DI; interfaces own server schemas/routers, admin configs/pages, and worker payloads/tasks. Add application UseCases only for orchestration complexity.

### DynamoDB Domain Variant

Use `infrastructure/dynamodb/models/` with `DynamoModel` and `BaseDynamoRepository`; inject `core_container.dynamodb_client`. Other layer boundaries are unchanged. Sources: [DynamoDB infrastructure](../../../src/_core/infrastructure/persistence/nosql/dynamodb).

## §2. Base Class Import Path

Use source owners as import authorities:

- Repository / embedding / vector / admin contracts: [protocols](../../../src/_core/domain/protocols).
- BaseService / BaseDynamoService: [services](../../../src/_core/domain/services); validation contracts: [validation](../../../src/_core/domain/validation.py).
- Database / Base / BaseRepository: [RDB](../../../src/_core/infrastructure/persistence/rdb); DynamoDB types: [DynamoDB](../../../src/_core/infrastructure/persistence/nosql/dynamodb); vector models / clients / stores: [vectors](../../../src/_core/infrastructure/vectors).
- Request / Response / Payload / configuration bases: [application DTOs](../../../src/_core/application/dtos); BaseCustomException: [exception base](../../../src/_core/exceptions/base_exception.py).
- Query / cursor / embedding / LLM value objects: [value objects](../../../src/_core/domain/value_objects); pagination / security / text / UUID helpers: [common](../../../src/_core/common).
- Provider construction and clients: [CoreContainer](../../../src/_core/infrastructure/di/core_container.py).

### Inheritance Chain

- `BaseRequest` → `ApiConfig` → `BaseModel` (camelCase alias, frozen, populate_by_name)
- `BaseResponse` → `ApiConfig` → `BaseModel`
- `SuccessResponse` → `ApiConfig`, `Generic[ReturnType]`
- `BasePayload` → `PayloadConfig` → `BaseModel` (frozen, extra="forbid", no alias)
- `ValueObject` → `BaseModel` (frozen=True)

## §3. Generic Type Signatures

`BaseRepositoryProtocol[ReturnDTO]` / `BaseRepository[ReturnDTO]` have one return TypeVar; writes accept `BaseModel`. `BaseService[CreateDTO, UpdateDTO, ReturnDTO]` has three so overrides and validators retain typed fields (ADR 011). `SuccessResponse[ReturnType]` is generic. Reference usage: [UserService](../../../src/user/domain/services/user_service.py) and [UserRepository](../../../src/user/infrastructure/repositories/user_repository.py). Never collapse BaseService back to one TypeVar.

### DynamoDB Generic Type Signatures

`BaseDynamoRepositoryProtocol[ReturnDTO]` and `BaseDynamoRepository[ReturnDTO]` have one return TypeVar; `BaseDynamoService[CreateDTO, UpdateDTO, ReturnDTO]` has three. See [DynamoDB service](../../../src/_core/domain/services/base_dynamo_service.py).

### S3 Vector Store Generic Type Signatures

`BaseVectorStoreProtocol[ReturnDTO]` is a runtime-checkable Protocol; `BaseS3VectorStore[ReturnDTO]` is an ABC. See [vector contract](../../../src/_core/domain/protocols/vector_store_protocol.py).

### BaseS3VectorStore.__init__ Signature

The keyword-only `model`, `return_entity`, and `bucket_name` follow `s3vector_client`; use the live [BaseS3VectorStore constructor](../../../src/_core/infrastructure/vectors/s3/base_store.py).

### BaseRepository.__init__ Signature

Inject `database`, keyword-only `model` and `return_entity`; see [BaseRepository](../../../src/_core/infrastructure/persistence/rdb/base_repository.py).

### Two signature conventions (#394, #396, #399)

- Read-only collection parameters take `Sequence`, not invariant `list`; a caller's `list[MyDTO]` must not require a cast to `list[BaseModel]`.
- Consumers needing only a few collaborator members declare an underscore-prefixed local `Protocol` beside the consumer, explaining the seam in its docstring.
- Such a protocol must accept the actual production object (NiceGUI `props` is a property returning a callable, not a method).
- Keep concrete client annotations when they type-check boto/aiohttp APIs; accept test doubles at the substitution site rather than erasing provider type checking.

## §4. Base CRUD Methods

### BaseRepositoryProtocol Methods

The [repository protocol](../../../src/_core/domain/protocols/repository_protocol.py) owns CRUD writes, paginated reads, existence checks, and aggregate reads. `count_datas_by_day` returns `list[DailyCount]` alongside `count_datas`; [BaseService](../../../src/_core/domain/services/base_service.py) exposes both. Add repository + protocol + service together for caller-facing aggregate reads; no validation hook runs on reads. Dialect normalisation stays in [BaseRepository](../../../src/_core/infrastructure/persistence/rdb/base_repository.py) (ADR 058).

### BaseService Methods (Repository Delegation Mapping)

The [service implementation](../../../src/_core/domain/services/base_service.py) is the delegation map: create/update/delete run the protected validation hook before the matching repository write; reads delegate and pagination wraps counts. Extend `BaseService[CreateRequest, UpdateRequest, DTO]`; override only for domain logic. `count_datas` and `count_datas_by_day` are paired service pass-throughs.

### BaseService Validation Hooks

`_validate_create(entity)`, `_validate_create_many(entities)`, `_validate_update(data_id, entity)`, and `_validate_delete(data_id)` are protected async no-ops by default. Override only for explicit domain business rules; reusable helpers live in [validation.py](../../../src/_core/domain/validation.py), non-trivial composition in domain `validators.py`. Service owns validation before every CRUD write; DB constraints remain the final integrity guard.

### BaseDynamoRepositoryProtocol Methods

Read current `put_item`, batch, get/query/update/delete contracts in [BaseDynamoRepositoryProtocol](../../../src/_core/domain/protocols/dynamo_repository_protocol.py) and [BaseDynamoRepository](../../../src/_core/infrastructure/persistence/nosql/dynamodb/base_dynamo_repository.py). Query returns a `CursorPage[ReturnDTO]`; keys use `DynamoKey`.

### BaseDynamoService Methods

See [BaseDynamoService](../../../src/_core/domain/services/base_dynamo_service.py) for direct payload/DTO delegation to the DynamoDB contract. No RDB pagination or numeric-ID assumptions apply.

### DynamoDB DI Pattern

Use a repository Singleton injected with `core_container.dynamodb_client`, and a service Factory injected with that repository. Guard a disabled (`None`) data-store client at the domain boundary; see [CoreContainer](../../../src/_core/infrastructure/di/core_container.py).

## §5. DI Pattern

The provider lifetimes below are policy, not a generated inventory. Reference wiring: [UserContainer](../../../src/user/infrastructure/di/user_container.py).

Storage uses enabled/disabled Selectors with lazy factories in [CoreContainer](../../../src/_core/infrastructure/di/core_container.py); S3/MinIO parameters come from Settings.

| Component | Provider Type | Notes |
|---------|--------------|------|
| Database | `providers.Singleton` | |
| Repository | `providers.Singleton` | |
| Service | `providers.Factory` | Direct injection from Router |
| UseCase | `providers.Factory` | Add only for complex logic |
| Domain Container | `containers.DeclarativeContainer` | |
| External Container reference | `providers.DependenciesContainer()` |
| App Container (Server/Worker) | `containers.DynamicContainer` (factory function) |
| Domain auto-discovery | `src._core.infrastructure.discovery.discover_domains()` |
| Dynamic Container loading | `src._core.infrastructure.discovery.load_domain_container()` |
| Broker (multi-backend) | `providers.Selector` | Selects SQS/RabbitMQ/InMemory by config (ADR 029) |
| Optional infra (storage / DynamoDB / S3 Vectors / embedding / LLM) | `providers.Selector` + lazy factory | Enabled branch constructs the real client; disabled branch returns `providers.Object(None)` for data stores or a stub (`StubEmbedder` / `TestModel`) for AI infras (ADR 042) |
| `EmbeddingConfig` / `LLMConfig` | Constructed inside lazy factories | Frozen dataclass VOs (domain layer) — **not** standalone container providers post-ADR 042; consumers receive the built `embedding_client` / `llm_model` instead |

### App-level Container (Auto-discovery)

Domain containers are `DeclarativeContainer`; app containers use `DynamicContainer` factory functions. [server container](../../../src/_apps/server/di/container.py) uses [discover_domains / load_domain_container](../../../src/_core/infrastructure/discovery.py) to register valid domains. Adding a domain requires no manual app-level container/bootstrap registration.

### Broker Selection Pattern (Runtime Configuration)

`BROKER_TYPE` selects SQS / RabbitMQ / InMemory via [CoreContainer](../../../src/_core/infrastructure/di/core_container.py). InMemory is the default and executes inline in the producer, so it cannot back a separate worker. stg/prod require an explicit broker. Tasks import the shared `broker` without conditional logic. Package extras and dependencies live in [pyproject.toml](../../../pyproject.toml); do not infer them from an old provider table.

### Embedding Pattern (PydanticAI Adapter)

One [PydanticAIEmbeddingAdapter](../../../src/_core/infrastructure/embedding/pydantic_ai_embedding_adapter.py) implements `BaseEmbeddingProtocol`; PydanticAI handles provider selection from the model-name prefix. CoreContainer selects the real adapter or `StubEmbedder`. Construct frozen `EmbeddingConfig` inside the lazy factory; `settings.embedding_dimension` owns dimension. Flags/fallbacks: [AGENTS.md](../../../AGENTS.md#optional-infrastructure-toggles).

### LLM Configuration (PydanticAI Agent)

[build_llm_model](../../../src/_core/infrastructure/llm/model_factory.py) creates the provider model; CoreContainer owns enabled/disabled selection and constructs `LLMConfig` inside the lazy factory. Disabled resolves to `TestModel` when the extra is installed, otherwise `None`. **Domain services receive a domain Protocol, never an SDK model or Agent.** Infrastructure adapters own `Agent(model=...)`; see [ClassificationContainer](../../../src/classification/infrastructure/di/classification_container.py) and [ClassificationService](../../../src/classification/domain/services/classification_service.py) (ADR 043). Provider formats / credentials follow the source owners in §2.

### S3 Vector Store DI Pattern

A vector-store Singleton receives `core_container.s3vector_client`, optional embedding client, and bucket setting; a domain service Factory receives the store. Use [DocsContainer](../../../src/docs/infrastructure/di/docs_container.py) for real/stub branching.

### Interface-Specific DI Pattern

| Interface | Outer decorator | Inner decorator | Service default | Wiring |
|-----------|----------------|-----------------|-----------------|--------|
| Server router | `@router.verb(...)` | `@inject` | `Depends(Provide[...])` | `wire(packages=[...routers])` |
| Admin page | `@ui.page(...)` | — | — | `bootstrap` injects `_service_provider` into `BaseAdminPage` |
| Worker task | `@broker.task(...)` | `@inject` | `Provide[...]` | `wire(modules=[...task])` |

- The `Depends()` wrapper is FastAPI-Router-only — it prevents FastAPI from interpreting the parameter as a query/body value.
- Worker tasks use bare `Provide[...]` because the framework does not interpret DI parameters on its own.
- Admin injects the provider into `BaseAdminPage._service_provider` and resolves the service internally.

## §6. Conversion Patterns

| Conversion | Pattern | Example |
|------|------|------|
| ORM → DTO | `ReturnDTO.model_validate(data, from_attributes=True)` | `UserDTO.model_validate(data, from_attributes=True)` |
| Request → Service | Direct pass `entity=item` (when fields match) | `create_data(entity=item)` |
| Request → DTO | `CreateDTO(**item.model_dump(), extra=...)` (when fields differ) | `CreateOrderDTO(**item.model_dump(), user_id=current_user.id)` |
| DTO → Response | `{Name}Response(**data.model_dump(exclude={...}))` | `UserResponse(**data.model_dump(exclude={"password"}))` |
| Message → Payload | `{Name}Payload.model_validate(kwargs)` | `UserTestPayload.model_validate(kwargs)` |
| Payload → Service | Direct pass `entity=payload` (when fields match) | `create_data(entity=payload)` |

## §7. Security Tools

### Pre-commit (Auto-run)

The installed formatting/security hooks and versions live in [pre-commit config](../../../.pre-commit-config.yaml): whitespace/newline, YAML/JSON/TOML, merge/debug/large-file checks, gitleaks and Ruff lint/format. Do not copy version numbers into this reference.

### Pre-commit (Manual Stage)

No manual-stage type checker remains. pyright is the sole type-check authority; mypy was retired in #375. Historical rationale is preserved in the [original snapshot](../../../docs/history/archive/harness-context/project-dna.md).

### CI Type Check and Dependency Audit (#333)

- **pyright blocks** and covers the repository, including tests and hidden harness directories. The authoritative include/exclude and rule settings live in [pyproject.toml](../../../pyproject.toml); never widen coverage by relaxing rules. Explicit `exclude` prevents the default `**/.*` from silently skipping included hook directories. [scope tests](../../../tests/unit/tools/test_pyright_scope.py) protect coverage and suppression locations. Unnecessary suppression comments are errors.
- **pip-audit is advisory**, covers shipped extras, and writes to the CI summary. Dependency audit follows [CI configuration](../../../.github/workflows/ci.yml).
- CI installs with `uv sync --locked`: a stale lock fails. `--frozen` accepts stale locks and is not an equivalent verification.

### Commit Message

- conventional-pre-commit (feat, fix, refactor, docs, chore, test, ci, perf, style, i18n)

### Architecture Violation Check (Auto-run)

Blocking: `no-domain-infra-import` (src), `no-domain-infra-import-examples` (relative imports in examples), `no-entity-pattern`, and `examples-copyflow`. Mapper prohibition is manual review, not a claimed pre-commit guarantee. Exact patterns and copy-flow smoke: [hook config](../../../.pre-commit-config.yaml) and [example tests](../../../tests/integration/examples).

### Content and Harness Guards (Auto-run)

- `tier1-language-policy` blocks Tier 1 language violations; checker globs and hook regex remain paired.
- `doc-links` blocks missing indexed paths and markdown anchors; full-repo `always_run` prevents unseen inbound breakage.
- `state-lifecycle-check` blocks tracked state; stale marker count is warn-only.
- `harness-hook-surface` blocks bare Python wrappers bypassing the shared launcher.
- `migration-safety` is advisory (ADR056-G1), because unsafe DDL depends on deployment context.

- `context-budget` blocks tracked harness byte overages (ADR 059): indexed-path selection with working-tree content, `always_run` and no filename filtering. Fenced examples skip line checks only. The hook checks sync-header shape and size, not date truth; dates recording the last substantive content change is a review rule.
- `harness-inventory` blocks generated-inventory drift and missing/unreviewed bucket decisions (ADR 062); the generator checks the indexed asset scope.
- `sensitive-logging` blocks same-line credential names in production logger/logging/print calls (ADR 061). It is lexical, not data-flow analysis; documented false-positive bypasses and review limits live in [CONTRIBUTING.md](../../../CONTRIBUTING.md#runtime-hook-retirement-and-production-logging).

Current registration and blocking/advisory flags: [pre-commit config](../../../.pre-commit-config.yaml). Register new local guards here when the command surface changes; use source links for implementation detail.

### Claude Hook

Live registration: [Claude settings](../../../.claude/settings.json); implementation: [hook wrappers](../../../.claude/hooks) and [shared governor policy](../../../.agents/shared/governor). Do not maintain a second per-event inventory here.

**Worktree ownership:** state and classification follow the validated payload `cwd` via `governor.resolve_session_roots`; only a worktree of the same repository is accepted. No `cwd` preserves the hook checkout, unplaceable `cwd` skips session work, and `HARNESS_STATE_ROOT` overrides state. Without git, only a `cwd` inside the hook checkout and outside nested checkouts is accepted. Codex/Antigravity already execute in the session tree; their shared ledger resolution retains the same contract. [worktree regression tests](../../../tests/unit/agents_shared/test_worktree_session_hooks.py) pin this boundary.

## §8. Active Features

| Feature | Status | Notes |
|------|------|------|
| Taskiq async tasks | Active | Broker abstraction (SQS/RabbitMQ/InMemory), @broker.task decorator |
| SQLAlchemy 2.0+ | Active | Mapped[T] + mapped_column() |
| Pydantic 2.x | Active | model_validate, model_dump, ConfigDict |
| dependency-injector | Active | DeclarativeContainer, @inject + Provide |
| Object Storage (aioboto3) | Active | S3/MinIO; optional `aws` extra. |
| AWS DynamoDB (aioboto3) | Active | Optional `aws` extra; BaseDynamoRepository. |
| NiceGUI (BaseAdminPage) | Active | Optional `admin` extra; token-less admin-identity session and per-page gates (§11 / §17). |
| alembic (migrations) | Active | DB migrations |
| Password hashing (bcrypt) | Active | hash_password(), verify_password() in src._core.common.security |
| AWS S3 Vectors (aioboto3) | Active | Optional `aws` extra; BaseS3VectorStore. |
| Embedding (PydanticAI) | Active | PydanticAIEmbeddingAdapter, BaseEmbeddingProtocol, auto-dimension, multi-provider |
| LLM (PydanticAI Agent) | Active | build_llm_model(), LLMConfig, Agent structured output |
| OpenTelemetry tracing | Active | Optional `otel` extra; server/worker instrumentation. See [OTEL runbook](../../../docs/operations/observability-otel.md). |
| Langfuse observability recipe | Active | Opt-in OTLP recipe. See [Langfuse runbook](../../../docs/operations/observability-langfuse.md). |
| Text chunking (semantic-text-splitter) | Active | chunk_text(), chunk_text_by_tokens() in src._core.common.text_utils |
| Structured Logging (structlog) | Active | Server/worker pipeline and sensitive-field prohibition: [AGENTS.md](../../../AGENTS.md#structured-logging). |
| JWT/Authentication | Active | HS256 access/refresh rotation, hashed persistence, Bearer-protected user routes (§15 / §17). |
| File Upload (UploadFile) | Not implemented | |
| RBAC/Permissions | Active | Admin-identity realm and per-page permissions (§17); `/v1/user` is admin-realm gated. Other non-user `/v1/*` route-level RBAC is not implemented. |
| Rate Limiting (slowapi) | Not implemented | |
| WebSocket | Not implemented | |
| Error Notification (Slack/Discord webhooks) | Active | [Toggle / dispatch authority](../../../AGENTS.md#optional-infrastructure-toggles); [operator runbook](../../../docs/operations/error-notifications.md). Developer invariants below. |

**Notification developer invariants (one home):**
- `install_task_middleware` registers the notifier after the same retry middleware instance; Taskiq calls `on_error` in reverse, so notification sees retry state before `_retries` is incremented.
- `ErrorNotifier._cooldown_key` and `NotificationRouter.resolve()` must use identical severity band tests, with both thresholds supplied from the same setting; an alert's cooldown tier must equal its delivery tier.
- The three client Selectors share one `_noop_notification_client` Singleton so disabled notification logs `notification_client_disabled` once. The router Selector's disabled branch is `providers.Object(None)`, not the Noop client.
- Exception handlers resolve `ErrorNotifier` at runtime through `request.app.state.container`; `_core/exceptions` never imports notification infrastructure, and dispatch never raises into the response path.

Guards: [middleware order](../../../tests/unit/_apps/worker/test_task_bootstrap_order.py), [cooldown](../../../tests/unit/_core/infrastructure/notification/test_error_notifier.py), [routing](../../../tests/unit/_core/infrastructure/notification/test_notification_router.py), [shared Noop](../../../tests/integration/_core/infrastructure/test_optional_infra.py). Optional extras and disabled behaviour are canonical in [AGENTS.md](../../../AGENTS.md#optional-infrastructure-toggles); dependency membership lives in [pyproject.toml](../../../pyproject.toml).

## §9. Router Pattern

Copy the live [user router](../../../src/user/interface/server/routers/user_router.py): `@router.verb` outside `@inject`, a `Depends(Provide[...])` service, Request passed directly as `entity=item`, and an explicit `SuccessResponse[Response]` conversion. Sensitive fields must be excluded from response dumps. [Scaffolding layers](../../../docs/ai/shared/scaffolding-layers.md) owns creation order.

## §10. Exception Pattern

Subclass `BaseCustomException` with explicit status, safe message, and stable error_code; use [domain exceptions](../../../src/user/domain/exceptions/user_exceptions.py) as the template. Never interpolate provider messages / internal DB details into client errors. Translation ownership is canonical in [AGENTS.md § Error Translation](../../../AGENTS.md#error-translation).

## §11. Admin Page Pattern

> Design system (#193): admin UI is token-driven (`_core/infrastructure/admin/theme.py`)
> and composed from the component builders in `_core/infrastructure/admin/components/`.
> CRUD pages are config-only and inherit it via `BaseAdminPage`; custom pages compose
> the builders. Catalog + DO/DON'T: [`admin-design-system.md`](admin-design-system.md).

### File Structure & Naming Convention

```
interface/admin/
├── configs/{name}_admin_config.py   # Config declaration
└── pages/{name}_page.py            # Route handlers
```

- Config variable: `{name}_admin_page = BaseAdminPage(...)` — name must match `{name}_admin_page` for auto-discovery
- Config module path: `src.{name}.interface.admin.configs.{name}_admin_config`
- Page module path: `src.{name}.interface.admin.pages.{name}_page`

### Config File Pattern (`configs/{name}_admin_config.py`)

Use [user admin config](../../../src/user/interface/admin/configs/user_admin_config.py) and [docs config with an extra query service](../../../src/docs/interface/admin/configs/docs_admin_config.py). Config is declaration-only: no `ui` import or routes. Sensitive columns are masked. `extra_services_config={alias: container_attr_name}` declares secondary services; bootstrap wires them and page handlers use `_get_extra_service(alias)`. The main CRUD provider satisfies `AdminCrudServiceProtocol`.

### Page File Pattern (`pages/{name}_page.py`)

Copy [user page](../../../src/user/interface/admin/pages/user_page.py). `@ui.page` stays outermost, with `@admin_error_boundary` inside. The first statement must enforce the page-key auth gate and return on `None`; then compose layout and delegate rendering to the config. Bootstrap injects the shared `page_configs` list. Event callbacks are separate invocations and call `AdminErrorHandler.handle` explicitly (IC-195-1 below).

### DI & Auto-discovery

- No `@inject`/`Provide` needed — service is resolved internally by `BaseAdminPage._service_provider`
- `bootstrap_admin()` auto-discovers domains via `discover_domains()`, loads config module, wires `_service_provider` from DI container, and imports page module (triggers `@ui.page` registration)
- `page_configs` list is injected by bootstrap into each page module (shared reference for navigation rendering)
- **No manual bootstrap registration needed** when adding admin pages to a domain

### Custom Rendering

For domain-specific rendering, subclass `BaseAdminPage` in the config file and override hook methods:
- `render_grid(dtos)` — custom AG Grid rendering
- `render_detail_card(dto)` — custom detail view
- `_fetch_list_data(page, search)` / `_fetch_detail_data(record_id)` — custom data fetching

### Admin Auth & Session (durable invariants — promoted from PR #155 ICs, extended by #194)

Admin identity is the `admin_identity` bounded context (ADR 049 / #218), not `user`. Historical IC-155 references to `User.role` / `User.permissions` mean the admin record / permissions. The session `role` is the constant `ADMIN_SESSION_ROLE`; membership is the admin role. Durable realm constraints remain in §17.

- **Session storage scope (IC-155-1)**: NiceGUI admin session storage may contain only the four authentication keys — `authenticated`, `user_id`, `username`, `role`. Access tokens, refresh tokens, raw JWTs, `permissions`, and `password_temporary` MUST NOT be stored in session. The ephemeral `setup_granted` flag is the sole permitted exception (set by login on bootstrap detect; cleared immediately after setup completes).
- **DB-membership + page-permission authorisation (IC-155-2, ADR 049 update)**: admin access requires the caller to resolve to an `admin_identity` record AND the target page key present in that record's `permissions`. Both are re-read from the DB on every request via `refresh_session()` — never cached from session. Unknown admins and wrong passwords surface as a single "invalid credentials" error to prevent enumeration.
- **One-time setup bootstrapping (IC-155-3)**: `ADMIN_BOOTSTRAP_*` env vars seed an `is_bootstrap_admin=True` row in `admin_identity` on boot. When no real admin (`is_bootstrap_admin=False`) exists, the bootstrap credential triggers the setup wizard — it never reaches the dashboard. Once the first real admin is created, the bootstrap row is deleted and the credential is permanently disabled (raises `AdminCredentialDisabledException`). Re-setting the env vars + restarting re-seeds the bootstrap row for recovery.
- **Mandatory page-key gate (IC-155-4)**: every `@ui.page("/admin/...")` route (except `/admin/login`, `/admin/setup`, and `/admin/error`) MUST call `require_auth(page_key="<key>")` or `require_auth_allowlisted()` as its first statement and return on `None`. `require_auth` enforces the IC-155-2 DB read + page-key check; `require_auth_allowlisted` enforces only the DB read (used for `dashboard` and `change-password`). Nav-drawer filtering is cosmetic only — the gate is the real control.
- **Centralized error handling (IC-195-1)**: admin errors route through `AdminErrorHandler` (`src/_core/infrastructure/admin/error_handler.py`) across three layers — (a) `@admin_error_boundary` on every `@ui.page` admin handler catches page-load errors; (b) event callbacks (button clicks, post-success refresh) call `AdminErrorHandler.handle(...)` directly; (c) a global `app.on_exception(handle_uncaught_admin_exception)` registered in `bootstrap_admin` structured-logs ANY uncaught admin exception (page / callback / timer) as a uniform last-resort safety net. Raw `str(exc)` is NEVER surfaced to the UI — only a 4xx `BaseCustomException.message` is shown (as a `warning`); `>= 500` domain errors and arbitrary exceptions show a generic message (`negative`). Full detail (`context`, `admin_user`, `error_type`, `error_code`; `request_id` auto-injected) goes to the structured server log only. An explicit `handle(..., critical=True)` redirects to `/admin/error`, the fourth gate-exempt route (IC-155-4): it has no auth gate (a critical failure may itself be a DB/auth outage and the gate hits the DB), performs no DB/session/`admin_layout` access, and echoes only a regex-validated correlation id passed via `?rid=`. No production path passes `critical=True` yet, so `/admin/error` is currently a defensive escalation surface; the global `on_exception` handler is the active uniform-logging control.

Quickstart prints the seeded `admin / admin` credentials only when `ENV=quickstart`; production / staging deployments must override the bootstrap env vars or disable seeding.

### Loading states (#198)

- **Async write buttons**: wrap the slow `await` in `async with button_loading(btn)` (`layout.py`) — it sets Quasar `loading`+`disable` and always clears in `finally`. Keep navigation / `dlg.close()` / list-refresh *outside* the `async with` so the button is not toggled after it may be torn down.
- **Page data loading**: `BaseAdminPage.render_list/render_detail` render a structure-mirroring skeleton, `await ui.context.client.connected()` before the fetch (so the skeleton is actually flushed to the client during a slow load), and delete the skeleton in `finally`. One change covers all domain pages; custom non-`BaseAdminPage` content areas (e.g. `docs_query_page`, `ai_usage_summary_page`) should provide appropriate inline feedback (e.g. `ui.spinner`) for their own slow fetches.

### Admin audit logging (#196 Phase 1 + #206 Phase 2)

- **Entry point / failure isolation:** [AuditLogger](../../../src/_core/infrastructure/admin/audit/logger.py) is the caller facade; it fills actor/correlation from session unless kwargs override, and never raises repository failures into a user action. Failures are structured-logged and notifier visibility follows the live logger. `audit_action` captures optional before/after state, logs SUCCESS/FAILURE, and re-raises the original action exception; capture-hook failures leave state `None`.
- **Append-only evidence:** [AdminAuditLog](../../../src/_core/infrastructure/admin/audit/models/audit_log_model.py) stores `admin_user_id` as correlation-only with **no foreign key** (ADR 057); `admin_username` is denormalised and survives account deletion. Action and result are orthogonal; record IDs permit strings/UUIDs. No account deletion may rewrite actor evidence.
- **Read / time boundary:** [audit repository](../../../src/_core/infrastructure/admin/audit/repository.py) uses a summary-column projection without large state JSON; detail fetches it on demand. Tz-aware caller filters are normalised to naive UTC before DB binding.
- **Snapshot safety:** [safe snapshot whitelist](../../../src/_core/infrastructure/admin/audit/safe_state.py) excludes passwords, token hashes, temporary credentials, raw exceptions and newly added DTO fields by default. `failure_reason` is a stable `error_code`, never `str(exc)`.
- **Registration:** server bootstrap and Alembic model loading both register the model. Audit package `__init__` must not re-export the NiceGUI-dependent logger, keeping the minimal-install path clean.
- **Instrumentation:** authenticate logs LOGIN; explicit user logout logs before session clear, while generic auth cleanup does not impersonate a logout. Account/setup/password write callbacks log results. `/admin/audit-log` requires `audit_log`; `log_reads=False` opts domains out of view events by default.
- **Retention:** `AUDIT_LOG_RETENTION_DAYS` is bounded 1–3650 (default 90). The decorated [cleanup task](../../../src/_apps/worker/tasks/audit_cleanup_task.py) can run from the optional scheduler, external cron or explicit enqueue; cleanup is an irreversible DELETE. Bootstrap wiring must cover worker, scheduler and InMemory producer paths. See [worker bootstrap](../../../src/_apps/worker/bootstrap.py) and [scheduler](../../../src/_apps/worker/scheduler.py).

## §12. S3 Vector Store Pattern

### VectorModel (Data Model)

Subclass `VectorModel` with `__vector_meta__: ClassVar[VectorModelMeta]` and typed metadata fields; `key` is UUID v4 hex, `data` is `VectorData(float32=[...])`. Filter/non-filter fields are explicit schema choices. Serialisation is owned by [VectorModel](../../../src/_core/infrastructure/vectors/vector_model.py); do not duplicate its API mapping.

### VectorModelMeta Fields

Field/default authority: [VectorModelMeta](../../../src/_core/infrastructure/vectors/vector_model.py). Do not silently alter existing index schema or expose provider models outside repositories.

### BaseS3VectorStore (Repository Counterpart)

Subclass [BaseS3VectorStore[DTO]](../../../src/_core/infrastructure/vectors/s3/base_store.py) with model/return_entity/bucket injection. Implement `_to_model` for DTO-to-vector conversion; return DTOs rather than exposing storage models.

### BaseVectorStoreProtocol Methods

Signatures: [BaseVectorStoreProtocol](../../../src/_core/domain/protocols/vector_store_protocol.py). Preserve the read-only collection convention in §3.

### S3 Vector Domain Variant (Directory Structure)

Infrastructure owns vector models/adapters and client injection. Domain Protocols and caller-facing DTOs contain no provider SDK types.

## §13. Embedding Pattern

### BaseEmbeddingProtocol

Contract: [BaseEmbeddingProtocol](../../../src/_core/domain/protocols/embedding_protocol.py). Translate SDK errors in infrastructure adapters.

### PydanticAI Embedding Adapter

One [adapter](../../../src/_core/infrastructure/embedding/pydantic_ai_embedding_adapter.py) bridges PydanticAI to the embedding Protocol and handles OpenAI batch splitting. Provider batching/credentials and dimension defaults are source-owned. Install `pydantic-ai`; Bedrock additionally requires `aws`, and provider-specific packages follow [extras](../../../pyproject.toml). `EmbeddingConfig` is a frozen domain VO; map SDK errors to domain exceptions in infrastructure, never the domain Service.

### Text Chunking Utilities

Use [text utilities](../../../src/_core/common/text_utils.py); their splitter already handles Unicode and tokenisation. Do not add a separate tiktoken dependency solely for these helpers.

## §14. LLM Pattern

### Model Factory

[build_llm_model](../../../src/_core/infrastructure/llm/model_factory.py) produces a model for an infrastructure adapter, never a domain Service. Canonical wiring: [ClassifierProtocol](../../../src/classification/domain/protocols/classifier_protocol.py) → [PydanticAIClassifier](../../../src/classification/infrastructure/classifier/pydantic_ai_classifier.py) / [StubClassifier](../../../src/classification/infrastructure/classifier/stub_classifier.py) → [Selector](../../../src/classification/infrastructure/di/classification_container.py). Domain Services consume the Protocol; agents are reusable and created once at adapter init. Model formats/credentials live in [provider helpers](../../../src/_core/infrastructure/ai/providers.py) and Settings. `LLMConfig` stays a frozen domain VO constructed in the factory. Structural prompt rules below remain canonical; read the adapter for formatting mechanics.

### Prompt-injection guardrails (#197)

`instructions=` separates user input; it is not a secrecy boundary (rendered instructions remain on ModelRequest).

Two layers, both living at the **adapter** boundary (not the PydanticAI Hooks/capabilities API — the adapters own the call sites, so plain functions are simpler, fully testable, and version-decoupled):

- **Structural (Phase 1+2, PR #208)**: `instructions=` over `system_prompt=`; every dynamic prompt field escaped via `escape_for_prompt_xml` and wrapped in named XML boundary tags; instruction constants typed `Final[LiteralString]`. See [prompt boundary helpers](../../../src/_core/infrastructure/llm/prompt_boundaries.py) and the classifier / RAG adapters linked above.
- **Runtime (Phase 3, #209)**: `src/_core/infrastructure/llm/guardrails.py` plain functions. `detect_prompt_injection` (input guard, scans every user-supplied field — RAG question; classifier `text` + each `categories` label — before `agent.run()`, raises `PromptInjectionDetected` 400). RAG output guard diffs `scan_pii(answer)` vs PII in `source_title`+`content` of the chunks and raises `GuardrailBlocked` 422 on fabrication; verbatim prompt-leak is log-only. `GUARDRAILS_ENABLED` (default True) is the DI-wired kill-switch. Guardrail exceptions carry no `details` (handler serializes `exc.details` to the response).
- **Observability (Phase 5, #211)**: `ai_usage.guardrail_triggered: bool` column (migration `0008`, with a `(guardrail_triggered, occurred_at)` index for the "blocked in last 24h" query). `track_agent_usage` is wired **inside** both adapters (`PydanticAIAnswerAgent.answer`, `PydanticAIClassifier.classify`) — Infrastructure→Application is allowed; the adapters take an `AgentUsageRecorderProtocol` and the concrete `ai_usage` import lives only in DI (`DocsContainer` / `ClassificationContainer`). The flag is set by a duck-typed `is_guardrail_block` class marker on the guardrail exceptions so `usage_tracker` never imports them (keeps the usage-tracker architecture test green). An input block records a zero-token row; an output block records consumed tokens (`capture.set_result` runs before the output guard). A guardrail block surfaces as `status='error'` + `guardrail_triggered=True` + `error_code` in `{PROMPT_INJECTION_DETECTED, GUARDRAIL_BLOCKED}`. Telemetry is standardized via `guardrail_telemetry.log_guardrail_event` (`agent`/`action`/`stage`/`rule` [+`count`/`types`]); `request_id`/`user_id` are bound to structlog contextvars at the request boundary (scoped unbind). Server-side `/v1/usage?guardrailTriggered=` filter + an `ai_usage` admin list column. Red-team corpus at `tests/integration/_core/infrastructure/llm/test_adversarial_prompts.py`.
- **Out of scope until a later phase**: `Document.trust_level`, base64/ROT13 decode (encoded-injection is a documented non-goal — the red-team suite asserts the structural boundary still holds), classifier output guard, per-user rate/budget caps (Phase 4 #210).

## §15. Auth Domain Pattern

The `auth` domain (PR #4 / PR #153) is a durable cross-cutting domain. The following invariants are promoted from PR #153 inherited constraints (ADR 047 IC promotion) and apply to all future auth-touching work.

### Domain shape

- **Non-CRUD domain (IC-153-1)**: `auth` does not follow the BaseService / BaseRepository CRUD scaffolding. `AuthService` exposes domain-specific methods (`register`, `login`, `refresh`, `logout`, `me`) instead of the generic CRUD verbs. Do not retrofit `BaseService[CreateDTO, UpdateDTO, ReturnDTO]` onto `AuthService` just to match the scaffolding pattern.

### Token persistence and shape

- **Refresh token persistence (IC-153-2)**: refresh tokens are NEVER stored in plaintext. Persistence stores keyed HMAC-SHA256 hashes plus `jti`, `user_id`, expiry, and revocation timestamps. Storage layout lives in the `refresh_token` table; rotation and revocation operate on the hash, not the raw token.
- **Stateless access tokens (IC-153-3)**: access tokens remain stateless for serverless compatibility. Server-side state is confined to refresh-token rotation and revocation; `/v1/auth/me` validates the access JWT alone without DB lookup beyond the user row.
- **JWT claim shape (IC-153-4 PR #155 version)**: access and refresh tokens carry the canonical claim set `sub`, `jti`, `type`, `iat`, `exp`, `iss`, `aud`. This shape is binding unless a later ADR explicitly supersedes issue #4.

### Surface and inheritance

- **Bearer protection (IC-153-5)**: existing `user` API routes are Bearer-protected. `/v1/auth/register` is the public signup path. New API routes default to Bearer-protected; public routes require explicit declaration in the router.
- **Future-work inheritance (IC-153-6)**: future RBAC, rate limiting, RS256 / key rotation, FastMCP auth integration, or non-user route protection MUST inherit this PR's JWT claim shape and refresh-token persistence unless a later ADR supersedes them. Treat this as a hard constraint when designing follow-up auth features.

## §16. Docs Frontend Contract

The `/docs` selector (PR #156) is the contributor-facing OpenAPI spec viewer. The following invariants are durable and govern future docs / spec work.

### Selector renderer

- **Single helper (IC-156-1)**: the selector renderer is a single `_render_selector` helper. Theme toggle JavaScript, FOUC-prevention inline script, and ARIA attributes are part of the production surface — they are not preview-time scaffolding to be stripped before merge.
- **Icon field with safe fallback (IC-156-2)**: `DOCS_CARDS` and `_handoff_cards()` carry an `icon` field. Renderers that omit the field MUST fall back via `.get("icon", "")` so a future card definition cannot raise `KeyError` in production traffic.
- **Kind discrimination (IC-156-3)**: `kind` (`primary` / `secondary`) is the canonical Recommended-vs-rest hierarchy carrier. Helpers that ignore `kind` (the Editorial regression in PR #156 R2.2) are a regression class — every list-row helper MUST read `kind`.

### Spec exposure

- **dev-only download endpoint (IC-156-4)**: `/openapi-download.json` is dev-only by design (gated indirectly through `docs_router` registration in `bootstrap.py`). Exposing the live spec in stg / prod requires an ADR; `TestDocsUrlGating` is the regression guard.

### UI hygiene

- **No AI-pattern clichés (IC-156-5)**: `linear-gradient`, `-webkit-background-clip`, `backdrop-filter`, ChatGPT-style purple gradient palettes, and similar AI-generated-UI clichés MUST stay out of the docs selector renderer. `test_docs_selector_returns_html` greps for the three CSS clichés as the regression guard. This is a docs-domain test, not a cross-cutting style governance rule.

## §17. Admin Identity Realm (ADR 049, #218)

Admin/operator identity is a dedicated bounded context (`src/admin_identity/`), physically and cryptographically separated from customer identity (`user`). The split exists for credential isolation (blast-radius) and a strong operational trust boundary. The following invariants are durable.

### Store separation

- **Separate identity store (IC-218-1)**: admins live in the `admin_identity` table; customers in `user`. No admin row may exist in `user`, and `user` carries no admin/role columns. Membership in `admin_identity` *is* the admin role — there is no `role` column on `admin_identity`. Cross-realm reads go only through the owning domain's repository/protocol.
- **Separate refresh store (IC-218-2)**: admin refresh tokens live in `admin_refresh_token` (FK `admin_id`), never `refresh_token` (FK `user_id`). IC-153-2 (hashed-only persistence) applies to both tables.

### Token realm (trust boundary)

- **Distinct token realm (IC-218-3)**: admin tokens are signed with `ADMIN_JWT_SECRET_KEY` and carry `ADMIN_JWT_ISSUER` / `ADMIN_JWT_AUDIENCE`, all distinct from the customer realm. The canonical claim shape (IC-153-4: `sub, jti, type, iat, exp, iss, aud`) is preserved; only `iss`/`aud`/secret differ. Collapsing the realms — admin secret, audience, or issuer equal to the customer realm's (`ADMIN_JWT_SECRET_KEY == JWT_SECRET_KEY`, `ADMIN_JWT_AUDIENCE == JWT_AUDIENCE`, or `ADMIN_JWT_ISSUER == JWT_ISSUER`) — is rejected at startup by `Settings._validate_environment_safety`. Never weaken this for convenience — it is what makes a customer token unusable on an admin route.
- **Realm-pinned verification (IC-218-4)**: `require_admin` (and any future admin-gated route) MUST verify admin-realm tokens against the `admin_identity` store. A customer-realm token presented to an admin route is rejected at the signature/audience layer (surfaces as `401 INVALID_TOKEN`), never reaching a role check. Bootstrap admins are setup-only and rejected by the gate (`403 FORBIDDEN`). Regression-guarded at both service and e2e level.

### Shared mechanism

- **Mechanism vs boundary (IC-218-5)**: auth *mechanism* is shared — `hash_password`/`verify_password` (`src/_core/common/security.py`) and `JwtTokenCodec` (`src/_core/common/jwt_codec.py`, config-injected). The *trust boundary* is per-realm — store, token config, refresh table, server dependency. New auth realms follow this split: share the mechanism, separate the boundary. Do not re-couple `AuthService` and `AdminAuthService` into one service.

### NiceGUI surface

- **Token-less dashboard session (IC-218-6)**: the NiceGUI admin dashboard keeps the IC-155-1 four-key, token-less session (`AdminAuthProvider`), now backed by `AdminAuthUseCase`. The admin token realm (IC-218-3) exists for the `/v1/admin/*` HTTP API, not the dashboard session. `ADMIN_BOOTSTRAP_*` seeds into `admin_identity`.

### Extension point

- **External IdP is out of scope (IC-218-7)**: external workforce IdP / SSO / MFA / SCIM and a physically separate admin database are NOT implemented. The sanctioned extension is to swap `AdminAuthService.verify_credentials` for an IdP-backed verifier and/or point the `admin_identity` repository at a separate database URL — no core change required.
