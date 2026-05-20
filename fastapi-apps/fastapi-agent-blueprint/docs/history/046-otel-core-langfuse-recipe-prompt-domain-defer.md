# 046. LLM Observability — OTEL Core + Langfuse Opt-in Recipe + Prompt Domain Defer

- Status: Accepted
- Date: 2026-04-28
- Related issues: #74 (Langfuse integration — superseded), #75 (AI Usage domain), #97 (simple-chatbot example)
- Related ADRs: [037](037-pydanticai-agent-integration.md)(PydanticAI), [042](042-optional-infrastructure-di-pattern.md)(Optional Infra DI), [038 (archive)](archive/038-llm-observability-dual-path.md)(superseded by this ADR)
- Supersedes: [archive/038](archive/038-llm-observability-dual-path.md)

## Summary

Re-evaluation of ADR 038 (Langfuse as 1st-class observability dependency) prompted by OSS onboarding friction and misalignment with ADR 042 (opt-in infrastructure). This ADR adopts **Model E**: OTEL as the standard trace output + Langfuse as an explicit opt-in recipe + prompt domain deferred until real demand.

The three core principles:

1. **OTEL core** — `Agent.instrument_all()` + OTLP exporter as the default trace path. Backend-agnostic: Jaeger, Tempo, Phoenix, or Langfuse.
2. **Langfuse opt-in** — `docker-compose.langfuse.yml` + `make observability-langfuse` as an explicit ops recipe. Not in quickstart.
3. **Prompt domain deferred** — Only `PromptSnapshot` value object defined now. Full prompt domain (editor, versioning, RBAC) built when real demand exists.

## Background

ADR 038 chose Langfuse as the 1st-class observability dependency for two reasons: (a) it is the only OSS tool covering tracing + prompt management + cost API, and (b) the project targets SaaS multi-tenant use where those three ops requirements coexist.

That rationale remains partially valid for **production SaaS teams** who need prompt iteration and trace linkage. However, it creates two problems that emerged after ADR 038:

| Problem | Impact |
|---------|--------|
| 5-component self-hosted stack (PG, ClickHouse, Redis, MinIO, web) required at quickstart | OSS contributors blocked on first `docker compose up` |
| ADR 042 (opt-in infra) established that no non-DB infra is mandatory | ADR 038's required Langfuse contradicts this principle |

A Codex cross-review (2026-04-28, `claude-opus-4-7`, sandbox=read-only) stress-tested four candidate models and converged on Model E as the lowest-failure-cost option. The review specifically rejected Model D (OTEL-only, no Langfuse, self-built prompt editor) for overstating what OTEL alone can replace.

## Problem

### 1. Langfuse at quickstart violates ADR 042

ADR 042 established that no non-DB infrastructure is mandatory — all optional infras use `providers.Selector` + graceful degradation. A required 5-component Langfuse stack is the single largest exception to this principle and the most common OSS onboarding failure point.

### 2. "OTEL-only" does not replace Langfuse-native features

PydanticAI's `Agent.instrument_all()` emits OTEL GenAI semantic convention spans. This covers: token usage, input/output messages, system instructions, latency. It does **not** cover:

- Prompt version linkage (which version was served for a given trace)
- Evaluation scores and dataset regression tests
- A/B prompt label analysis
- Live prompt editing with trace feedback

Langfuse receives OTLP, but its prompt linking, scores, datasets, and evaluations require the Langfuse SDK/API or custom span processors — not just OTLP. "OTEL-standardized" means trace *collection* is backend-agnostic, not that LLMOps product features are portable.

### 3. Self-built prompt editor is underscoped

An in-house NiceGUI prompt editor can reach CRUD parity in ~1 week. An **operationally viable** prompt editor requires diff view, rollback, audit trail, variable validation, preview/compile test, staging/production label workflow, RBAC, and concurrent edit conflict handling. Omitting these produces a DB row editor, not a prompt management system.

Additionally, a 30-second in-memory TTL cache is not "live editing" — it is eventual consistency with up to 30s lag. In multi-worker deployments (4 server processes + 2 workers), a bad prompt rollback leaves some workers serving the bad version for up to 30 seconds with no trace linkage to identify affected requests.

