# 040. RAG as a Reusable `_core` Pattern, Not a Domain

- Status: Accepted
- Date: 2026-04-20
- Related issue: #80 (End-to-end RAG example)
- Related ADRs: [034](archive/034-s3vectors-vectorstore-pattern.md) (Vector store), [035](archive/035-embedding-service-abstraction.md) (Embedding abstraction), [037](037-pydanticai-agent-integration.md) (PydanticAI Agent)

## Summary

Retrieval-Augmented Generation is modeled as a reusable infrastructure pattern (`src/_core/infrastructure/rag/` + orchestrator at `src/_core/domain/services/rag_pipeline.py`), not a bounded context. A thin example consumer domain `src/docs/` uses it to deliver the `POST /v1/docs/documents` + `POST /v1/docs/query` endpoints required by #80, but the pattern is the actual reusable asset — future AI-shaped domains (`support_bot`, `product_qa`, …) plug into `RagPipeline` rather than copy-pasting RAG plumbing.

## Background

- **Trigger**: Issue #80 asked for "an end-to-end RAG domain" at `src/rag/`. Initial scaffolding followed that literal ask — full `src/rag/` domain with its own stub providers, query agent, DTOs, and container. Mid-implementation, a design review raised a valid DDD objection: "RAG" is not a bounded context, it is a *how*. Leaving it shaped as a domain would mean the next AI feature (support bot, product QA, …) has to duplicate the pipeline.

- **Prior in-tree assets**: S3 Vectors (ADR 034), embedding abstraction (ADRs 035/039), PydanticAI Agent pattern (ADR 037), chunking utility (ADR 036). These already treated the building blocks of RAG as `_core` infrastructure; only the orchestrator was missing.

## Problem

### 1. "RAG" is a pattern name, not a business capability

A bounded context is named after *what the business does*: `knowledge_base`, `support_bot`, `product_qa`. "RAG" describes a retrieval-and-generation technique — it is implementation-level vocabulary. Placing it as a domain confuses pattern with product.

### 2. Reuse regresses when the pattern lives inside one domain

If `DocumentService.create_data` owns chunk → embed → upsert and `QueryService.answer_question` owns embed → search → agent, every new AI domain must re-implement the same five-step dance. The chunking utility and embedder are already shared; the *composition* was not.

### 3. `_core` building blocks were orphaned without an orchestrator

`BaseEmbeddingProtocol`, `BaseVectorStoreProtocol`, `chunk_text`, and the new `BaseInMemoryVectorStore` are individually reusable, but there was no canonical "how to assemble them" in the blueprint. Consumers had to invent their own assembly, risking drift.

## Decision

### 1. Pattern in `_core`, consumer domain in `src/docs/`

Split the work along the pattern/consumer seam:

```
src/_core/domain/dtos/rag/
├── chunk.py                     # BaseChunkDTO
├── citation.py                  # CitationDTO
└── query_answer.py              # QueryAnswerDTO

src/_core/domain/protocols/
└── answer_agent_protocol.py     # AnswerAgentProtocol

src/_core/domain/services/
└── rag_pipeline.py              # RagPipeline[TChunk] — pure orchestrator

src/_core/infrastructure/rag/
├── stub_embedder.py             # zero-config fallback
├── stub_answer_agent.py         # zero-config fallback
└── pydantic_ai_answer_agent.py  # real LLM via PydanticAI

src/_core/infrastructure/vectors/
└── base_in_memory_vector_store.py  # process-local cosine for quickstart

src/docs/                        # Example consumer — docs QA
├── domain/services/{document_service,docs_query_service}.py
├── infrastructure/vectors/document_chunk_*.py
└── interface/server/routers/docs_router.py
```

`RagPipeline` sits under `_core/domain/services/` because it only depends on Protocols (embedder, vector store, answer agent) and value objects; no infrastructure imports. That placement keeps the "Domain → Infrastructure import" prohibition intact for consumer services.

### 2. `RagPipeline[TChunk]` is generic over the chunk shape

```python
class RagPipeline(Generic[TChunk]):
    async def answer(
        self,
        question: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> tuple[QueryAnswerDTO, list[TChunk]]: ...
```

Consumer domains define their own chunk DTO (subclassing `BaseChunkDTO` for extra metadata, or using it directly). Every chunk carries `source_id: str` and `source_title: str` so answer agents can build citations without knowing the consumer's internals.

