# 035. Embedding Service Abstraction with Selector Pattern

- Status: Accepted
- Date: 2026-04-14
- Related issue: #69
- Related ADRs: [029](029-broker-abstraction-selector.md)(Selector pattern), [034](034-s3vectors-vectorstore-pattern.md)(VectorStore pattern)

## Summary

To provide shared embedding infrastructure for AI/ML applications, we added a `BaseEmbeddingProtocol` with OpenAI and Bedrock Titan implementations, selected via `providers.Selector` -- following the Broker pattern established in ADR 029. Dimension is auto-derived from the model to prevent configuration drift with vector store indexes.

## Background

- **Trigger**: Issue #69 -- the project supports vector storage (S3 Vectors, #11) but has no infrastructure for generating embeddings. Domain services that need to store or search vectors must bring their own embedding logic.

- **Decision type**: Upfront design with iterative refinements -- the initial implementation used a configurable `EMBEDDING_DIMENSION` environment variable, but review revealed this was dangerous (changing dimension breaks existing vector indexes without warning). The design was corrected to auto-derive dimension from the model before merge.

### Prior Art in the Project

| Infrastructure | Selection Pattern | ADR |
|---------------|-------------------|-----|
| S3/MinIO | Parameter switching (endpoint_url) | [023](023-object-storage-unification.md) |
| PostgreSQL/MySQL/SQLite | Parameter switching (engine) | [027](027-flexible-rdb-configuration.md) |
| SQS/RabbitMQ/InMemory | `providers.Selector` (different classes) | [029](029-broker-abstraction-selector.md) |
| **OpenAI/Bedrock Embedding** | **`providers.Selector` (different classes)** | **035 (this)** |

## Problem

### 1. No shared embedding infrastructure

Each domain that needs embeddings must independently:
- Set up API clients (AsyncOpenAI, aioboto3 bedrock-runtime)
- Handle authentication, rate limiting, error mapping
- Manage batch splitting to respect API limits
- Track vector dimensions for index compatibility

This leads to duplicated client setup across domains and makes model switching (e.g., OpenAI to Bedrock) a cross-cutting change.

### 2. Different providers have fundamentally different APIs

| Aspect | OpenAI | Bedrock Titan |
|--------|--------|---------------|
| Client | AsyncOpenAI (`openai` package) | aioboto3 `bedrock-runtime` |
| Batch support | Native (up to 2,048 texts/request) | Single text per `invoke_model` |
| Token limit | 8,192/text, 300,000/request total | 8,192 tokens, 50,000 chars |
| Dimension | 1,536 (3-small), 3,072 (3-large) | 1,024 (Titan v2), 1,536 (v1) |
| Dependency | Optional (`openai` + `tiktoken`) | Core (`aioboto3`, already present) |

