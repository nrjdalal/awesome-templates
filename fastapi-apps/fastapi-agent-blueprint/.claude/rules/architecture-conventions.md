# Architecture Conventions

> Last synced: 2026-08-12 via #368 (PRs #369, #370, #371, #373) — `count_datas_by_day` added to `BaseRepository` + `BaseRepositoryProtocol` + `BaseService` (the pairing rule is recorded below), returning the new `DailyCount` VO. Data flow, object roles and generic signatures are otherwise unchanged. Prior: 2026-08-11 via #365/PR #366 + PR #367 (admin neutral-mono restyle — **reviewed, structural patterns unchanged**. Data flow, object roles, generic signatures, and the Admin Page Config contract below are all untouched: the change is presentation-only, confined to `theme.py` / `layout.py` / `components/charts.py` token values plus the removal of the `/admin-static` mount. One durable constraint worth knowing when editing the admin shell, canonical in [`admin-design-system.md`](../../docs/ai/shared/admin-design-system.md): the Quasar `--q-*` brand group must be emitted under `body` with `!important`, because NiceGUI writes that palette as an inline body style that outranks any `:root` rule — a `:root` declaration is silently inert, which is what shipped from #193 until #365). Prior: 2026-08-01 via #286/PR #313 + #315/PR #319 (Error Notification — severity channel routing: three client Selectors sharing one Noop Singleton plus a router Selector resolving to None, the `_effective_min_threshold()` floor, the tier-scoped cooldown key, and the band-test invariant. Data-flow / object-role / generic-signature patterns unchanged). Prior: 2026-07-28 via #310 (Error Notification — worker task-failure dispatch + middleware ordering contract added below; the server-only scope from PR #311 is superseded. Data-flow / object-role / generic-signature patterns unchanged). Prior: 2026-07-27 via #307/PR #311 (Error Notification runbook — added the server-only dispatch scope to the optional-infra section below; data-flow / object-role / generic-signature patterns unchanged). Prior: 2026-07-23 via #17/PR #304 (Error Notification webhook infra — new optional-infra section added below; existing data-flow / object-role / generic-signature patterns unchanged). Prior: 2026-06-01 via #218 (admin-identity realm separation reviewed; the new `admin_identity` domain reuses the existing data flow / object roles / generic-signature patterns — BaseService/BaseRepository generics and conversion patterns are unchanged. New realm invariants live in project-dna §17.)
> For Absolute Prohibitions, Conversion Patterns, Write DTO criteria, Responsibility Matrix, Error Translation, Optional AI Infra (Protocol + Selector Pattern), Admin Service Contract, and **Default Coding Flow** (process layer, ADR 045), refer to AGENTS.md.
> This file only contains **structural context** that supplements AGENTS.md for Claude.

## Data Flow (3-Tier Hybrid)
```
Default (simple CRUD):
  Write: Request → Service(BaseService) → Repository → Model → DB
  Read:  Response ← Service ← Repository ← DTO ← Model

Complex logic:
  Write: Request → UseCase → Service → Repository → Model → DB
  Read:  Response ← UseCase ← Service ← Repository ← DTO ← Model
```
> UseCase is added only when combining multiple Services or crossing transaction boundaries
> For detailed Conversion Patterns: refer to the "Conversion Patterns" section in AGENTS.md

## DynamoDB Data Flow
```
  Write: Request → Service(BaseDynamoService) → Repository(BaseDynamoRepository) → DynamoModel → DynamoDB
  Read:  CursorPage[DTO] ← Service ← Repository ← DTO ← DynamoModel
```
Key differences from RDB:
- Composite keys via DynamoKey(partition_key, sort_key?)
- Cursor-based pagination via CursorPage (not offset-based)
- BaseDynamoService/BaseDynamoRepository — mirrors RDB counterparts

## S3 Vectors Data Flow
```
  Write: Entity → VectorStore(BaseS3VectorStore) → VectorModel → S3 Vectors API
  Read:  VectorSearchResult[DTO] ← VectorStore ← DTO ← S3 Vectors API response
```
Key differences from RDB/DynamoDB:
- String keys (UUID v4 hex) via `generate_vector_id`
- Similarity search via VectorQuery (top_k, filters) → VectorSearchResult
- Subclass must implement `_to_model()` for domain-specific DTO → VectorModel conversion
- `VectorModelMeta.dimension` auto-derived from `settings.embedding_dimension`

