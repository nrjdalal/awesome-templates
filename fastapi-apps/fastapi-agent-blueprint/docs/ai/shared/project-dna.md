# Project DNA - Shared Pattern Reference Extracted from Code

> Shared canonical reference for both Claude and Codex workflow assets.
> Update this file when shared architecture patterns change, then sync the harness docs that point to it.

> This file is auto-extracted/updated from `src/user/` (reference domain) and `src/_core/` (Base classes)
> when `/sync-guidelines` is run. **Run `/sync-guidelines` instead of editing manually.**
>
> Last updated: 2026-06-01 (#211 / #197 Phase 5 — guardrail observability ledger + red-team suite)

## Section Index
§0 Project Scale and Design Philosophy |
§1 Directory Structure | §2 Base Class Path | §3 Generic Type Signatures | §4 CRUD Methods
§5 DI Pattern | §6 Conversion Patterns | §7 Security Tools | §8 Active Features
§9 Router Pattern | §10 Exception Pattern | §11 Admin Page Pattern
§12 S3 Vector Store Pattern | §13 Embedding Pattern | §14 LLM Pattern
§15 Auth Domain Pattern | §16 Docs Frontend Contract

> **Visual summary:** see [`architecture-diagrams.md`](architecture-diagrams.md)
> for the layer dependency graph, Write/Read data flow (RDB), and the
> RDB / DynamoDB / S3 Vectors variant table. The sections below are the
> authoritative text reference; the diagrams exist to orient new readers
> before they dig into §1–§14.

---

## §0. Project Scale and Design Philosophy

### Scale
- AI Agent Backend Platform targeting enterprise-grade services with 10+ domains and 5+ team members
- All proposals and designs must consider scalability, maintainability, and team collaboration at this scale

### Enterprise Practice Criteria for Proposals

Skills proactively consider the following perspectives when generating code, making design proposals, or performing reviews:

**Scalability**
- List query APIs always include pagination by default
- Suggest separating into async Worker tasks when large-scale data processing is expected
- Specify joinedload/selectinload for relationship queries that risk N+1 queries

**Team Collaboration**
- Cross-domain dependencies must always be proposed via Protocol-based DIP (direct import proposals are prohibited)
- When modifying shared DTOs, first analyze the impact scope (which domains reference them)
- API signature changes are proposed with backward compatibility by default

**Operations**
- Data mutation (CUD) APIs must verify whether audit trail is needed
- Suggest timeout, retry, and circuit breaker settings when integrating with external APIs
- Error responses must include error_codes at a level that clients can act upon

**Security**
- Sensitive data (PII) must be excluded from Responses and not logged
- Endpoints requiring authentication must be explicitly marked
- Environment-specific settings (secrets, DB URLs) must be managed via environment variables only

---

## §1. Layer Directory Structure

```
src/{name}/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── dtos/{name}_dto.py
│   ├── protocols/{name}_repository_protocol.py
│   ├── services/{name}_service.py
│   ├── exceptions/{name}_exceptions.py
│   └── value_objects/                    # (as needed)
├── application/                           # (optional — only for complex logic)
│   ├── __init__.py
│   └── use_cases/{name}_use_case.py
├── infrastructure/
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── models/{name}_model.py
│   ├── repositories/{name}_repository.py
│   └── di/{name}_container.py
└── interface/
    ├── __init__.py
    ├── server/
    │   ├── schemas/{name}_schema.py
    │   ├── routers/{name}_router.py
    │   └── bootstrap/{name}_bootstrap.py
    ├── admin/
    │   ├── configs/{name}_admin_config.py
    │   └── pages/{name}_page.py
    └── worker/
        ├── payloads/{name}_payload.py
        ├── tasks/{name}_test_task.py
        └── bootstrap/{name}_bootstrap.py
```

### DynamoDB Domain Variant

A domain backed by DynamoDB uses `infrastructure/dynamodb/` instead of `infrastructure/database/`:

```
src/{name}/
├── infrastructure/
│   ├── dynamodb/
│   │   └── models/{name}_model.py    # extends DynamoModel
│   ├── repositories/{name}_repository.py  # extends BaseDynamoRepository
│   └── di/{name}_container.py        # dynamodb_client=core_container.dynamodb_client
└── (everything else identical)
```

## §2. Base Class Import Path

| Class | Import Path |
|---------|------------|
| BaseRepositoryProtocol | `src._core.domain.protocols.repository_protocol.BaseRepositoryProtocol` |
| BaseService | `src._core.domain.services.base_service.BaseService` |
| ValidationErrorDetail | `src._core.domain.validation.ValidationErrorDetail` |
| ValidationFailed | `src._core.domain.validation.ValidationFailed` |
| BaseRepository | `src._core.infrastructure.persistence.rdb.base_repository.BaseRepository` |
| Base (ORM DeclarativeBase) | `src._core.infrastructure.persistence.rdb.database.Base` |
| Database | `src._core.infrastructure.persistence.rdb.database.Database` |
| BaseDynamoRepositoryProtocol | `src._core.domain.protocols.dynamo_repository_protocol.BaseDynamoRepositoryProtocol` |
| BaseDynamoService | `src._core.domain.services.base_dynamo_service.BaseDynamoService` |
| BaseDynamoRepository | `src._core.infrastructure.persistence.nosql.dynamodb.base_dynamo_repository.BaseDynamoRepository` |
| DynamoModel | `src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model.DynamoModel` |
| DynamoModelMeta | `src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model.DynamoModelMeta` |
| GSIDefinition | `src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model.GSIDefinition` |
| DynamoDBClient | `src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_client.DynamoDBClient` |
| DynamoKey | `src._core.domain.value_objects.dynamo_key.DynamoKey` |
| SortKeyCondition | `src._core.domain.value_objects.dynamo_key.SortKeyCondition` |
| CursorPage | `src._core.domain.value_objects.cursor_page.CursorPage` |
| CursorPaginationInfo | `src._core.application.dtos.base_response.CursorPaginationInfo` |
| BaseRequest | `src._core.application.dtos.base_request.BaseRequest` |
| BaseResponse | `src._core.application.dtos.base_response.BaseResponse` |
| SuccessResponse | `src._core.application.dtos.base_response.SuccessResponse` |
| ErrorResponse | `src._core.application.dtos.base_response.ErrorResponse` |
| PaginationInfo | `src._core.application.dtos.base_response.PaginationInfo` |
| BasePayload | `src._core.application.dtos.base_payload.BasePayload` |
| PayloadConfig | `src._core.application.dtos.base_config.PayloadConfig` |
| ApiConfig | `src._core.application.dtos.base_config.ApiConfig` |
| BaseCustomException | `src._core.exceptions.base_exception.BaseCustomException` |
| ValueObject | `src._core.domain.value_objects.value_object.ValueObject` |
| QueryFilter | `src._core.domain.value_objects.query_filter.QueryFilter` |
| make_pagination | `src._core.common.pagination.make_pagination` |
| hash_password | `src._core.common.security.hash_password` |
| verify_password | `src._core.common.security.verify_password` |
| AdminCrudServiceProtocol | `src._core.domain.protocols.admin_service_protocol.AdminCrudServiceProtocol` |
| BaseVectorStoreProtocol | `src._core.domain.protocols.vector_store_protocol.BaseVectorStoreProtocol` |
| BaseEmbeddingProtocol | `src._core.domain.protocols.embedding_protocol.BaseEmbeddingProtocol` |
| BaseS3VectorStore | `src._core.infrastructure.vectors.s3.base_store.BaseS3VectorStore` |
| VectorModel | `src._core.infrastructure.vectors.vector_model.VectorModel` |
| VectorModelMeta | `src._core.infrastructure.vectors.vector_model.VectorModelMeta` |
| VectorData | `src._core.infrastructure.vectors.vector_model.VectorData` |
| S3VectorClient | `src._core.infrastructure.vectors.s3.client.S3VectorClient` |
| VectorQuery | `src._core.domain.value_objects.vector_query.VectorQuery` |
| VectorSearchResult | `src._core.domain.value_objects.vector_search_result.VectorSearchResult` |
| PydanticAIEmbeddingAdapter | `src._core.infrastructure.embedding.pydantic_ai_embedding_adapter.PydanticAIEmbeddingAdapter` |
| EmbeddingConfig | `src._core.domain.value_objects.embedding_config.EmbeddingConfig` |
| LLMConfig | `src._core.domain.value_objects.llm_config.LLMConfig` |
| build_llm_model | `src._core.infrastructure.llm.model_factory.build_llm_model` |
| chunk_text | `src._core.common.text_utils.chunk_text` |
| chunk_text_by_tokens | `src._core.common.text_utils.chunk_text_by_tokens` |
| generate_vector_id | `src._core.common.uuid_utils.generate_vector_id` |
| CoreContainer | `src._core.infrastructure.di.core_container.CoreContainer` |

### Inheritance Chain

- `BaseRequest` → `ApiConfig` → `BaseModel` (camelCase alias, frozen, populate_by_name)
- `BaseResponse` → `ApiConfig` → `BaseModel`
- `SuccessResponse` → `ApiConfig`, `Generic[ReturnType]`
- `BasePayload` → `PayloadConfig` → `BaseModel` (frozen, extra="forbid", no alias)
- `ValueObject` → `BaseModel` (frozen=True)

## §3. Generic Type Signatures

```python
# BaseRepositoryProtocol / BaseRepository — 1 TypeVar (ReturnDTO only)
# Repository write inputs stay BaseModel; read primitives support Service-owned validation.
ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)

class BaseRepositoryProtocol(Protocol, Generic[ReturnDTO]): ...
class BaseRepository(Generic[ReturnDTO], ABC): ...

# BaseService — 3 TypeVars (CreateDTO, UpdateDTO, ReturnDTO)
# Service overrides access specific fields and validation hooks, so typed inputs are required
# Background: ADR 011 Post-decision Update (2026-04-09)
CreateDTO = TypeVar("CreateDTO", bound=BaseModel)
UpdateDTO = TypeVar("UpdateDTO", bound=BaseModel)

class BaseService(Generic[CreateDTO, UpdateDTO, ReturnDTO]): ...

# SuccessResponse
ReturnType = TypeVar("ReturnType")
class SuccessResponse(ApiConfig, Generic[ReturnType]): ...

# Reference domain (user) usage example:
class UserRepositoryProtocol(BaseRepositoryProtocol[UserDTO], Protocol): pass
class UserRepository(BaseRepository[UserDTO]): ...
class UserService(BaseService[CreateUserRequest, UpdateUserRequest, UserDTO]): ...
```

### DynamoDB Generic Type Signatures

```python
# BaseDynamoRepositoryProtocol / BaseDynamoRepository — 1 TypeVar (ReturnDTO only)
class BaseDynamoRepositoryProtocol(Generic[ReturnDTO]): ...
class BaseDynamoRepository(Generic[ReturnDTO], ABC): ...

# BaseDynamoService — 3 TypeVars (CreateDTO, UpdateDTO, ReturnDTO)
class BaseDynamoService(Generic[CreateDTO, UpdateDTO, ReturnDTO]): ...

# DynamoDB domain usage example:
class ChatRoomRepositoryProtocol(BaseDynamoRepositoryProtocol[ChatRoomDTO]): pass
class ChatRoomRepository(BaseDynamoRepository[ChatRoomDTO]): ...
class ChatRoomService(BaseDynamoService[CreateChatRoomRequest, UpdateChatRoomRequest, ChatRoomDTO]): ...
```

### S3 Vector Store Generic Type Signatures

```python
# BaseVectorStoreProtocol — typing.Protocol (runtime_checkable), 1 TypeVar
# BaseS3VectorStore — ABC with concrete implementation (Generic base)
class BaseVectorStoreProtocol(Protocol[ReturnDTO]): ...
class BaseS3VectorStore(Generic[ReturnDTO], ABC): ...

# S3 Vector domain usage example:
class DocumentVectorStoreProtocol(BaseVectorStoreProtocol[DocumentDTO]): pass
class DocumentS3VectorStore(BaseS3VectorStore[DocumentDTO]): ...
```

### BaseS3VectorStore.__init__ Signature

```python
def __init__(
    self,
    s3vector_client: S3VectorClient,
    *,
    model: type[VectorModel],
    return_entity: type[ReturnDTO],
    bucket_name: str,
) -> None:
```

### BaseRepository.__init__ Signature

```python
def __init__(
    self,
    database: Database,
    *,
    model: type[Base],
    return_entity: type[ReturnDTO],
) -> None:
```

## §4. Base CRUD Methods

### BaseRepositoryProtocol Methods

| Method | Signature |
|--------|---------|
| insert_data | `async (entity: BaseModel) -> ReturnDTO` |
| insert_datas | `async (entities: list[BaseModel]) -> list[ReturnDTO]` |
| select_datas | `async (page: int, page_size: int) -> list[ReturnDTO]` |
| select_data_by_id | `async (data_id: int) -> ReturnDTO` |
| select_datas_by_ids | `async (data_ids: list[int]) -> list[ReturnDTO]` |
| exists_by_id | `async (data_id: int) -> bool` |
| exists_by_fields | `async (filters: Mapping[str, Any], *, exclude_id: int \| None = None) -> bool` |
| existing_values_by_field | `async (field: str, values: list[Any], *, exclude_id: int \| None = None) -> set[Any]` |
| select_datas_with_count | `async (page: int, page_size: int, query_filter: QueryFilter \| None = None) -> tuple[list[ReturnDTO], int]` |
| update_data_by_data_id | `async (data_id: int, entity: BaseModel) -> ReturnDTO` |
| delete_data_by_data_id | `async (data_id: int) -> bool` |
| count_datas | `async () -> int` |

### BaseService Methods (Repository Delegation Mapping)

> `BaseService[CreateDTO, UpdateDTO, ReturnDTO]` provides all methods below.
> Domain Services extend `BaseService[Create{Name}Request, Update{Name}Request, {Name}DTO]` and only override when custom logic is needed.

| BaseService Method | Signature | Repository Call |
|-------------------|-----------|----------------|
| create_data | `(entity: CreateDTO) -> ReturnDTO` | `_validate_create(entity)` then `insert_data(entity=entity)` |
| create_datas | `(entities: list[CreateDTO]) -> list[ReturnDTO]` | `_validate_create_many(entities)` then `insert_datas(entities=entities)` |
| get_datas | `(page, page_size, query_filter) -> (list[ReturnDTO], PaginationInfo)` | select_datas_with_count(...) |
| get_data_by_data_id | `(data_id: int) -> ReturnDTO` | select_data_by_id(data_id=data_id) |
| get_datas_by_data_ids | `(data_ids: list[int]) -> list[ReturnDTO]` | select_datas_by_ids(data_ids=data_ids) |
| update_data_by_data_id | `(data_id: int, entity: UpdateDTO) -> ReturnDTO` | `_validate_update(data_id, entity)` then `update_data_by_data_id(data_id, entity)` |
| delete_data_by_data_id | `(data_id: int) -> bool` | `_validate_delete(data_id)` then `delete_data_by_data_id(data_id=data_id)` |
| count_datas | `() -> int` | count_datas() |

### BaseService Validation Hooks

`BaseService` owns pre-write validation. Hooks are protected async methods with
no-op defaults; domain Services override only the hooks that have explicit
business rules.

| Hook | Signature | Default |
|------|-----------|---------|
| _validate_create | `async (entity: CreateDTO) -> None` | no-op |
| _validate_create_many | `async (entities: list[CreateDTO]) -> None` | no-op |
| _validate_update | `async (data_id: int, entity: UpdateDTO) -> None` | no-op |
| _validate_delete | `async (data_id: int) -> None` | no-op |

Reusable validation helpers live in `_core/domain/validation.py`. Domain-specific
composition belongs in `{domain}/domain/validators.py` when the rule set is
non-trivial.

### BaseDynamoRepositoryProtocol Methods

| Method | Signature |
|--------|---------|
| put_item | `async (entity: BaseModel) -> ReturnDTO` |
| get_item | `async (key: DynamoKey) -> ReturnDTO` |
| query_items | `async (partition_key_value: str, sort_key_condition?, index_name?, filter_expression?, limit?, cursor?, scan_forward?) -> CursorPage[ReturnDTO]` |
| update_item | `async (key: DynamoKey, entity: BaseModel) -> ReturnDTO` |
| delete_item | `async (key: DynamoKey) -> bool` |

### BaseDynamoService Methods

| Method | Signature | Repository Call |
|--------|-----------|----------------|
| create_item | `(entity: CreateDTO) -> ReturnDTO` | put_item(entity=entity) |
| get_item | `(key: DynamoKey) -> ReturnDTO` | get_item(key=key) |
| query_items | `(partition_key_value, ...) -> CursorPage[ReturnDTO]` | query_items(...) |
| update_item | `(key: DynamoKey, entity: UpdateDTO) -> ReturnDTO` | update_item(key, entity) |
| delete_item | `(key: DynamoKey) -> bool` | delete_item(key=key) |

### DynamoDB DI Pattern

```python
class {Name}Container(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    {name}_repository = providers.Singleton(
        {Name}Repository,
        dynamodb_client=core_container.dynamodb_client,  # ← DynamoDB
    )

    {name}_service = providers.Factory(
        {Name}Service,
        {name}_repository={name}_repository,
    )
```

## §5. DI Pattern

```python
from dependency_injector import containers, providers

class {Name}Container(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    {name}_repository = providers.Singleton(
        {Name}Repository,
        database=core_container.database,
    )

    {name}_service = providers.Factory(
        {Name}Service,
        {name}_repository={name}_repository,
    )

    # Add UseCase only when complex business logic is needed
    # {name}_use_case = providers.Factory(
    #     {Name}UseCase,
    #     {name}_service={name}_service,
    # )
```

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

Domain Containers use `DeclarativeContainer`,
but Server/Worker App-level Containers use `DynamicContainer` + factory functions.
`discover_domains()` automatically detects and registers valid domains under `src/*/`,
so **no App-level container/bootstrap file modifications are needed when adding a new domain.**

```python
# src/_apps/server/di/container.py
from src._core.infrastructure.discovery import discover_domains, load_domain_container

def create_server_container() -> containers.DynamicContainer:
    container = containers.DynamicContainer()
    container.core_container = providers.Container(CoreContainer)
    for domain in discover_domains():
        cls = load_domain_container(domain)
        setattr(container, f"{domain}_container",
                providers.Container(cls, core_container=container.core_container))
    return container
```

### Broker Selection Pattern (Runtime Configuration)

The message broker uses `providers.Selector` to dynamically select between broker backends
based on the `BROKER_TYPE` environment variable:

```python
# src/_core/infrastructure/di/core_container.py
broker = providers.Selector(
    lambda: (settings.broker_type or "inmemory").lower().strip(),
    sqs=providers.Singleton(CustomSQSBroker, queue_url=..., ...),
    rabbitmq=providers.Singleton(create_rabbitmq_broker, url=...),
    inmemory=providers.Singleton(InMemoryBroker),
)
```

| BROKER_TYPE | Broker Class | Dependency |
|-------------|-------------|------------|
| `sqs` | `CustomSQSBroker` | `taskiq-aws` (main) |
| `rabbitmq` | `AioPikaBroker` | `taskiq-aio-pika` (optional) |
| `inmemory` (default) | `InMemoryBroker` | `taskiq` (main) |

- Selector evaluates at container creation time; selected Singleton is cached
- Task code always uses `from src._apps.worker.broker import broker` — no conditional logic needed
- stg/prod environments require explicit `BROKER_TYPE` setting

### Embedding Pattern (PydanticAI Adapter)

Embedding uses a single `PydanticAIEmbeddingAdapter` — no per-provider `providers.Selector` needed.
PydanticAI is the abstraction layer; the adapter bridges it to `BaseEmbeddingProtocol`.
(Background: ADR 039 — "external framework IS the abstraction" pattern from ADR 037)

CoreContainer wraps `embedding_client` in a Selector that returns `StubEmbedder` when `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` are unset, so consumer domains degrade gracefully (ADR 042):

```python
# src/_core/infrastructure/di/core_container.py
def _embedding_selector() -> str:
    return "enabled" if settings.embedding_model_name else "disabled"

embedding_client = providers.Selector(
    _embedding_selector,
    enabled=providers.Singleton(
        _build_embedding_client,
        model_name=settings.embedding_model_name,
        dimension=settings.embedding_dimension,
        api_key=settings.embedding_openai_api_key,
        aws_access_key_id=settings.embedding_bedrock_access_key,
        aws_secret_access_key=settings.embedding_bedrock_secret_key,
        aws_region=settings.embedding_bedrock_region,
    ),
    disabled=providers.Singleton(_build_stub_embedder, dimension=settings.embedding_dimension),
)
```

| EMBEDDING_PROVIDER | Model Name Format | Dependency |
|-------------------|------------------|------------|
| `openai` | `openai:text-embedding-3-small` | `pydantic-ai` extra (includes `tiktoken`) |
| `bedrock` | `bedrock:amazon.titan-embed-text-v2:0` | `pydantic-ai` extra + `aws` extra (aioboto3) |
| `google` | `google:text-embedding-004` | `pydantic-ai-google` extra |
| `ollama` | `ollama:nomic-embed-text` | `pydantic-ai` extra |

- Single adapter implements `BaseEmbeddingProtocol` (embed_text, embed_batch, dimension)
- `EmbeddingConfig`: frozen dataclass value object (domain layer) carrying provider+credentials
- Provider selection happens inside adapter via `model_name` prefix format
- Dimension is auto-derived from model name — `settings.embedding_dimension` is single source of truth

### LLM Configuration (PydanticAI Agent)

LLM uses `build_llm_model()` factory to construct a PydanticAI Model object.
Domain services receive the pre-built model and create `Agent(model=...)` instances.
(Background: ADR 037 — PydanticAI Agent pattern; ADR 042 — Selector + lazy factory)

CoreContainer wraps `llm_model` in a Selector whose disabled branch returns a PydanticAI `TestModel` (via `build_stub_llm_model`) so any domain that does `Agent(model=core_container.llm_model)` degrades gracefully when `LLM_PROVIDER` / `LLM_MODEL` are unset:

```python
# src/_core/infrastructure/di/core_container.py
def _llm_selector() -> str:
    return "enabled" if settings.llm_model_name else "disabled"

llm_model = providers.Selector(
    _llm_selector,
    enabled=providers.Singleton(
        _build_llm_model,
        model_name=settings.llm_model_name or "",
        api_key=settings.llm_api_key,
        aws_access_key_id=settings.llm_bedrock_access_key,
        aws_secret_access_key=settings.llm_bedrock_secret_key,
        aws_region=settings.llm_bedrock_region,
    ),
    disabled=providers.Singleton(_build_stub_llm_model),
)
```

| LLM_PROVIDER | Model Name Format | Dependency |
|-------------|------------------|------------|
| `openai` | `openai:gpt-4o` | `pydantic-ai` extra |
| `anthropic` | `anthropic:claude-sonnet-4-20250514` | `pydantic-ai-anthropic` extra |
| `bedrock` | `bedrock:us.anthropic.claude-sonnet-4-20250514-v1:0` | `pydantic-ai` extra + `aws` extra (aioboto3) |

- `LLMConfig`: frozen dataclass value object (domain layer) carrying provider+credentials
- `build_llm_model()`: factory function returning Provider-specific Model or plain string
- Domain services inject `llm_model` and construct `Agent(model=llm_model)` at init
- Bedrock credentials follow per-service injection convention

### S3 Vector Store DI Pattern

```python
class {Name}Container(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    {name}_vector_store = providers.Singleton(
        {Name}S3VectorStore,
        s3vector_client=core_container.s3vector_client,
        embedding_client=core_container.embedding_client,
        bucket_name=settings.s3vectors_bucket_name,
    )

    {name}_service = providers.Factory(
        {Name}Service,
        {name}_vector_store={name}_vector_store,
    )
```

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

- trailing-whitespace, end-of-file-fixer, check-yaml/json/toml
- check-added-large-files (1MB), check-merge-conflict, debug-statements, mixed-line-ending (LF)
- gitleaks v8.30.1 -- block credentials from reaching git at commit time (#87)
- ruff check --fix (Unified rules for E, W, F, UP, I, B, C4, SIM, S -- replaces pyupgrade, autoflake, isort, flake8, bandit)
- ruff format (Black-compatible formatting)

### Pre-commit (Manual Stage)

- mypy (--ignore-missing-imports, --check-untyped-defs)

### Commit Message

- conventional-pre-commit (feat, fix, refactor, docs, chore, test, ci, perf, style, i18n)

### Architecture Violation Check (Auto-run)

- no-domain-infra-import: No Infrastructure imports from Domain layer
- no-entity-pattern: No Entity pattern -- unified to DTO (background: ADR 004)

### Claude Hook

- SessionStart (check-required-plugins): verifies the pyright-lsp plugin is installed and the `CONTEXT7_API_KEY` env var is set.
- PreToolUse (pre-tool-security): SQL injection, hardcoded secrets, Domain→Infra import, sensitive data logging check.
- PostToolUse (post-tool-format): auto-formats `.py` files after Edit/Write (ruff format + ruff check).
- Stop (stop-sync-reminder): classifies the changed files (via `git diff`) into Foundation / Structure buckets and recommends running `/sync-guidelines`.

## §8. Active Features

| Feature | Status | Notes |
|------|------|------|
| Taskiq async tasks | Active | Broker abstraction (SQS/RabbitMQ/InMemory), @broker.task decorator |
| SQLAlchemy 2.0+ | Active | Mapped[T] + mapped_column() |
| Pydantic 2.x | Active | model_validate, model_dump, ConfigDict |
| dependency-injector | Active | DeclarativeContainer, @inject + Provide |
| Object Storage (aioboto3) | Active | S3/MinIO switchable via STORAGE_TYPE, ObjectStorage + ObjectStorageClient (via `aws` extra) |
| AWS DynamoDB (aioboto3) | Active | BaseDynamoRepository + DynamoDBClient (optional infra, via `aws` extra) |
| NiceGUI (BaseAdminPage) | Active | Admin dashboard (AG Grid, auto-discovery, Template Method rendering) -- gated via `admin` extra (#104) and DB-backed admin auth (#154) |
| alembic (migrations) | Active | DB migrations |
| Password hashing (bcrypt) | Active | hash_password(), verify_password() in src._core.common.security |
| AWS S3 Vectors (aioboto3) | Active | BaseS3VectorStore + S3VectorClient (optional infra, via `aws` extra) |
| Embedding (PydanticAI) | Active | PydanticAIEmbeddingAdapter, BaseEmbeddingProtocol, auto-dimension, multi-provider |
| LLM (PydanticAI Agent) | Active | build_llm_model(), LLMConfig, Agent structured output |
| OpenTelemetry tracing | Active | Optional `[otel]` extra, `OTEL_ENABLED` + `OTEL_EXPORTER_OTLP_ENDPOINT`, server/worker `_maybe_configure_otel()`, PydanticAI Agent instrumentation |
| Langfuse observability recipe | Active | Opt-in local OTLP/HTTP trace ingestion stack via `docker-compose.langfuse.yml`; `make observability-langfuse` generates ignored `_env/langfuse.env` with random local secrets |
| Text chunking (semantic-text-splitter) | Active | chunk_text(), chunk_text_by_tokens() in src._core.common.text_utils |
| Structured Logging (structlog) | Active | structlog + asgi-correlation-id, RequestLogMiddleware (server), StructlogContextMiddleware (worker), LOG_LEVEL / LOG_JSON_FORMAT env vars, sqlalchemy.engine double-emit fix (#9) |
| JWT/Authentication | Active | `src/auth/` provides HS256 access/refresh tokens, refresh-token rotation/revocation persistence, `/v1/auth/*`, and Bearer protection for `user` API routes (#4) |
| File Upload (UploadFile) | Not implemented | |
| RBAC/Permissions | Active | Admin identity is a separate realm (`admin_identity`, #218/ADR 049 — see §17). Membership in `admin_identity` *is* admin status; the record's `permissions` (JSON) list controls which admin pages each admin can access. `/admin/accounts` UI manages accounts and per-page permission grants. Bootstrap one-time setup wizard creates the first real admin with all permissions. Server-route RBAC for `/v1/user` (reads + CUD) added in #199 via the `require_admin` interface dependency, re-pointed to the admin token realm in #218 (verifies admin-realm tokens against `admin_identity`, rejects bootstrap admins); non-user `/v1/*` route-level gating is not yet implemented. |
| Rate Limiting (slowapi) | Not implemented | |
| WebSocket | Not implemented | |

> Extras note (#104, ADR 042): `nicegui` belongs to the `admin` extra; `boto3` / `aioboto3` / `types-aiobotocore-*` belong to the `aws` extra. Deployments install only what they need — `uv sync --extra admin --extra aws`; `make setup` installs both by default. When an extra is missing, the corresponding Selector branch returns `None` / `StubEmbedder` / `TestModel` for graceful degradation.

## §9. Router Pattern

```python
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from src._core.application.dtos.base_response import SuccessResponse

router = APIRouter()

@router.post(
    "/{name}",
    summary="...",
    response_model=SuccessResponse[{Name}Response],
    response_model_exclude={"pagination"},
)
@inject
async def create_{name}(
    item: Create{Name}Request,
    {name}_service: {Name}Service = Depends(Provide[{Name}Container.{name}_service]),
) -> SuccessResponse[{Name}Response]:
    data = await {name}_service.create_data(entity=item)
    return SuccessResponse(data={Name}Response(**data.model_dump(exclude={...})))
```

## §10. Exception Pattern

```python
from src._core.exceptions.base_exception import BaseCustomException

class {Name}NotFoundException(BaseCustomException):
    def __init__(self, {name}_id: int) -> None:
        super().__init__(
            status_code=404,
            message=f"{Name} with ID [ { {name}_id } ] not found",
            error_code="{NAME}_NOT_FOUND",
        )

class {Name}AlreadyExistsException(BaseCustomException):
    def __init__(self, {field}: str) -> None:
        super().__init__(
            status_code=409,
            message=f"{Name} with {field} [ { {field} } ] already exists",
            error_code="{NAME}_ALREADY_EXISTS",
        )
```

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

```python
from src._core.infrastructure.admin.base_admin_page import (
    BaseAdminPage,
    ColumnConfig,
)

{name}_admin_page = BaseAdminPage(
    domain_name="{name}",
    display_name="{Name}",
    icon="person",                    # Material icon name
    columns=[
        ColumnConfig(field_name="id", header_name="ID", width=80),
        ColumnConfig(field_name="username", header_name="Username", searchable=True),
        ColumnConfig(field_name="password", header_name="Password", masked=True),
        ColumnConfig(field_name="created_at", header_name="Created At"),
    ],
    searchable_fields=["username", "email"],
    sortable_fields=["id", "username", "created_at"],
    default_sort_field="id",
    # extra_services_config: declare additional DI-wired services by alias → container attr name.
    # Bootstrap resolves each by attr name from the domain container.
    # Use _get_extra_service(alias) in page handlers to access them.
    # extra_services_config={"query": "docs_query_service"},  # example (docs domain)
)
```

- `ColumnConfig` options: `field_name`, `header_name`, `sortable`, `searchable`, `hidden`, `masked`, `width`
- Sensitive fields (password, secret, token): always set `masked=True`
- `extra_services_config`: optional, for domains that need more than one service (e.g. separate query service). Declare `{alias: container_attr_name}` pairs; bootstrap wires them automatically. Call `page._get_extra_service("alias")` in page handlers.
- Config only — no route logic, no `ui` import

### Page File Pattern (`pages/{name}_page.py`)

```python
from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import admin_error_boundary
from src._core.infrastructure.admin.layout import admin_layout
from src.{name}.interface.admin.configs.{name}_admin_config import {name}_admin_page

# Injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/{name}")
@admin_error_boundary(context="{name}_list")
async def {name}_list_page(page: int = 1, search: str = ""):
    session = await require_auth(page_key="{name}")
    if session is None:
        return
    admin_layout(page_configs, current_domain="{name}", session=session)
    await {name}_admin_page.render_list(page=page, search=search)


@ui.page("/admin/{name}/{record_id}")
@admin_error_boundary(context="{name}_detail")
async def {name}_detail_page(record_id: int):
    session = await require_auth(page_key="{name}")
    if session is None:
        return
    admin_layout(page_configs, current_domain="{name}", session=session)
    await {name}_admin_page.render_detail(record_id=record_id)
```

> `@ui.page` stays outermost; `@admin_error_boundary` (inner) catches unhandled
> page-load errors. Event callbacks (button clicks) are separate invocations —
> call `AdminErrorHandler.handle(exc, context=...)` inside them. See §11 IC-195-1.

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

The NiceGUI admin layer integrates with the admin-identity credential check (PR #155 / ADR 047 IC promotion; page-level permissions added #194; **admin identity separated into its own domain + token realm by ADR 049 / #218**). The following invariants are durable and apply to all future admin work:

> **ADR 049 update (#218)**: admin identity now lives in the dedicated `admin_identity` bounded context, **not** the `user` table. Where IC-155-* below say `User.role`/`User.permissions`, read them as "the `admin_identity` record / its `permissions`". The NiceGUI session contract (IC-155-1) is unchanged — the `role` key is now a constant session marker (`ADMIN_SESSION_ROLE`) since membership in `admin_identity` *is* the admin role. See §17 for the realm invariants.

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

- **Persistence**: `src/_core/infrastructure/admin/audit/` (`AdminAuditLog` model + `0007` migration). Append-only. Phase 1 shipped `insert`; Phase 2 (#206) added `list_filtered` (summary projection + total count), `get_by_id` (full row with JSON state), and `delete_older_than` (retention cleanup). The list query uses an explicit `_SUMMARY_COLUMNS` projection so `before_state` / `after_state` JSON never travels in the list payload — the detail dialog fetches it on-demand. Tz-aware datetimes passed by callers (UI filters, scheduler, REPL) are normalized to naive UTC inside the repository (`_to_naive_utc`) before binding against the tz-naive `created_at` column on Postgres/asyncpg.
- **Facade**: `AuditLogger` (`audit/logger.py`) is the only entry callers use — `await get_audit_logger().log(action=..., domain=..., result=..., ...)`. Actor (`admin_user_id` / `admin_username`) and `correlation_id` auto-fill from the NiceGUI session and `asgi-correlation-id`; explicit kwargs override (used by the LOGIN failure path that has no session yet). **Audit-write never raises** — repository failures are swallowed via a structlog warning so a broken audit log cannot break the user action.
- **`@audit_action` decorator (Phase 2)**: `audit/logger.py` exposes `audit_action(action, domain, before_fn=..., after_fn=...)` to wrap admin write callables. The decorator runs `before_fn` (optional snapshot hook), invokes the wrapped callable, logs `SUCCESS`/`FAILURE` (with `error_code` for handled exceptions), then re-raises the original exception so the page-level `@admin_error_boundary` still notifies the operator. `before_fn` / `after_fn` failures are swallowed via `_safe_capture` (state stays `None`) so capture-hook bugs cannot break the wrapped action.
- **Model registration**: `src/_apps/server/bootstrap.py` and `migrations/env_utils.load_models()` both import `src._core.infrastructure.admin.audit.models` so the table is in `Base.metadata` for quickstart's `create_all()` and Alembic autogenerate. The package `__init__` deliberately **does not** re-export `audit.logger` (which imports `nicegui`) so the minimal-install boot path stays clean — admin-only callers import logger symbols from `audit.logger` directly.
- **Schema layout**: `action` is the verb (`LOGIN`, `ACCOUNT_DELETE`, `VIEW_LIST`, `VIEW_DETAIL`, …), `result` is `SUCCESS`/`FAILURE` — orthogonal, no `LOGIN_SUCCESS` compound. `record_id` is a varchar (UUID/string-id ready). `admin_username` is denormalized so log entries survive account deletion (FK is `ON DELETE SET NULL`). Composite indexes pair the common filter columns with `created_at DESC`.
- **Snapshot safety**: `before_state` / `after_state` are produced by the `safe_user_snapshot` whitelist serializer (`audit/safe_state.py`). Password hashes, refresh-token hashes, temporary passwords, raw exception messages, and any newly-added `UserDTO` field default to **not** being audited until explicitly allow-listed. `failure_reason` carries the domain `error_code` only — never `str(exc)`.
- **Instrumentation sites (Phase 1)**: `AdminAuthProvider.authenticate` self-logs `LOGIN` SUCCESS/FAILURE; `layout._handle_logout` records `LOGOUT` before clearing the session (the static `AdminAuthProvider.logout()` is called from many cleanup paths and must not emit a user-logout event); the four account-management callbacks (`accounts.create_account` / `save_perms` / `confirm_remove`, `setup.create_first_admin`, `change_password.do_change`) log SUCCESS and handled-failure with `error_code` as `failure_reason`.
- **Operator UI (Phase 2)**: `/admin/audit-log` (gated by the `audit_log` permission key, which is fixed in `AdminPermissionRegistry._FIXED_KEYS` alongside `accounts` and granted to the first real admin via the existing setup flow). Filter bar + AG Grid summary list + row-click detail dialog rendering `before_state` / `after_state` as plain text (`ui.code`) to prevent HTML injection. The page itself does **not** call `AuditLogger.log` (avoids self-loops). `BaseAdminPage.log_reads: bool = False` is the opt-in switch for per-domain `VIEW_LIST` / `VIEW_DETAIL` events; default off, on means the page's `render_list` / `render_detail` emit a single audit event per request.
- **Retention (Phase 2)**: `audit_log_retention_days` setting (`Field(default=90, ge=1, le=3650)`) bounds the retention window so a bogus env can't silently delete everything. `src/_apps/worker/tasks/audit_cleanup_task.py` is a regular `@broker.task` with a `schedule=[{"cron": "0 3 * * *"}]` label so it is triggerable in three ways: (1) the dedicated TaskiqScheduler process (`make scheduler`, reads labels via `LabelScheduleSource`), (2) external cron / k8s `CronJob` enqueuing the task by name, or (3) a one-off REPL invocation. The same `@broker.task` decoration covers all three. `_naive_utc_now()` produces a tz-naive cutoff for the Postgres column. `src/_apps/worker/scheduler.py` is the scheduler entrypoint and imports `worker.app` so `bootstrap_app` runs (middlewares + domain wiring) on the scheduler process too; `bootstrap.py` calls `container.wire(modules=[_audit_cleanup])` at module level so Provide markers resolve in both the worker and scheduler processes (codex round-2 must-fix).

## §12. S3 Vector Store Pattern

### VectorModel (Data Model)

`DynamoModel` counterpart — subclasses define index schema via `__vector_meta__` and declare metadata as Pydantic fields.

```python
from typing import ClassVar
from src._core.infrastructure.vectors.vector_model import (
    VectorModel, VectorModelMeta, VectorData,
)

class {Name}VectorModel(VectorModel):
    __vector_meta__: ClassVar[VectorModelMeta] = VectorModelMeta(
        index_name="{name}-search",
        # dimension defaults to settings.embedding_dimension (auto-derived)
        distance_metric="cosine",
        filter_fields=["category", "author_id"],
        non_filter_fields=["content_preview"],
    )

    category: str
    author_id: str
    content_preview: str
```

- `key`: auto-generated UUID v4 hex (via `generate_vector_id`)
- `data`: `VectorData(float32=[...])` — embedding vector
- Remaining fields → metadata (filter/non-filter)
- `to_s3vector()` serializes to S3 Vectors API format; `from_s3vector()` deserializes

### VectorModelMeta Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `index_name` | `str` | required | S3 Vectors index name |
| `data_type` | `Literal["float32"]` | `"float32"` | Vector data type |
| `dimension` | `int` | `settings.embedding_dimension` | Vector dimension (auto-derived) |
| `distance_metric` | `Literal["cosine", "euclidean"]` | `"cosine"` | Distance metric |
| `filter_fields` | `list[str]` | `[]` | Filterable metadata fields |
| `non_filter_fields` | `list[str]` | `[]` | Non-filterable metadata fields |

### BaseS3VectorStore (Repository Counterpart)

Implements `BaseVectorStoreProtocol`. Subclass must implement `_to_model()` for domain-specific conversion.

```python
from src._core.infrastructure.vectors.s3.base_store import BaseS3VectorStore

class {Name}S3VectorStore(BaseS3VectorStore[{Name}DTO]):
    def __init__(self, s3vector_client, *, bucket_name):
        super().__init__(
            s3vector_client=s3vector_client,
            model={Name}VectorModel,
            return_entity={Name}DTO,
            bucket_name=bucket_name,
        )

    def _to_model(self, entity: BaseModel) -> {Name}VectorModel:
        return {Name}VectorModel(
            data=VectorData(float32=entity.embedding),
            category=entity.category,
            # ... map DTO fields to model metadata
        )
```

### BaseVectorStoreProtocol Methods

| Method | Signature |
|--------|---------|
| upsert | `async (entities: Sequence[BaseModel]) -> int` |
| search | `async (query: VectorQuery) -> VectorSearchResult[ReturnDTO]` |
| get | `async (keys: list[str]) -> list[ReturnDTO]` |
| delete | `async (keys: list[str]) -> bool` |

### S3 Vector Domain Variant (Directory Structure)

```
src/{name}/
├── infrastructure/
│   ├── s3vectors/
│   │   └── models/{name}_model.py    # extends VectorModel
│   ├── repositories/{name}_vector_store.py  # extends BaseS3VectorStore
│   └── di/{name}_container.py        # s3vector_client + embedding_client injection
└── (everything else identical)
```

## §13. Embedding Pattern

### BaseEmbeddingProtocol

Backend-agnostic protocol for embedding implementations.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class BaseEmbeddingProtocol(Protocol):
    @property
    def dimension(self) -> int: ...
    async def embed_text(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

### PydanticAI Embedding Adapter

Single adapter class replaces per-provider clients. PydanticAI handles provider abstraction;
the adapter bridges to `BaseEmbeddingProtocol` and adds OpenAI batch splitting.
(Background: ADR 039 — PydanticAI Embedder transition)

| Provider | Batching | Credentials |
|----------|----------|------------|
| OpenAI | Auto (2048 items / 300K tokens via tiktoken) | `api_key` → `OpenAIProvider` |
| Bedrock | PydanticAI semaphore (default 5 concurrent) | `aws_*` → `BedrockProvider` |
| Google / Ollama | Native batch or local | Auto-detect env vars |

- Requires `pydantic-ai` extra: `uv sync --extra pydantic-ai` (installs `pydantic-ai-slim` + `tiktoken`)
- Provider-specific extras: `pydantic-ai-anthropic` (Anthropic LLM), `pydantic-ai-google` (Google embedding)
- Bedrock providers rely on `aioboto3`, which now ships in the `aws` extra (`uv sync --extra aws`) — install both `pydantic-ai` and `aws` extras for Bedrock embedding/LLM (#104 Part 2)
- OpenAI batch splitting requires `tiktoken` (included in pydantic-ai extra)
- Raises domain exceptions: `EmbeddingRateLimitException`, `EmbeddingAuthenticationException`, `EmbeddingInputTooLongException`, `EmbeddingModelNotFoundException`
- `EmbeddingConfig`: frozen dataclass (domain-layer VO) carrying model_name + dimension + credentials

### Text Chunking Utilities

| Function | Strategy | Use Case |
|----------|----------|----------|
| `chunk_text(text, chunk_size, overlap)` | Character-based (Unicode boundary aware) | General-purpose splitting |
| `chunk_text_by_tokens(text, model, max_tokens, overlap)` | Token-based (tiktoken-rs) | Embedding preprocessing |

- `semantic-text-splitter` handles Unicode word/sentence boundaries internally
- Token-based chunking uses tiktoken-rs (built into semantic-text-splitter) — no separate tiktoken install needed

## §14. LLM Pattern

### Model Factory

`build_llm_model(llm_config)` returns a PydanticAI Model object (or plain model string)
suitable for `Agent(model=...)`. Domain services must **not** import PydanticAI directly.
Instead, follow the ADR 040/043 pattern: domain Protocol + infra Adapter.
(Background: ADR 037 — PydanticAI Agent integration; ADR 043 — responsibility refactor)

```python
# 1. Domain layer: protocol only — no SDK imports
class ClassifierProtocol(Protocol):
    async def classify(self, text: str, categories: list[str] | None = None) -> ClassificationDTO: ...

class ClassificationService:
    def __init__(self, classifier: ClassifierProtocol) -> None:
        self._classifier = classifier

    async def classify(self, text: str, categories: list[str] | None = None) -> ClassificationDTO:
        return await self._classifier.classify(text=text, categories=categories)

# 2. Infrastructure adapter: PydanticAI Agent lives here
class PydanticAIClassifier:
    def __init__(self, llm_model: Any) -> None:
        # `instructions=` (modern PydanticAI slot) is preferred over the legacy
        # `system_prompt=` since #197 Phase 1+2 — instructions are separated from
        # the user prompt parts and, on the OpenAI Responses provider, are sent as
        # a dedicated top-level `instructions` field. This is NOT a secrecy
        # boundary (PydanticAI still stores the rendered instructions on the
        # ModelRequest); the value is separation-from-user-input, not concealment.
        # The persona prose is typed as `Final[LiteralString]` so pyright blocks
        # any future f-string interpolation of untrusted runtime data into the
        # agent's behavioural contract.
        self._agent: Agent[None, ClassificationDTO] = Agent(
            model=llm_model,
            output_type=ClassificationDTO,
            instructions=_INSTRUCTIONS,
        )

    async def classify(self, text: str, categories: list[str] | None = None) -> ClassificationDTO:
        # All dynamic prompt fields (user text, category labels, retrieved chunk
        # title/content, user question) go through ``escape_for_prompt_xml`` in
        # ``src/_core/infrastructure/llm/prompt_boundaries.py`` and are wrapped
        # in named XML boundary tags (`<user_text>`, `<category>`, `<documents>`
        # / `<document>` / `<title>` / `<content>`). The `instructions=` text
        # tells the model to treat the wrapped content as untrusted DATA and
        # NEVER follow embedded directives — see #197 Phase 1+2.
        result = await self._agent.run(_format_prompt(text, categories))
        return result.output

# 3. DI container: Selector wires real vs stub
classifier = providers.Selector(
    _classifier_selector,  # "real" if LLM_MODEL_NAME else "stub"
    real=providers.Singleton(PydanticAIClassifier, llm_model=core_container.llm_model),
    stub=providers.Singleton(StubClassifier),
)
classification_service = providers.Factory(ClassificationService, classifier=classifier)
```

| Provider | Model Class | Credentials |
|----------|------------|------------|
| OpenAI | `OpenAIChatModel` | `api_key` → `OpenAIProvider` |
| Anthropic | `AnthropicModel` | `api_key` → `AnthropicProvider` |
| Bedrock | `BedrockConverseModel` | `aws_*` → `BedrockProvider` |

- `LLMConfig`: frozen dataclass (domain-layer VO) carrying model_name + credentials
- PydanticAI Agent is reusable across requests (create once at adapter init)
- Structured output via `Agent[DepsType, OutputType]` — type-checked at build time
- Domain service injects `ClassifierProtocol` (or equivalent), not `llm_model` directly
- ADR 043: Domain → Protocol → Infra Adapter → Selector is the canonical AI feature pattern

### Prompt-injection guardrails (#197)

Two layers, both living at the **adapter** boundary (not the PydanticAI Hooks/capabilities API — the adapters own the call sites, so plain functions are simpler, fully testable, and version-decoupled):

- **Structural (Phase 1+2, PR #208)**: `instructions=` over `system_prompt=`; every dynamic prompt field escaped via `escape_for_prompt_xml` and wrapped in named XML boundary tags; instruction constants typed `Final[LiteralString]`. See §14 code comments + `src/_core/infrastructure/llm/prompt_boundaries.py`.
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