A factory function with mixed parameters (like the broker's rejected Alternative A in ADR 029) would grow unmanageably as providers are added.

### 3. Dimension must be consistent with vector store indexes

Embedding model dimension must match `VectorModelMeta.dimension`. If these drift apart (e.g., switching from OpenAI 1,536 to Bedrock 1,024 without updating the index), vector upserts silently fail or produce corrupted results. Making dimension a separate configuration increases this risk.

## Alternatives Considered

### A. LiteLLM unified gateway

Use LiteLLM's `aembedding()` function which provides a single API across 20+ embedding providers.

**Rejected**: (1) LiteLLM pulls in a large transitive dependency tree, violating the project's dependency minimalism. (2) It would be the only "meta-library" in the project -- every other infrastructure module (DynamoDB, S3, Broker) implements a direct client wrapper. (3) The Selector pattern cannot be demonstrated with a single implementation, reducing the blueprint's educational value. (4) LiteLLM hides provider-specific behavior (batching limits, token counting) that developers need to understand.

### B. LangChain Embeddings interface

Use `langchain-core`'s `Embeddings` ABC and implement providers against it.

**Rejected**: Issue #69 itself noted this adds a heavy dependency for a simple interface. The project's VectorStore already diverges from LangChain's pattern (ADR 034). Coupling embedding to LangChain would create an inconsistency where VectorStore is custom but Embedding is LangChain.

### C. Configurable EMBEDDING_DIMENSION environment variable (tried and corrected)

The initial implementation included `EMBEDDING_DIMENSION` as a user-settable env var, passed to both clients and the DI container.

**Corrected before merge**: Changing the dimension without re-embedding all existing vectors and recreating indexes causes silent data corruption. Dimension is a property of the model, not an independent configuration. The corrected design auto-derives dimension from the model name via internal lookup tables, and `VectorModelMeta.dimension` defaults to `settings.embedding_dimension` (a computed property).

### D. Direct implementations with Selector pattern (chosen)

Implement each provider as a standalone client class, selected via `providers.Selector` based on `EMBEDDING_PROVIDER` environment variable.

## Decision

### 1. BaseEmbeddingProtocol in domain layer

```
src/_core/domain/protocols/embedding_protocol.py
```

Three members: `dimension` (property), `embed_text(str)`, `embed_batch(list[str])`. No Generic TypeVar needed (input/output types are fixed). Domain services inject this protocol directly (like VectorStore, per ADR 034).

### 2. Provider-specific clients in infrastructure layer

```
src/_core/infrastructure/embedding/
    bedrock_embedding_client.py   # aioboto3, single invoke_model per text
    openai_embedding_client.py    # AsyncOpenAI, token-based batch splitting
    exceptions.py                 # EmbeddingException hierarchy
```

Each client follows the established async client pattern (ADR 009): session held as instance attribute, client created per operation via context manager, errors wrapped into domain exceptions.

### 3. providers.Selector for multi-backend selection

```python
embedding_client = providers.Selector(
    lambda: (settings.embedding_provider or "openai").lower().strip(),
    openai=providers.Singleton(OpenAIEmbeddingClient, ...),
    bedrock=providers.Singleton(BedrockEmbeddingClient, ...),
)
```

Default provider is OpenAI (most accessible). Adding a new provider means adding one Singleton -- no existing providers modified.

### 4. Dimension auto-derived from model

Each client has an internal `_MODEL_DIMENSIONS` lookup table. The Settings class exposes a computed `embedding_dimension` property (read-only) that resolves provider + model to dimension. `VectorModelMeta.dimension` defaults to this property via `default_factory` with lazy import to avoid circular initialization.

| Model | Dimension |
|-------|-----------|
| text-embedding-3-small | 1,536 |
| text-embedding-3-large | 3,072 |
| text-embedding-ada-002 | 1,536 |
| amazon.titan-embed-text-v2:0 | 1,024 |
| amazon.titan-embed-text-v1 | 1,536 |

### 5. Token-based batching for OpenAI

OpenAI's binding constraint is 300,000 total tokens per request (not 2,048 items). The client uses `tiktoken` to count tokens before batching. Individual texts exceeding 8,192 tokens raise `EmbeddingInputTooLongException`. Bedrock validates at 50,000 characters per text.

### 6. OpenAI as optional dependency

```toml
[project.optional-dependencies]
openai = ["openai>=1.0.0", "tiktoken>=0.7.0"]
```

Follows the broker pattern (ADR 029): lazy import with clear `ImportError` message. Bedrock requires no extra dependency (aioboto3 is already core).

## Rationale

### Infrastructure Selection Framework (extended)

| Condition | Pattern | Example |
|-----------|---------|---------|
| Same class, different params | Parameter switching | S3/MinIO, PostgreSQL/MySQL |
| Different classes, different signatures | `providers.Selector` | Broker (029), **Embedding (this)** |
| Different paradigm (not CRUD) | Dedicated pattern | VectorStore (034) |

### Why Auto-Derive Dimension?

Embedding model dimension and vector store index dimension must be identical. If these are configured independently:

```
EMBEDDING_DIMENSION=1536  →  new vectors are 1536-dim
VectorModelMeta(dimension=1024)  →  index expects 1024-dim
→  silent mismatch, search quality degrades or API errors
```

By deriving both from the same source (model name), the values are always consistent. Changing the embedding model is an intentional act that requires re-embedding -- making dimension independently configurable would mask this requirement.

### Trade-offs Accepted

- **Two optional dependency groups for embedding**: `[openai]` for OpenAI (includes tiktoken). Bedrock needs no extra. This adds complexity to the install instructions but follows the established optional dependency pattern.
- **No retry/backoff in v1**: The clients do not implement retry logic for transient errors. This is intentional for a blueprint -- retry strategies are domain-specific and can be added per-project. Bedrock SDK has built-in retry.
- **Bedrock processes texts sequentially**: `invoke_model` accepts only one text per call. This is a Bedrock API constraint, not a design choice. The `embed_batch` loop is straightforward but slower than OpenAI's native batching.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
