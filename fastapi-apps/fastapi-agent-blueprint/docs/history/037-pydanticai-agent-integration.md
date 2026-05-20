# 037. PydanticAI Agent Integration

- Status: Accepted
- Date: 2026-04-15
- Related issue: #15
- Related ADRs: [029](archive/029-broker-abstraction-selector.md)(Selector pattern), [034](archive/034-s3vectors-vectorstore-pattern.md)(VectorStore pattern), [035](archive/035-embedding-service-abstraction.md)(Embedding abstraction)

## Summary

To provide shared LLM/agent infrastructure for AI-powered domain services, we adopt PydanticAI as the agent framework. Unlike Embedding (ADR 035) or Broker (ADR 029), no `BaseAgentProtocol` or `providers.Selector` is needed — PydanticAI already abstracts model providers internally. The core layer provides only an `LLMConfig` value object and Settings fields; each domain creates its own PydanticAI `Agent` instances directly.

## Background

- **Trigger**: Issue #15 — as AI features become common in the platform, there is no standardized way to integrate LLM-powered functionality within the project's layered architecture. Each domain would need to independently set up model clients, handle structured outputs, and manage provider authentication.

- **Decision type**: Upfront design — evaluated four framework alternatives (PydanticAI, LangChain, Agno, Direct SDK) against the project's existing architecture patterns before implementation.

### Prior Art in the Project

| Infrastructure | Selection Pattern | ADR |
|---------------|-------------------|-----|
| S3/MinIO | Parameter switching (endpoint_url) | [023](archive/023-object-storage-unification.md) |
| PostgreSQL/MySQL/SQLite | Parameter switching (engine) | [027](archive/027-flexible-rdb-configuration.md) |
| SQS/RabbitMQ/InMemory | `providers.Selector` (different classes) | [029](archive/029-broker-abstraction-selector.md) |
| OpenAI/Bedrock Embedding | `providers.Selector` (different classes) | [035](archive/035-embedding-service-abstraction.md) |
| S3 Vectors VectorStore | Dedicated pattern (different paradigm) | [034](archive/034-s3vectors-vectorstore-pattern.md) |
| **PydanticAI Agent** | **No project-level abstraction needed** | **037 (this)** |

## Problem

### 1. No shared LLM infrastructure

Each domain that needs LLM-powered features must independently:
- Configure model provider clients (OpenAI, Anthropic, Bedrock)
- Handle API key management and authentication
- Implement structured output parsing and validation
- Define tool functions and manage agent state
- Handle provider-specific errors (rate limits, context length, auth failures)

This leads to duplicated setup across domains and makes provider switching a cross-cutting change.

### 2. Structured output needs Pydantic-native handling

The project's data flow relies on Pydantic models at every layer (Request → DTO → Model → DTO → Response). LLM outputs need to fit into this chain as validated Pydantic models, not raw strings parsed ad-hoc.

| Without framework | With PydanticAI |
|-------------------|-----------------|
| `json.loads(response.text)` → manual validation | `result_type=ClassificationDTO` → auto-validated |
| Provider-specific response format | Unified `result.output` across all providers |
| Retry logic for malformed JSON | Built-in retry with structured output validation |

### 3. Two DI systems must coexist

The project uses `dependency-injector` for singleton/factory management (database, HTTP clients, configuration). PydanticAI has its own DI via `RunContext[DepsT]` for request-scoped dependencies. These serve different purposes and must work together without conflict.

## Alternatives Considered

### A. LangChain

Full orchestration framework with 1,000+ integrations and pre-built chains.

**Rejected**: (1) Issue #15 itself noted LangChain's heavy abstraction may conflict with the project's own layered patterns. (2) LangChain 1.0 (October 2025) introduced breaking changes that left much of the ecosystem outdated. (3) LangChain enforces its own chain/agent abstractions that would compete with the project's UseCase layer for control flow. (4) Developer experience scored 5/10 in the Nextbuild 90-day benchmark, vs PydanticAI's 8/10.

### B. Agno (formerly PhiData)

High-performance agent framework with 3μs instantiation, clean API, and native tracing.

**Rejected**: (1) Agno uses its own proprietary tracing system, not OTEL standard — connecting to Langfuse or other observability tools requires additional integration work. (2) Not Pydantic-native — while it supports Pydantic models, it wasn't built by the Pydantic team and doesn't share the FastAPI DI philosophy. (3) The performance advantage (3μs vs hundreds of μs) is irrelevant when LLM calls themselves take seconds. (4) Newer framework with less production track record than PydanticAI v1.0.

### C. Direct SDK usage (anthropic/openai)

Use provider SDKs directly with manual structured output handling.

**Rejected**: (1) No multi-model abstraction — each domain must handle provider-specific APIs. (2) Structured output requires manual JSON parsing and validation — exactly what PydanticAI automates. (3) No built-in tool/function calling abstraction. (4) At the scale of 10+ domains, the duplicated boilerplate becomes a maintenance burden. (5) No OTEL instrumentation — observability must be built from scratch.

### D. PydanticAI (chosen)

Python agent framework from the Pydantic team, designed for production use with FastAPI-like developer experience.

## Decision

### 1. PydanticAI as the agent framework

