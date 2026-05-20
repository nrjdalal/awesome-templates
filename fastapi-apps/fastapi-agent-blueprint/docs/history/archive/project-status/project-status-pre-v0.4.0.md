# Project Status — Pre-v0.4.0 Historical Record

> Archived from `.claude/rules/project-status.md` (PR-B.1, 2026-05-06).
> These rows represent features shipped between v0.2.0 and v0.4.0 (released 2026-04-21).
> Live table: [.claude/rules/project-status.md](../../../.claude/rules/project-status.md).

## Major Changes (v0.2.0 → v0.4.0)

| Feature | Issue | Impact |
|---------|-------|--------|
| NiceGUI Admin Dashboard | #14 | New interface layer: admin/ (configs + pages) |
| Environment Config Validation | #53 | Settings model_validator, strict mode for stg/prod |
| Flexible RDB Config | #7 | DatabaseConfig.from_env(), multi-engine support |
| DynamoDB Support | #13 | BaseDynamoRepository, DynamoModel, DynamoDBClient |
| Broker Abstraction | #8 | providers.Selector for SQS/RabbitMQ/InMemory |
| BaseService 3-TypeVar | ADR 011 | Generic[CreateDTO, UpdateDTO, ReturnDTO] restoration |
| CRUD Write Validation | #10 | BaseService pre-write validation hooks, `_core/domain/validation.py` helpers, repository existence primitives, and User username/email uniqueness constraints |
| Password Hashing | - | hash_password/verify_password in _core.common.security |
| Serena Removal & Pyright Adoption | #63 | pyright-lsp as the default code-intelligence layer, PostToolUse formatting hook, transition to tool-agnostic skills |
| Codex CLI Harness & Hybrid C Skills | #66 | Shared AGENTS.md, docs/ai/shared/ reference layer, 14 Hybrid C skill migrations |
| S3 Vectors Support | #70 | BaseS3VectorStore, VectorModel, S3VectorClient, VectorQuery/VectorSearchResult |
| Embedding Service Abstraction | #69 | Selector pattern (OpenAI/Bedrock), BaseEmbeddingProtocol, auto-dimension |
| Text Chunking | #69 | semantic-text-splitter, chunk_text/chunk_text_by_tokens |
| ADR 035/036 | #69 | Embedding abstraction + text chunking design decisions |
| Storage Abstraction | #58 | STORAGE_TYPE env var, S3/MinIO parameter switching, Settings computed properties |
| PydanticAI Agent Integration | #15 | Agent structured output, classification prototype, LLMConfig + build_llm_model |
| PydanticAI Embedder Transition | ADR 039 | PydanticAIEmbeddingAdapter replaces per-provider clients, EmbeddingConfig VO |
| Bedrock Credential Support | #15 | LLMConfig with per-service AWS credential injection, model_factory |
| Zero-config Quickstart | #78 | `make quickstart` + `make demo`, ENV=quickstart with SQLite + InMemory broker + auto create_all, Settings defaults for zero-infra boot |
| RAG Pattern + docs Domain | #80 | `_core/domain/services/rag_pipeline.py` (Generic[TChunk] orchestrator), `_core/domain/dtos/rag.py` (BaseChunkDTO, CitationDTO, QueryAnswerDTO), `_core/domain/protocols/answer_agent_protocol.py`, `_core/infrastructure/rag/` (StubEmbedder, StubAnswerAgent, PydanticAIAnswerAgent), `_core/infrastructure/vectors/` (BaseInMemoryVectorStore), `src/docs/` consumer (document CRUD + query), `make demo-rag`, VECTOR_STORE_TYPE env var, [ADR 040](../040-rag-as-reusable-pattern.md) |
| ADR Consolidation | #83 | 40 ADRs → 14 core + 29 archived under `docs/history/archive/`, new `docs/history/README.md` core-reading-order guide |
| Optional Infrastructure (CoreContainer) — Part A | #101 | `providers.Selector` + lazy factories for all 5 non-broker optional infras (storage, DynamoDB, S3 Vectors, embedding, LLM). Disabled branches: `providers.Object(None)` for data stores, `StubEmbedder` for embedding. `llm_config` / `embedding_config` dropped from public container surface. [ADR 042](../042-optional-infrastructure-di-pattern.md), AGENTS.md "Optional Infrastructure" reference section |
| Optional Infrastructure — Part B | #101 | `build_stub_llm_model()` factory returns PydanticAI `TestModel` (or `None` if `pydantic-ai` extra not installed). `ClassificationService` now degrades gracefully when `LLM_*` unset. `docs/ai/shared/scaffolding-layers.md` gains "Optional AI Infra Variant" section teaching the domain-level Selector+stub pattern for new-domain scaffolding |
| Structured Logging | #9 | Integrates the `structlog` + `asgi-correlation-id` pipeline into server/worker bootstrap. `configure_logging()`, `RequestLogMiddleware` + `CorrelationIdMiddleware` (server), and `StructlogContextMiddleware` (worker) bind task/correlation id contextvars. `LOG_LEVEL` / `LOG_JSON_FORMAT` env vars (dev/local/quickstart → console, stg/prod → JSON). `DATABASE_ECHO` is mapped to `logging.getLogger("sqlalchemy.engine").setLevel(INFO)` to remove double-emit. `generic_exception_handler` now records `logger.exception("unhandled_exception", ...)` instead of `print(traceback)`. |
| Admin extra split | #104 | Moves `nicegui` into the `[admin]` extra. `_maybe_bootstrap_admin()` skips on `ImportError` while emitting only an `admin_mount_skipped` structured log line — the server still boots. `make setup` installs `--extra admin` by default. The CI `minimal-install` job guards against regressions where `/admin` would mount even without the extra. |
| AWS extra split | #104 Part 2 | Moves `boto3` / `aioboto3` / `types-aiobotocore-*` into the `[aws]` extra. The four AWS client modules (`ObjectStorageClient`, `ObjectStorage`, `DynamoDBClient`, `S3VectorClient`) lazy-import `aioboto3` / `boto3` from `__init__` / lazy singletons. CoreContainer's Selector returns `None` on the disabled branch, so the lazy import never fires when the `aws` extra is missing and the related env vars are unset. `make setup` installs `--extra aws` by default. |
