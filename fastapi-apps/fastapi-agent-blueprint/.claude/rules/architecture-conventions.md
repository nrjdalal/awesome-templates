---
paths:
  - "src/**"
  - "examples/**"
  - "tests/**"
  - "migrations/**"
---

# Architecture Conventions

> Last synced: 2026-11-06 via #414 B1/B4/B5
> For Absolute Prohibitions, Conversion Patterns, Write DTO criteria, Responsibility Matrix, Error Translation, Optional AI Infra (Protocol + Selector Pattern), Admin Service Contract, Optional Infrastructure Toggles (Error Notification), and **Default Coding Flow** (process layer, ADR 045), refer to AGENTS.md.
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
- `BaseRepositoryProtocol(Protocol, Generic[ReturnDTO])` / `BaseRepository(Generic[ReturnDTO])` — 1 TypeVar plus read primitives for Service-owned validation. Write inputs that are only iterated take `Sequence[BaseModel]`, never `list[BaseModel]`: `list` is invariant, so the narrower spelling forces every caller holding `list[MyDTO]` into a cast. An implementation or test double with a *narrower* parameter than the protocol does not satisfy it — that is how #395 found two doubles that had drifted from the interfaces they impersonate
- Aggregate read primitives come in pairs: a repository method that callers need must also exist on `BaseService`, because callers hold a service (the admin dashboard resolves `config._get_service()`, never a repository). `count_datas` / `count_datas_by_day` both follow this — repository + protocol + service pass-through, no `_validate_*` hook on the read path. Engine normalisation stays in `BaseRepository` (ADR 058) and the service layer must not mask it
- `BaseDynamoService(Generic[CreateDTO, UpdateDTO, ReturnDTO])` — mirrors BaseService
- `BaseDynamoRepositoryProtocol(Generic[ReturnDTO])` / `BaseDynamoRepository(Generic[ReturnDTO])` — mirrors BaseRepository
- `BaseVectorStoreProtocol(Generic[ReturnDTO])` / `BaseS3VectorStore(Generic[ReturnDTO])` — vector store pattern
- Domain Service example: `UserService(BaseService[CreateUserRequest, UpdateUserRequest, UserDTO])`
- DO NOT simplify back to 1 TypeVar — this was tried and reverted (see ADR 011 Post-decision Update)
- Service-owned CRUD write validation hooks are canonical in `AGENTS.md` § CRUD Write Validation; keep rule details there.

## Optional Infrastructure Selection

See [project-dna.md §5](../../docs/ai/shared/project-dna.md#5-di-pattern) for the canonical provider policy and [CoreContainer](../../src/_core/infrastructure/di/core_container.py) for live wiring. Storage uses enabled/disabled Selectors with lazy factories; provider-specific S3/MinIO parameters come from Settings.

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