PydanticAI v1.0 (stable since September 2025) provides:
- `result_type=PydanticModel` — structured output that maps 1:1 to project DTOs
- `RunContext[DepsT]` — request-scoped dependency injection
- `Agent.instrument_all()` — OTEL-standard instrumentation for any observability backend
- 20+ model providers (OpenAI, Anthropic, Bedrock, Gemini, etc.) via a single `model` string

### 2. No BaseAgentProtocol

Unlike Embedding (where OpenAI and Bedrock have fundamentally different SDK APIs hidden behind `BaseEmbeddingProtocol`), PydanticAI's `Agent` class IS the abstraction layer. Creating a `BaseAgentProtocol` on top would be double-indirection with no value.

This follows the same reasoning as ADR 034's VectorStore — when the external tool already provides a clean abstraction, wrapping it in a project protocol adds complexity without benefit.

### 3. No providers.Selector for LLM

PydanticAI handles model switching internally via the `model` parameter string (e.g., `"openai:gpt-4o"`, `"anthropic:claude-sonnet-4-20250514"`). There are no separate client classes with different constructors — it's a single `Agent` class with a model string.

In the Infrastructure Selection Framework:

| Condition | Pattern | PydanticAI fit |
|-----------|---------|----------------|
| Same class, different params | Parameter switching | **Yes — `Agent(model="openai:...")` vs `Agent(model="anthropic:...")`** |
| Different classes, different signatures | `providers.Selector` | No — only one `Agent` class |
| Different paradigm | Dedicated pattern | N/A |

### 4. Core provides LLMConfig + Settings only

```
src/_core/config.py                              # LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, Bedrock fields
src/_core/domain/value_objects/llm_config.py     # LLMConfig(model_name, api_key) — frozen dataclass
src/_core/infrastructure/di/core_container.py    # llm_config = providers.Singleton(LLMConfig, ...)
src/_core/infrastructure/llm/exceptions.py       # LLMException hierarchy
```

Domain services receive `LLMConfig` via DI and construct their own `Agent` instances with domain-specific `system_prompt`, `output_type`, `deps_type`, and tool functions.

### 5. Hybrid DI pattern

Two DI layers serving different lifetimes:

| Layer | System | Lifetime | Examples |
|-------|--------|----------|----------|
| Infrastructure | dependency-injector | Singleton/Factory (app lifecycle) | `LLMConfig`, database, HTTP clients |
| Request | PydanticAI `RunContext` | Per-call | `user_id`, `org_id`, session context |

```python
class ClassificationService:
    def __init__(self, llm_config: LLMConfig) -> None:   # ← dependency-injector
        self._agent = Agent(model=llm_config.model_name, ...)
    
    async def classify(self, text: str) -> ClassificationDTO:
        result = await self._agent.run(text)              # ← RunContext for request deps
        return result.output
```

### 6. No BaseAIService

AI agent services are heterogeneous — a classification service has `classify()`, a generation service has `generate()`, a RAG service has `query()`. There is no common CRUD-like interface to factor out. This follows the VectorStore precedent (ADR 034): when operations don't share a common shape, an empty base class adds no value.

### 7. Optional dependency with lazy import

```toml
[project.optional-dependencies]
pydantic-ai = ["pydantic-ai>=1.0.0"]
pydantic-ai-bedrock = ["pydantic-ai[bedrock]>=1.0.0"]
```

Domain services that use PydanticAI import it inside `__init__` with a clear error message, following the broker/embedding lazy-import convention.

## Rationale

### Infrastructure Selection Framework (extended)

| Condition | Pattern | Example |
|-----------|---------|---------|
| Same class, different params | Parameter switching | S3/MinIO, PostgreSQL/MySQL |
| Different classes, different signatures | `providers.Selector` | Broker (029), Embedding (035) |
| Different paradigm (not CRUD) | Dedicated pattern | VectorStore (034) |
| **External framework is the abstraction** | **No project-level wrapper** | **PydanticAI Agent (this)** |

PydanticAI fits a new category in the framework: the external tool already provides the abstraction boundary that would otherwise be built as a Protocol. The project's role is to configure it (via `LLMConfig`), not to wrap it.

### Why PydanticAI specifically?

1. **Same ecosystem**: Built by the Pydantic team — same philosophy as FastAPI, long-term compatibility assured
2. **Type safety**: Benchmarked to catch 23 development-time bugs that would reach production in other frameworks (Nextbuild 90-day benchmark)
3. **OTEL standard**: Built-in instrumentation via `Agent.instrument_all()` — any observability backend (Langfuse, Phoenix, Jaeger) can be connected without agent code changes
4. **Production stable**: v1.0 since September 2025 with weekly releases and stable API commitment

## Trade-offs Accepted

- **PydanticAI version dependency**: Pinning to `>=1.0.0` means tracking PydanticAI releases. The v1.0 API stability commitment mitigates breaking change risk, but the framework is relatively young compared to core dependencies like SQLAlchemy.
- **Two DI systems coexisting**: Developers must understand when to use dependency-injector (singletons, app-level config) vs RunContext (per-request data). ADR documentation and the classification prototype domain serve as the canonical reference.
- **No retry/backoff in v1**: Like Embedding (ADR 035), the initial implementation does not include retry logic. PydanticAI has its own retry for structured output validation, but provider-level retries (rate limits, transient errors) are left to per-domain implementation.

## Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