### 4. prompt_id FK creates premature lock-in

Wiring `ai_usage_log` to a `prompt` table FK before the prompt domain is built forces the schema to commit to a domain model that does not yet exist. Nullable metadata columns are the minimum viable anchor.

## Alternatives Considered

| Model | Summary | Key risk | Verdict |
|-------|---------|----------|---------|
| **A — Langfuse mandatory** (ADR 038) | Langfuse 1st-class, required at quickstart | OSS onboarding barrier; violates ADR 042 | Rejected |
| **B — Self-build only** | Custom trace waterfall + prompt editor; no Langfuse | Span waterfall UI + prompt versioning = months of work | Rejected |
| **C — Selector dual-path** | Maintain both Langfuse and self-built paths simultaneously | Two code paths, maintenance cost scales with both | Rejected |
| **D — OTEL-only** | OTEL trace out + self-built prompt CRUD + ai_usage domain; Langfuse deprecated | Conflates "OTEL trace collection" with "LLMOps product features". Self-built prompt editor underscoped. Internal contradiction: PromptServiceProtocol DIP + "defer Selector abstraction" cannot coexist | Rejected (Codex cross-review) |
| **E — OTEL core + Langfuse recipe (chosen)** | OTEL as trace standard + Langfuse as explicit opt-in + prompt domain deferred | Langfuse-native features (prompt linking, eval) require opt-in recipe step; prompt management absent until real demand | **Adopted** |

## Decision

### 1. OTEL core (`otel` extra)

OTLP trace output as the standard. Backend-agnostic — any OTLP-compatible backend (Jaeger, Grafana Tempo, Arize Phoenix, Langfuse) works.

```python
# pyproject.toml
[project.optional-dependencies]
otel = [
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp-proto-grpc",
]

# src/_core/infrastructure/observability/otel_setup.py
def configure_otel(settings: Settings) -> None:
    """Called at server/worker bootstrap when OTEL_ENABLED=true."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    ...
    Agent.instrument_all()  # PydanticAI GenAI semantic convention spans

# bootstrap.py
def _maybe_configure_otel(settings: Settings) -> None:
    if not settings.otel_enabled:
        return
    try:
        from src._core.infrastructure.observability.otel_setup import configure_otel
        configure_otel(settings)
    except ImportError:
        logger.warning("otel_extra_not_installed", hint="uv sync --extra otel")
```

**Settings additions** (`src/_core/config.py`):
```
otel_enabled: bool = False                         # OTEL_ENABLED
otel_exporter_otlp_endpoint: str | None = None     # OTEL_EXPORTER_OTLP_ENDPOINT
```

**Default state**: `make quickstart` works unchanged. Zero new required env vars.

### 2. Langfuse opt-in recipe

Langfuse is not removed — it becomes an explicit ops recipe for teams that need prompt linking and evaluation.

```
# Opt-in (not in base quickstart)
make observability-langfuse   # starts docker-compose.langfuse.yml
# then set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# What OTLP alone gives you (backend-agnostic):
#   token usage, latency, input/output messages, system instructions

# What requires Langfuse SDK/API in addition:
#   prompt version → trace linkage
#   evaluation scores and datasets
#   A/B label analysis
# See docs/operations/observability-langfuse.md for the full recipe.
```

`docker-compose.langfuse.yml` remains in the repo for teams that want it. It is **not** referenced from `docker-compose.yml` or `make quickstart`.

### 3. AI Usage domain (#75) — nullable prompt reference columns

`ai_usage_log` records nullable prompt metadata instead of a `prompt_id` FK:

| Column | Type | Purpose |
|--------|------|---------|
| `prompt_name` | `String(200), nullable` | Prompt identifier (name or key) |
| `prompt_version` | `String(50), nullable` | Version label — Langfuse-compatible string, not integer |
| `prompt_source` | `String(20), nullable` | `"inline"` \| `"langfuse"` \| `"self"` \| `None` |
| `external_prompt_ref` | `String(500), nullable` | Langfuse prompt UUID or other external reference |