## BaseService Generic Structure
- `BaseService(Generic[CreateDTO, UpdateDTO, ReturnDTO])` — 3 TypeVars (ADR 011 update, 2026-04-09)
- `BaseRepositoryProtocol(Protocol, Generic[ReturnDTO])` / `BaseRepository(Generic[ReturnDTO])` — 1 TypeVar plus read primitives for Service-owned validation
- Aggregate read primitives come in pairs: a repository method that callers need must also exist on `BaseService`, because callers hold a service (the admin dashboard resolves `config._get_service()`, never a repository). `count_datas` / `count_datas_by_day` both follow this — repository + protocol + service pass-through, no `_validate_*` hook on the read path. Engine normalisation stays in `BaseRepository` (ADR 058) and the service layer must not mask it
- `BaseDynamoService(Generic[CreateDTO, UpdateDTO, ReturnDTO])` — mirrors BaseService
- `BaseDynamoRepositoryProtocol(Generic[ReturnDTO])` / `BaseDynamoRepository(Generic[ReturnDTO])` — mirrors BaseRepository
- `BaseVectorStoreProtocol(Generic[ReturnDTO])` / `BaseS3VectorStore(Generic[ReturnDTO])` — vector store pattern
- Domain Service example: `UserService(BaseService[CreateUserRequest, UpdateUserRequest, UserDTO])`
- DO NOT simplify back to 1 TypeVar — this was tried and reverted (see ADR 011 Post-decision Update)
- Service-owned CRUD write validation hooks are canonical in `AGENTS.md` § CRUD Write Validation; keep rule details there.

## Broker Selection
- `BROKER_TYPE` env var: SQS/RabbitMQ/InMemory via `providers.Selector` in CoreContainer. Task code uses `from src._apps.worker.broker import broker` with no conditional logic; stg/prod require explicit `BROKER_TYPE`.

## Storage Selection
- `STORAGE_TYPE` env var: S3/MinIO, same `ObjectStorageClient` class with different constructor params (no `providers.Selector` needed — contrast with Broker). Settings computed properties (`storage_access_key`, etc.) resolve fields by `STORAGE_TYPE`.

## Embedding (PydanticAI Adapter)
- Single `PydanticAIEmbeddingAdapter` replaces per-provider clients (ADR 039)
- No provider-level Selector — PydanticAI handles provider abstraction internally via `model_name` prefix
- `CoreContainer.embedding_client` wraps the adapter in `providers.Selector`: enabled → real adapter; disabled → `StubEmbedder` for graceful degradation (ADR 042)
- `EmbeddingConfig` (frozen dataclass VO) is constructed inside the lazy factory — not a standalone container provider
- Implements `BaseEmbeddingProtocol` (embed_text, embed_batch, dimension)
- Dimension auto-derived from model name — `settings.embedding_dimension` is single source of truth

## LLM (PydanticAI Agent)
- `build_llm_model()` factory returns PydanticAI Model object from `LLMConfig`
- `CoreContainer.llm_model` wraps the factory in `providers.Selector`: enabled → real model; disabled → PydanticAI `TestModel` via `build_stub_llm_model` (or `None` when the `pydantic-ai` extra is uninstalled) (ADR 042)
- `LLMConfig` (frozen dataclass VO) is constructed inside the lazy factory — not a standalone container provider
- Domain services inject the Selector-resolved `llm_model` and create `Agent(model=llm_model)` at init; stub propagates transparently
- Supports OpenAI, Anthropic, Bedrock providers via `model_name` prefix
- Agents are reusable across requests (create once at service init)

