# Reference

Deep details that used to live in the README. Start with the
[60-second quickstart](quickstart.md) or the
[README](../README.md) for the high-level pitch; come here when you need
environment specifics, the full tech stack, or a manual walkthrough.

## Contents

- [Local development with PostgreSQL](#local-development-with-postgresql)
- [Manual setup (without Make)](#manual-setup-without-make)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Manual domain scaffolding](#manual-domain-scaffolding)
- [Roadmap](#roadmap)
- [Selected ADRs](#selected-adrs)

---

## Local development with PostgreSQL

The quickstart path uses SQLite + in-memory broker. For real development
(migrations, PostgreSQL, Docker Compose):

```bash
# 1. Clone
git clone https://github.com/Mr-DooSun/fastapi-agent-blueprint.git
cd fastapi-agent-blueprint

# 2. Setup (requires uv)
make setup

# 3. Environment variables
cp _env/local.env.example _env/local.env

# 4. PostgreSQL + migrations + server
make dev
```

Open <http://localhost:8001/docs> to explore the API. The selector recommends
Stoplight Elements / Scalar and exposes a `Download OpenAPI (JSON)` button
plus a link to the [frontend handoff guide](frontend-handoff.md).

For the first Alembic rollout in an environment that already has tables
created outside Alembic, see the
[RDB migration runbook](operations/rdb-migrations.md).

## Manual setup (without Make)

```bash
# 1. Create venv + install deps
uv venv --python 3.12
source .venv/bin/activate
uv sync --group dev --extra admin --extra aws   # drop extras you don't need

# 2. Environment variables
cp _env/local.env.example _env/local.env

# 3. Start PostgreSQL (Docker)
docker compose -f docker-compose.local.yml up -d postgres

# 4. Migrations + server
alembic upgrade head
python run_server_local.py --env local
```

### Optional dependency extras

| Extra | What it installs | Enables |
|---|---|---|
| `admin` | `nicegui` | The NiceGUI admin dashboard at `/admin`. Drop for API-only deployments; the server still boots, `/api/*` still serves, just no dashboard |
| `aws` | `boto3`, `aioboto3`, `types-aiobotocore-*` | Object storage (S3/MinIO), DynamoDB, S3 Vectors. Drop for non-AWS deployments — the 4 AWS-backed client modules still import, CoreContainer Selectors resolve to `None` when the matching `*_TYPE` / `*_ACCESS_KEY` env vars are unset |
| `sqs` | `taskiq-aws` | `BROKER_TYPE=sqs` broker backend |
| `rabbitmq` | `taskiq-aio-pika` | `BROKER_TYPE=rabbitmq` broker backend |
| `pydantic-ai` | `pydantic-ai-slim` + `tiktoken` | `EMBEDDING_PROVIDER` / `LLM_PROVIDER` and any agent-based domain |
| `pydantic-ai-anthropic` | Anthropic provider for PydanticAI | `LLM_PROVIDER=anthropic` |
| `pydantic-ai-google` | Google provider for PydanticAI | `EMBEDDING_PROVIDER=google` / `LLM_PROVIDER=google` |
| `pydantic-ai-duckduckgo` | DuckDuckGo search tool for PydanticAI (`ddgs`) | `examples/web_search_chatbot/` real search tool |

Pass `--extra <name>` to `uv sync` for each capability you need. `make setup` pulls `--extra admin --extra aws` by default for full dev coverage; `make quickstart` only needs `--extra admin` (it runs on SQLite + InMemory broker). Every other extra opts in explicitly.

The NiceGUI admin dashboard authenticates through the DB-backed `auth` domain.
Use `ADMIN_BOOTSTRAP_*` settings to create or promote the initial admin user;
`ADMIN_ID` / `ADMIN_PASSWORD` are no longer the login authority.

---

## Tech stack

FastAPI + SQLAlchemy 2.0 + Pydantic 2.x + dependency-injector + Taskiq +
asyncpg, plus optional `NiceGUI` (`[admin]` extra) and `aioboto3`
(`[aws]` extra) when you need the admin dashboard or the AWS-backed
infrastructure clients.

### AI & Agent

| Technology | Purpose | Status |
|---|---|---|
| **AWS S3 Vectors** | Managed vector index backend for semantic search | Available |
| **OpenAI / Bedrock embeddings** | Pluggable embedding backends via config | Available |
| **PydanticAI** | Structured LLM orchestration (Agent + typed outputs) | Available (classification domain) |
| **FastMCP** | MCP server — expose domain services as AI-agent tools | Planned ([#18](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/18)) |

### Core

| Technology | Purpose |
|---|---|
| **FastAPI** | Async web framework |
| **Pydantic** 2.x | Data validation & settings |
| **SQLAlchemy** 2.0 | Async ORM |
| **dependency-injector** | IoC container ([why?](history/archive/013-why-ioc-container.md)) |

### Infrastructure

| Technology | Purpose |
|---|---|
| **PostgreSQL** + asyncpg | Primary RDBMS |
| **Taskiq** + SQS / RabbitMQ / InMemory | Async task queue ([why not Celery?](history/archive/001-celery-to-taskiq.md)) |
| **aiohttp** | Async HTTP client |
| **aioboto3** (`[aws]` extra) | DynamoDB, S3/MinIO, S3 Vectors clients |
| **semantic-text-splitter** | Character/token chunking for embedding preprocessing |
| **Alembic** | DB migrations |

### DevOps

| Technology | Purpose |
|---|---|
| **Ruff** | Linting + formatting ([replaces 6 tools](history/archive/012-ruff-migration.md)) |
| **pre-commit** | Git hook automation + architecture enforcement |
| **UV** | Python package management ([why not Poetry?](history/archive/005-poetry-to-uv.md)) |
| **NiceGUI** | Admin dashboard UI |

---

## Project structure

```
fastapi-agent-blueprint/
├── src/
│   ├── _apps/                       # App entry points
│   │   ├── server/                  # FastAPI HTTP server
│   │   ├── worker/                  # Taskiq async worker
│   │   └── admin/                   # NiceGUI admin app (mounted on server)
│   │
│   ├── _core/                       # Shared infrastructure
│   │   ├── common/                  # Pagination, security, text utils, UUID helpers
│   │   ├── domain/
│   │   │   ├── protocols/           # BaseRepositoryProtocol[ReturnDTO]
│   │   │   └── services/            # BaseService[CreateDTO, UpdateDTO, ReturnDTO]
│   │   ├── infrastructure/
│   │   │   ├── persistence/
│   │   │   │   ├── rdb/             # Database, BaseRepository[ReturnDTO]
│   │   │   │   └── nosql/dynamodb/  # DynamoDBClient, BaseDynamoRepository
│   │   │   ├── vectors/
│   │   │   │   ├── s3/              # S3VectorClient, BaseS3VectorStore
│   │   │   │   └── in_memory/       # In-memory vector store (quickstart)
│   │   │   ├── embedding/           # PydanticAI embedding adapter
│   │   │   ├── llm/                 # build_llm_model factory
│   │   │   ├── storage/             # S3 / MinIO ObjectStorageClient
│   │   │   ├── taskiq/              # Broker adapters, TaskiqManager
│   │   │   ├── http/                # HttpClient, BaseHttpGateway
│   │   │   ├── observability/       # OTEL setup (ADR 046)
│   │   │   ├── rag/                 # RagPipeline, StubAnswerAgent (ADR 040)
│   │   │   ├── di/                  # CoreContainer
│   │   │   └── discovery.py         # Auto domain discovery
│   │   ├── application/dtos/        # BaseRequest, BaseResponse, SuccessResponse
│   │   ├── exceptions/              # Handlers, BaseCustomException
│   │   └── config.py                # Settings (pydantic-settings)
│   │
│   └── user/                        # Reference domain
│       ├── domain/
│       │   ├── dtos/                # UserDTO
│       │   ├── protocols/           # UserRepositoryProtocol
│       │   ├── services/            # UserService(BaseService[...])
│       │   └── exceptions/          # UserNotFoundException
│       ├── infrastructure/
│       │   ├── database/models/     # UserModel
│       │   ├── repositories/        # UserRepository(BaseRepository[UserDTO])
│       │   └── di/                  # UserContainer
│       └── interface/
│           ├── server/              # routers/, schemas/, bootstrap/
│           ├── worker/              # payloads/, tasks/, bootstrap/
│           └── admin/               # configs/, pages/ (NiceGUI)
│
├── migrations/                      # Alembic
└── _env/                            # Environment variable files (gitignored)
```

---

## Manual domain scaffolding

> Looking for a guided walk-through that ends with a passing test and a
> `curl`? Use the [**"Your first domain in 10 minutes" tutorial**](tutorial/first-domain.md)
> instead — this section is a compact reference card of the same three
> layers, without the step-by-step verification.
>
> Prefer the automated path? `/new-domain product` (Claude Code) or
> `$new-domain product` (Codex CLI) scaffolds the entire domain —
> 15 content files + 25 `__init__.py` + 4 tests — in one command.

Below is the same flow by hand, using a `Product` domain as an example.

### 1. Domain layer

```python
# src/product/domain/dtos/product_dto.py
class ProductDTO(BaseModel):
    id: int = Field(..., description="Product ID")
    name: str = Field(..., description="Product name")
    price: int = Field(..., description="Price")
    created_at: datetime
    updated_at: datetime

# src/product/domain/protocols/product_repository_protocol.py
class ProductRepositoryProtocol(BaseRepositoryProtocol[ProductDTO]):
    pass

# src/product/domain/services/product_service.py
class ProductService(
    BaseService[CreateProductRequest, UpdateProductRequest, ProductDTO]
):
    def __init__(self, product_repository: ProductRepositoryProtocol):
        super().__init__(repository=product_repository)
    # CRUD is provided. Just add custom business logic.
```

### 2. Infrastructure layer

```python
# src/product/infrastructure/database/models/product_model.py
class ProductModel(Base):
    __tablename__ = "product"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=func.now())

# src/product/infrastructure/repositories/product_repository.py
class ProductRepository(BaseRepository[ProductDTO]):
    def __init__(self, database: Database):
        super().__init__(database=database, model=ProductModel, return_entity=ProductDTO)

# src/product/infrastructure/di/product_container.py
class ProductContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()
    product_repository = providers.Singleton(ProductRepository, database=core_container.database)
    product_service = providers.Factory(ProductService, product_repository=product_repository)
```

### 3. Interface layer

```python
# src/product/interface/server/routers/product_router.py
@router.post("/product", response_model=SuccessResponse[ProductResponse])
@inject
async def create_product(
    item: CreateProductRequest,
    product_service: ProductService = Depends(Provide[ProductContainer.product_service]),
) -> SuccessResponse[ProductResponse]:
    data = await product_service.create_data(entity=item)
    return SuccessResponse(data=ProductResponse(**data.model_dump()))
```

### Auto registration

`discover_domains()` (see `src/_core/infrastructure/discovery.py`) detects
the new domain automatically — **no edits** to `_apps/` containers or
bootstrap files.

Discovery conditions:

- `src/{name}/__init__.py` exists
- `src/{name}/infrastructure/di/{name}_container.py` exists

---

## Roadmap

Short list; open issues are the source of truth. See the
[issue tracker](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues)
for the live view.

### Phase 1 — AI agent foundation

- [ ] FastMCP interface ([#18](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/18))
- [ ] Additional vector backend: pgvector ([#11](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/11))
- [x] JWT authentication ([#4](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/4))
- [x] PydanticAI Agent integration ([#15](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/15))

### Phase 2 — Production readiness

- [x] Structured logging — structlog ([#9](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/9))
- [ ] Error notifications ([#17](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/17))
- [ ] CRUD data validation ([#10](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/10))

### Phase 3 — Ecosystem

- [ ] Test coverage expansion ([#2](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/2))
- [x] Performance testing — Locust ([#3](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/3))
- [ ] Serverless deployment ([#6](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/6))
- [ ] WebSocket documentation ([#1](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/1))

### Completed (recent)

- Zero-config quickstart ([#78](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/78))
- Visual architecture diagrams + SVG exports ([#81](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/81), [#89](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/89))
- PydanticAI embedder transition (ADR 039)
- Storage abstraction — S3/MinIO ([#58](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/58))
- Embedding service — OpenAI/Bedrock ([#69](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/69))
- S3 Vectors support ([#11](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/11))
- DynamoDB support ([#13](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/13))
- Broker abstraction — SQS/RabbitMQ/InMemory ([#8](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/8))
- Admin dashboard — NiceGUI ([#14](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/14))

---

## Selected ADRs

Every technical choice in this project is captured as an ADR.
The 14 load-bearing decisions a contributor must understand live at
[`docs/history/README.md`](history/README.md); historical / superseded / tooling decisions
are preserved under [`docs/history/archive/`](history/archive/).

| # | Title |
|---|---|
| [003](history/003-response-request-pattern.md) | Response/Request pattern |
| [004](history/004-dto-entity-responsibility.md) | DTO/Entity responsibility redefined |
| [006](history/006-ddd-layered-architecture.md) | Domain-driven layered architecture |
| [007](history/007-di-container-and-app-separation.md) | DI container hierarchy and app separation |
| [011](history/011-3tier-hybrid-architecture.md) | 3-tier hybrid architecture |
| [017](history/017-exception-handling-strategy.md) | Exception handling strategy |
| [019](history/019-domain-auto-discovery.md) | Domain auto-discovery |
| [037](history/037-pydanticai-agent-integration.md) | PydanticAI Agent integration |
| [039](history/039-pydantic-ai-embedder-transition.md) | PydanticAI embedder transition |
| [040](history/040-rag-as-reusable-pattern.md) | RAG as a reusable `_core` pattern |
| [041](history/041-vector-backends-consolidation.md) | Multi-backend infrastructure layout |