**Important constraint**: these columns are **usage metadata for billing/analytics only** — they are not a reproducible prompt registry. A `prompt_version` label may point to different content over time (labels move). If exact prompt reproduction is required, that signals time to build the deferred prompt domain (see §4 below).

### 4. PromptSnapshot value object (deferred domain anchor)

The full prompt domain (editor, versioning, RBAC) is deferred. A lightweight `PromptSnapshot` value object is defined now so consumer domains have a stable contract.

```python
# src/_core/domain/value_objects/prompt_snapshot.py
from src._core.domain.value_objects.base import ValueObject  # Pydantic BaseModel, frozen=True

class PromptSnapshot(ValueObject):
    """Immutable carrier for a resolved prompt at execution time.

    Pydantic ValueObject base chosen (over plain frozen dataclass) because
    name/source validation is needed: name must be non-empty, source must be
    a known vocabulary. Config-only VOs with no validation use dataclass(frozen=True);
    this VO has lightweight field constraints.
    """
    name: str
    version: str | None = None
    content: str
    source: str  # "inline" | "langfuse" | "self"
    external_ref: str | None = None
    metadata: dict = {}

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt name must not be empty")
        return v
```

Consumer domains use `get_active(name) -> PromptSnapshot` as the contract. The concrete implementation is deferred — consumers stub with `PromptSnapshot(name="...", content=INLINE_PROMPT, source="inline")`.

**Trigger conditions to build the full prompt domain**:
- A non-developer needs to edit prompts without code deployment, **or**
- The project operates 3+ distinct prompts simultaneously requiring version management

### 5. simple-chatbot example (#97)

`examples/simple-chatbot/` uses an inline system prompt (module constant). No dependency on `ai_usage` or the prompt domain.

```python
SYSTEM_PROMPT = "You are a helpful assistant."
# tokens_used shown in response for educational purposes only.
# Production usage tracking: see ai_usage domain (#75).
```

## Rationale

### Why not commit to the prompt domain now?

The two real trigger conditions (non-developer editing + multi-prompt operations) are not yet present in this project. Building a production-grade prompt editor before the demand exists is the exact failure mode ADR 042 was written to prevent. The `PromptSnapshot` contract is sufficient — consumer domains can be written against the interface today without the implementation.

### Why keep Langfuse at all?

Langfuse remains the best opt-in tool for teams who need prompt-to-trace linkage, evaluation datasets, and A/B analysis. Removing it from the recipe would force those teams to rebuild functionality that is free under MIT. The key change is: Langfuse is no longer a default dependency, it is an explicitly-documented opt-in path.

### Why OTEL as the core?

`Agent.instrument_all()` is one line. Any OTLP-compatible backend receives the standard GenAI semantic convention spans immediately. Teams not needing LLMOps product features (small projects, quickstart evaluation, cost-conscious deployments) get useful telemetry with zero vendor commitment.

## Trade-offs Accepted

- **Prompt management absent from base blueprint** — teams that expect a prompt editor out of the box will find it missing. Mitigation: the `PromptSnapshot` contract and defer rationale in this ADR are documented so contributors know exactly when to build it.
- **Langfuse-native features require opt-in recipe step** — prompt-to-trace linkage requires following `docs/operations/observability-langfuse.md`. This cannot be simplified further without re-introducing Langfuse as a required dependency.
- **prompt_version is not a reproducible reference** — Langfuse labels can move. Teams relying on exact reproduction must either use `external_prompt_ref` (Langfuse prompt UUID, which is stable) or wait for the full prompt domain.

## Issue Sequence

This ADR governs the following issue updates (execute after this ADR merges):

1. #74 closed (superseded by PR #135). Split follow-ups: #136 (OTEL core setup), #137 (Langfuse opt-in recipe).
2. Update #75 acceptance: replace `prompt_id FK` with the four nullable columns above + the "usage metadata only" disclaimer.
3. Update #97 acceptance: inline system prompt, no prompt domain dependency, `tokens_used` retained as educational output.

## Self-check

- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Does this align with ADR 042 (optional infrastructure)?
- [x] Were the Codex cross-review corrections (PromptSnapshot base class, prompt_version semantics, placeholder issue numbers) incorporated?
