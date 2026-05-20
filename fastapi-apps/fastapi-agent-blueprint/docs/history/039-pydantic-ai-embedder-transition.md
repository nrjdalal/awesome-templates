# 039. PydanticAI Embedder Transition

- Status: Accepted
- Date: 2026-04-15
- Related issue: #15 (PydanticAI integration)
- Related ADRs: [035](archive/035-embedding-service-abstraction.md)(Embedding abstraction), [037](037-pydanticai-agent-integration.md)(PydanticAI Agent)

## Summary

Replaced the per-provider embedding clients (`OpenAIEmbeddingClient`, `BedrockEmbeddingClient`) and `providers.Selector` pattern with a single `PydanticAIEmbeddingAdapter` that delegates to PydanticAI's `Embedder`. The adapter implements `BaseEmbeddingProtocol` (unchanged) and adds OpenAI-specific batch splitting. An `EmbeddingConfig` value object (following the `LLMConfig` pattern from ADR 037) carries configuration through DI.

## Background

- **Trigger**: Planned expansion from 2 providers (OpenAI, Bedrock) to 4+ providers (OpenAI, Bedrock, Google, Ollama/SentenceTransformers). Maintaining separate SDK-wrapping clients for each provider would require ~690 lines of code + individual test suites.

- **Prior state**: ADR 035 established `BaseEmbeddingProtocol` + `providers.Selector` with `OpenAIEmbeddingClient` (~145 lines) and `BedrockEmbeddingClient` (~114 lines). Each client wrapped its respective SDK, handled batch splitting (OpenAI) or sequential calls (Bedrock), and mapped provider-specific errors to domain exceptions.

- **ADR 037 precedent**: PydanticAI Agent integration established the "external framework IS the abstraction" pattern for LLM completion. This ADR extends the same pattern to embedding.

## Problem

### 1. Linear scaling of provider code

Each new embedding provider requires a dedicated client class with:
- SDK initialization and authentication handling (~30 lines)
- `embed_text()` and `embed_batch()` implementation (~40 lines)
- Provider-specific batch/concurrency strategy (~30 lines)
- Error mapping to domain exceptions (~25 lines)
- Dimension lookup table

At 4 providers, this totals ~690 lines. At 6+ providers (Cohere, VoyageAI, etc.), it becomes a significant maintenance burden for a 5-person team.

### 2. PydanticAI already provides the abstraction

PydanticAI's `Embedder` class supports all target providers natively:
- `Embedder("openai:text-embedding-3-small")`
- `Embedder("bedrock:amazon.titan-embed-text-v2:0")`
- `Embedder("google-gla:gemini-embedding-001")`
- `Embedder("ollama:nomic-embed-text")`
- `Embedder("sentence-transformers:all-MiniLM-L6-v2")`

Adding a provider = changing a config string. No SDK wrapping code needed.

### 3. Bedrock performance gap

The existing `BedrockEmbeddingClient.embed_batch()` used sequential `for` loop processing. PydanticAI's Bedrock embedding uses semaphore-based concurrent processing (default 5 parallel requests), providing ~5x throughput improvement.

## Decision

### 1. EmbeddingConfig value object

Follows the `LLMConfig` pattern (ADR 037):

```python
@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str               # "openai:text-embedding-3-small"
    dimension: int = 1536
    api_key: str | None = None    # OpenAI/Cohere
    aws_access_key_id: str | None = None   # Bedrock
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
```

Bedrock credentials use per-service injection (project convention matching DynamoDB, SQS, S3Vectors).

### 2. PydanticAIEmbeddingAdapter

Single adapter class implementing `BaseEmbeddingProtocol`:
- Constructs PydanticAI `Embedder` with explicit `Provider` objects when credentials are provided
- Falls back to environment variable auto-detection when credentials are `None`
- OpenAI: includes batch splitting logic (2,048 items / 300K tokens per request)
- Other providers: delegates directly to PydanticAI (which handles concurrency internally)

### 3. No Selector pattern

Unlike ADR 035's `providers.Selector`, the adapter uses a single class for all providers. PydanticAI internally selects the correct provider from the model string prefix. This matches the ADR 037 infrastructure selection framework: "external framework is the abstraction."

### 4. OpenAI batch splitting retained

PydanticAI does not auto-split large batches. The adapter preserves the existing tiktoken-based splitting logic from `OpenAIEmbeddingClient` for OpenAI only. Other providers either have no batch limits (local) or PydanticAI handles them internally (Bedrock semaphore, Google native batch).

### 5. Dimension management unchanged

`settings.embedding_dimension` remains the single source of truth, derived from provider + model via lookup tables in `config.py`. Extended to support Google (768) and local models (384-768). `VectorModelMeta.dimension` continues to use this property.

## Infrastructure Selection Framework (updated)

| Condition | Pattern | Example |
|-----------|---------|---------|
| Same class, different params | Parameter switching | S3/MinIO, PostgreSQL/MySQL |
| Different classes, different signatures | `providers.Selector` | Broker (029) |
| Different paradigm (not CRUD) | Dedicated pattern | VectorStore (034) |
| External framework is the abstraction | No project-level wrapper | **PydanticAI Agent (037), PydanticAI Embedder (039)** |

## Trade-offs Accepted

- **PydanticAI Embedder version dependency**: Embedder was introduced in v1.39.0 (2025-12-24). Pinned to `>=1.39.0`.
- **OpenAI batch splitting duplicates PydanticAI intent**: PydanticAI provides `count_tokens()` and `max_input_tokens()` utilities but does not auto-split. We retain our own splitting logic until PydanticAI adds it natively.
- **Dimension lookup tables**: PydanticAI does not expose embedding dimensions programmatically. We maintain `_OPENAI_DIMENSIONS`, `_BEDROCK_DIMENSIONS`, `_GOOGLE_DIMENSIONS`, `_LOCAL_DIMENSIONS` in `config.py`.

## Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