### 3. Graceful degradation via Selector in the consumer container

`DocsContainer` wires three `providers.Selector` blocks:

- `embedder`: real `PydanticAIEmbeddingAdapter` when `EMBEDDING_*` is set, otherwise `StubEmbedder`.
- `answer_agent`: `PydanticAIAnswerAgent` when `LLM_*` is set, otherwise `StubAnswerAgent`.
- `chunk_vector_store`: `DocumentChunkS3VectorStore` when `VECTOR_STORE_TYPE=s3vectors`, otherwise `DocumentChunkInMemoryVectorStore`.

This lets `make quickstart` + `make demo-rag` run with zero external credentials while the same code path scales up to real providers in staging/prod by flipping env vars.

### 4. Stubs are `_core`, not domain

`StubEmbedder` and `StubAnswerAgent` live under `_core/infrastructure/rag/`. Any future AI domain gets graceful degradation for free. Putting them in `src/docs/` would have forced the next consumer to either re-create them or import across domains.

### 5. Issue #80 endpoints shape

Endpoints live on the consumer, not the pattern: `POST /v1/docs/documents`, `GET /v1/docs/documents`, `GET /v1/docs/documents/{id}`, `DELETE /v1/docs/documents/{id}`, `POST /v1/docs/query`. The admin surface is `/admin/docs`. The showcase command `make demo-rag` keeps its name because the *capability* being demonstrated is RAG, even though the domain driving the demo is `docs`.

## Consequences

- **New AI-shaped domains copy `src/docs/`, not the pipeline.** They define their own `{Name}ChunkDTO`, `{Name}ChunkVectorStore`, `{Name}Service`, and inject `RagPipeline` — plumbing is one-liner DI.
- **`_core/rag/` becomes a touchpoint.** Any cross-cutting RAG concern (telemetry, retry, filter defaults) should land here, not be re-invented per domain.
- **Stubs are production-visible fallbacks.** They log a WARNING at construction so stg/prod boots scream if misconfigured. Coupled with env validation (ADR around Settings model_validator), stubs should never silently ship.
- **`BaseChunkDTO.source_id` is stringified** to work uniformly across int-PK and UUID-PK domains. Consumer domains cast on read (`int(chunk.source_id)` in the docs purge path).
- **Chunks get a transient `_distance` attribute** in `RagPipeline` before the agent sees them so citations can carry retrieval distance. Underscore-prefixed so it does not leak into serialisation. The trade-off: the agent Protocol accepts *mutable* chunks, not frozen VOs. Document this in the Protocol docstring.
- **Naming**: the blueprint convention "what the business does, not how" is now normative. Future work should name domains after products (support bot, knowledge base, etc.), not patterns.

## Alternatives Considered

- **Keep `src/rag/` as a domain** (original #80 scope). Rejected: repeats RAG code for every future AI domain; conflates pattern with product.
- **Put `RagPipeline` under `_core/infrastructure/rag/`** alongside the stubs. Rejected: the pipeline has no infrastructure dependencies, only Protocol + VO imports, so placing it in domain services respects the import direction rule. Consumers can import it from `_core/domain/services` without tripping the "Domain → Infrastructure" prohibition.
- **Drop the consumer domain entirely**; ship only `_core/rag/`. Rejected: #80 needs a runnable endpoint surface to satisfy the "prove the template works" goal. A pattern with no visible consumer does not answer "does this template actually produce AI apps?".
- **Use `_core/infrastructure/rag/protocols.py` for `AnswerAgentProtocol`** (first pass). Rejected: consumer services would need to import it from infrastructure, violating the Domain → Infrastructure prohibition. Protocols moved to `_core/domain/protocols/answer_agent_protocol.py` to fix.

## Follow-ups

- Optional `_core.rag.telemetry` hook for retrieval/generation metrics (Langfuse integration path, ADR 038).
- `BaseLocalVectorStore` using sqlite-vec when quickstart eventually needs persistence across restarts.
- `Database.session()` currently wraps `BaseCustomException` into a 500 `DatabaseException`; visible in `tests/e2e/docs/test_docs_router.py::test_delete_document` where a post-delete `GET` returns 500 instead of 404. Not caused by this ADR — file separately.
