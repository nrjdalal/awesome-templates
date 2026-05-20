# 034. S3 Vectors Integration with VectorStore Pattern

- Status: Accepted
- Date: 2026-04-14
- Related issue: #11
- Related ADRs: [023](023-object-storage-unification.md)(S3 via aioboto3), [029](029-broker-abstraction-selector.md)(multi-backend Selector)

## Summary

To add vector database support for AI/ML applications, we integrated Amazon S3 Vectors as the first backend using the industry-standard VectorStore pattern -- deliberately diverging from the project's Repository pattern used for RDB and DynamoDB, because vector similarity search is a fundamentally different paradigm from CRUD persistence.

## Background

- **Trigger**: Issue #11 requested vector database support. The original proposal suggested pgvector (PostgreSQL extension), but an existing S3 Vectors wrapper in a production project offered a proven starting point with lower operational overhead (serverless, no infrastructure provisioning).

- **Decision type**: Upfront design with course corrections -- the initial implementation used Repository pattern for consistency with DynamoDB, but industry convention review revealed this was a forced fit. The design was corrected to VectorStore pattern before merge.

### Prior Art in the Project

The project already has two data storage patterns:

| Storage | Pattern | ADR |
|---------|---------|-----|
| RDB (PostgreSQL/MySQL/SQLite) | BaseRepository (CRUD) | -- |
| DynamoDB | BaseDynamoRepository (composite key + cursor pagination) | -- |
| **S3 Vectors (this)** | **BaseS3VectorStore (upsert + similarity search)** | **034** |

## Problem

### 1. Vector operations do not map to CRUD

The DDD Repository pattern manages domain aggregate lifecycles through Create, Read, Update, Delete. Vector database operations are fundamentally different:

| Repository (CRUD) | VectorStore |
|---|---|
| Create one entity by ID | Upsert batch of embeddings |
| Read by exact ID/condition | **Similarity search** (approximate nearest neighbor) |
| Update fields by ID | No meaningful update -- replace entire vector |
| Delete by ID | Delete by key |

The core operation -- similarity search -- has no Repository equivalent. It returns ranked results with distance scores, not exact matches. Forcing this into a Repository interface creates a leaky abstraction where the most important operation (search) doesn't fit the pattern.

### 2. No framework uses "Repository" for vector operations

Every major framework uses "VectorStore" or equivalent:

| Framework | Term | Class |
|-----------|------|-------|
| LangChain | VectorStore | `VectorStore` (ABC) |
| LlamaIndex | VectorStore | `BasePydanticVectorStore` |
| Spring AI | VectorStore | `VectorStore` (Interface) |
| Semantic Kernel | VectorStore | `VectorStore` + `VectorStoreRecordCollection` |
| Haystack | DocumentStore | `DocumentStore` (Protocol) |

Using "Repository" would confuse developers familiar with these frameworks and misrepresent the abstraction's semantics.

### 3. Method names must be backend-agnostic

S3 Vectors SDK uses `put_vectors`/`query_vectors`/`get_vectors`/`delete_vectors`. Exposing these names in the domain protocol would couple the interface to S3's naming, making pgvector integration awkward later.

## Alternatives Considered

### A. Repository pattern with DynamoDB-style naming

Mirror `BaseDynamoRepository` exactly: `put_item()`, `get_item()`, `query_items()`, `delete_item()`.

Rejected: This was the initial implementation. It forced CRUD semantics onto non-CRUD operations (similarity search is not query by key) and deviated from every vector DB framework's conventions. Changed before merge after industry convention review.

### B. LangChain-compatible interface (`add_texts`, `similarity_search`)

Adopt LangChain's exact method names to maximize ecosystem compatibility.

Rejected: LangChain's interface couples embedding generation with storage (`add_texts` generates embeddings internally). Our architecture separates these concerns -- embedding is a domain service responsibility, not the store's. Also, `add_texts` implies text input, but the store accepts pre-computed vectors.

### C. VectorStore pattern with backend-agnostic method names (chosen)

Define `BaseVectorStoreProtocol` with `upsert`/`search`/`get`/`delete`. S3 Vectors and future pgvector both implement this protocol.