## Error Notification (Webhook)
- `NOTIFICATION_PROVIDER` env var: Slack/Discord via `providers.Selector` in CoreContainer; disabled → `NoopNotificationClient` (ADR 042). `BaseNotificationProtocol` lives in `src/_core/domain/protocols/`. Since #286 there are **four** notification Selectors. Three are client Selectors — `notification_client`, `notification_critical_client`, `notification_warning_client` — and they share **one** `_noop_notification_client` Singleton on their `disabled` branch. That sharing is load-bearing: `NoopNotificationClient` logs its warning from `__init__`, so a Singleton per Selector would emit one `notification_client_disabled` line per tier. Pinned by `test_noop_notification_client_disabled_warning_emitted_once`. The fourth Selector, `notification_router`, does **not** use the Noop client — its `disabled` branch is `providers.Object(None)`
- `ErrorNotifier` (Singleton) gates by an alerting floor of `_effective_min_threshold()` — `NOTIFICATION_SEVERITY_THRESHOLD` (default 500), or `min(severity, warning)` when routing is on — plus a per-process `NOTIFICATION_COOLDOWN_SECONDS` keyed on `error_code` (`{tier}:{error_code}` under routing); dispatch is fire-and-forget (`asyncio.create_task`, never awaited in the request path; send failures logged `exc_type`-only so the secret webhook URL never reaches logs)
- Hooked from `custom_exception_handler` / `generic_exception_handler` through `app.state.container` at runtime — the exceptions module never imports notification infrastructure, and dispatch never raises into the response path
- **Dispatch surface (#310)**: two `maybe_dispatch` call sites reached from four places — one in `_core/exceptions/exception_handlers.py` (inside `_dispatch_error_notification`, invoked from three handlers) and one in `TaskFailureNotificationMiddleware` (`_core/infrastructure/notification/taskiq_middleware.py`). `validation_exception_handler` (422) and `http_exception_handler` do **not** dispatch (pinned by negative tests), and the NiceGUI admin hook stays log-only as a stated non-goal — see AGENTS.md § Optional Infrastructure Toggles. Operator-facing writeup in [`docs/operations/error-notifications.md`](../../docs/operations/error-notifications.md)
- **Worker path specifics**: no HTTP status exists, so severity is synthesised (`BaseCustomException` keeps its `status_code`, else 500) and the cooldown key is scoped `{task_name}:{error_code}` — a bare code would let one noisy task mute every other task. The middleware supplies that composite as `error_code=`, and `ErrorNotifier` then applies its own tier prefix when routing is active, so the effective worker key is `{tier}:{task_name}:{error_code}`; the HTTP path's key is bare `error_code` only when no router is wired. Alerts fire once per incident on the terminal failure. The middleware reads retry state off the *same* `PermanentAwareSmartRetryMiddleware` instance registered on the broker, and must be registered **after** it: taskiq runs `on_error` over `reversed(middlewares)`, and the retry middleware mutates `message.labels["_retries"]` in place via an `AsyncKicker` that holds the dict by reference
- **Channel routing (#286, #315)**: `NOTIFICATION_WARNING_THRESHOLD` is the only switch — `_notification_routing_selector` gates `notification_router` on it alone, and `disabled=providers.Object(None)` means `ErrorNotifier` falls back to its `else self._client` branch, i.e. the #17 single-target path. The two per-tier webhook URLs are overrides, not switches: each falls back to the single provider webhook when unset, and setting one *without* the threshold is rejected at boot (before #315 it booted and silently ignored both). `NotificationRouter.resolve()` returning `None` means do-not-dispatch. **Invariant**: the band test in `ErrorNotifier._cooldown_key` must stay identical to `NotificationRouter.resolve()`'s, or an alert can be keyed to one tier and delivered to the other — the two hold independent copies of `severity_threshold`, kept equal only because the container feeds both from one setting. Boot validation enforces `warning_threshold < severity_threshold`, which is what guarantees a widened gate always lands in a resolvable tier
- Adapters POST via the shared `HttpClient` and never JSON-parse webhook responses (Slack success body is plain-text `ok`; Discord returns `204 No Content`)

## Object Roles

### DTO (Domain DTO)
- Location: `src/{domain}/domain/dtos/{domain}_dto.py`
- Role: Carries read results from Repository → Service → Router (full data)
- **Read-only, single type**: `{Name}DTO` — may include sensitive fields (password, etc.)
- Create/Update DTO is only created separately when fields differ from Request

### Value Object vs DTO — decision rule
- **VO (`src/_core/domain/value_objects/`)**: frozen, value-equal, self-validating. Represents a domain concept whose identity IS its fields (e.g. `VectorQuery`, `EmbeddingConfig`, `LLMConfig`, `DynamoKey`, `QueryFilter`).
  - Prefer `@dataclass(frozen=True)` for config-only VOs (no runtime validation needed).
  - Use `ValueObject(BaseModel, frozen=True)` base when Pydantic validators are required.
- **Shared DTO (`src/_core/domain/dtos/`)**: transfer/carrier across layers. Not frozen. Mutable transients allowed (e.g. `RagPipeline` attaches `_distance` on `BaseChunkDTO`). Read-result containers that are intrinsically values AND never mutated (e.g. `CursorPage`, `VectorSearchResult`) stay in `value_objects/` as frozen VOs.
- **Rule of thumb**: "Can I hand this to another layer and expect it to never change downstream?" — yes → VO (frozen). no → DTO.
- Suffix `DTO` on class names signals carrier role (ADR 004). VOs keep their domain name without suffix.

### API Schema (Interface DTO)
- Location: `src/{domain}/interface/server/schemas/{domain}_schema.py`
- Inherits `BaseRequest` / `BaseResponse`
- Explicit field declarations
- Intentionally excludes sensitive fields (Response)
- When fields are identical, Request also serves as the layer DTO

### Model (SQLAlchemy ORM)
- Location: `src/{domain}/infrastructure/database/models/{domain}_model.py`
- Must never leave the Repository layer
- Conversion: `DTO → Model: Model(**dto.model_dump())`
- Conversion: `Model → DTO: DTO.model_validate(model, from_attributes=True)`

### DynamoModel
- Location: `src/{domain}/infrastructure/dynamodb/models/{domain}_model.py`
- Uses `DynamoModelMeta` + `__dynamo_meta__` for table schema declaration
- Must never leave the Repository layer (same rule as ORM Model)

### VectorModel
- Location: `src/{domain}/infrastructure/vectors/models/{domain}_model.py`
- Uses `VectorModelMeta` + `__vector_meta__` for index schema declaration
- Must never leave the VectorStore layer (same rule as ORM Model/DynamoModel)
- Conversion: `Entity → Model: _to_model()` (abstract, subclass implements)
- Conversion: `API response → DTO: return_entity.model_validate(metadata)`

### Admin Page Config (BaseAdminPage)
- Config: `src/{domain}/interface/admin/configs/{domain}_admin_config.py`
- Page: `src/{domain}/interface/admin/pages/{domain}_page.py`
- Config-only declaration (no ui import); route handlers in separate page file
- DI: _service_provider internal resolve (no @inject/Provide)