Chosen: Follows industry naming conventions (Pinecone's `upsert`, Semantic Kernel's `search`), separates embedding from storage, and works naturally for any vector backend.

## Decision

### 1. VectorStore pattern, not Repository

The domain protocol is `BaseVectorStoreProtocol`, not `BaseVectorRepositoryProtocol`. The infrastructure implementation is `BaseS3VectorStore`, not `BaseS3VectorRepository`.

This is an intentional divergence from the project's RDB/DynamoDB convention. Repository is for aggregate persistence; VectorStore is for embedding storage and similarity search.

### 2. Backend-agnostic protocol with backend-specific implementations

```
domain/protocols/
  vector_store_protocol.py    # upsert / search / get / delete

infrastructure/
  s3vectors/                   # S3 Vectors implementation
    base_s3vector_store.py     # implements protocol, calls S3 API internally
  pgvector/                    # (future) pgvector implementation
    base_pgvector_store.py     # implements same protocol, uses SQLAlchemy
```

The protocol uses generic names (`upsert`, `search`). The S3 implementation internally calls `put_vectors`, `query_vectors`, etc. When pgvector is added, it will use SQL INSERT and `<=>` operator internally, but expose the same interface.

### 3. No BaseVectorService

Unlike `BaseDynamoService` (which wraps `BaseDynamoRepository`), there is no `BaseVectorService`. Reasons:

- A pass-through service that only delegates to the store adds no value
- Domain services (e.g., `QuestionService`) inject `VectorStore` directly alongside `EmbeddingService` to orchestrate domain-specific logic
- This matches industry practice -- LangChain, LlamaIndex, and production RAG systems call VectorStore directly

### 4. DTO pattern over Document

LangChain uses `Document(page_content, metadata)` as the universal data unit. We chose not to adopt this:

- "Document" is LangChain-specific (Qdrant uses "Point", Pinecone uses "Record", Milvus uses "Entity")
- The `page_content + metadata` structure is too rigid for non-text embeddings (product vectors, user profile vectors, code embeddings)
- Our DTO pattern (domain-specific PutDTO/ReturnDTO) is more flexible and consistent with the project's existing data flow

### 5. Backend-specific infrastructure directory

```
infrastructure/vectors/    # not infrastructure/vector/
```

Named after the backend (like `infrastructure/dynamodb/`), not the concept. When pgvector is added, it goes in `infrastructure/pgvector/`. This prevents confusion about which code is generic vs backend-specific.

### 6. VectorModel for storage serialization

`VectorModel` is the infrastructure serialization model (like `DynamoModel`). It handles `to_s3vector()` / `from_s3vector()` conversion and is never exposed outside the store. Domain code only sees DTOs.

## Rationale

### Infrastructure Selection Framework (extended from ADR 029)

| Condition | Pattern | Example |
|-----------|---------|---------|
| Same class, different params | Parameter switching | S3/MinIO (023), PostgreSQL/MySQL (027) |
| Different classes, different signatures | `providers.Selector` | SQS/RabbitMQ/InMemory (029) |
| **Different paradigm (not CRUD)** | **Dedicated pattern (VectorStore)** | **S3 Vectors / pgvector (this)** |

### Why Diverge from Repository?

The project uses Repository for RDB and DynamoDB because those are CRUD storage systems. Forcing the same pattern onto vector operations would be consistency for its own sake -- the kind of consistency that makes code harder to understand by hiding fundamental differences behind a familiar name.

A developer seeing `BaseS3VectorStore.search(query)` immediately understands this is similarity search. A developer seeing `BaseS3VectorRepository.query_vectors(query)` has to wonder if this is a key-based query (like DynamoDB) or something else.

### Trade-offs Accepted

- **Two patterns in one project**: Repository for CRUD storage, VectorStore for similarity search. This adds conceptual overhead but accurately represents the underlying difference.
- **No Service base class**: Domains that need complex orchestration (embedding + search + reranking) must write their own service composition. This is intentional -- that orchestration is domain logic, not infrastructure.
- **S3 Vectors first, pgvector later**: Only one backend is implemented. The protocol is designed for multi-backend, but the pgvector implementation is deferred. The risk is that the protocol may need adjustment when pgvector is actually added.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
