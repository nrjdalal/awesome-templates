# AI Infrastructure Overview

> Living reference for AI infrastructure decisions and issue status.
> Covers PydanticAI core (#15 — completed), OTEL observability (#74 split — shipped), AI Usage Tracking (#75 — shipped), and the prompt provider contract (#447 — ADR 066).
> Not a substitute for canonical sources (`AGENTS.md`, `project-dna.md`); use for current issue status and OTEL backend comparison.
>
> **2026-04-28 update**: ADR 038 (Langfuse 1st-class) superseded by ADR 046 (OTEL core + Langfuse opt-in recipe + prompt domain defer). Architecture diagram and technology table updated accordingly.

## Architecture Diagram

```
PydanticAI Agent execution
│
├─ Trace path: OTEL spans ──→ OTLP backend (backend-agnostic)
│   │   Backends: Jaeger / Grafana Tempo / Arize Phoenix / Langfuse (opt-in)
│   │
│   ├─ Base (otel extra): token usage, latency, input/output messages
│   │
│   └─ Langfuse opt-in recipe:
│       ├─ Current recipe receives OTLP traces only
│       ├─ Prompt version → trace linkage requires Langfuse SDK/API
│       └─ Evaluation scores, datasets, and A/B labels require SDK/API or span processing
│
└─ Usage path: result.usage() ──→ Self DB (ai_usage_log)
    ├─ Customers: per-org AI call history
    ├─ Customers: real-time usage/cost dashboard
    ├─ Customers: billing justification
    └─ Ops team: per-org cost monitoring (NiceGUI admin)
```

## Technology Choices

| Component | Choice | Why | ADR |
|-----------|--------|-----|-----|
| Agent Framework | PydanticAI v1.0+ | Pydantic-native structured output, OTEL standard, FastAPI DI philosophy, v1.0 stable | [037](../../history/037-pydanticai-agent-integration.md) |
| Trace output | OTEL (OTLP exporter) | Backend-agnostic; `Agent.instrument_all()` one line; any OTLP backend works | [046](../../history/046-otel-core-langfuse-recipe-prompt-domain-defer.md) |
| Langfuse | Opt-in recipe | MIT OSS; current recipe receives OTLP traces only; prompt linking, eval, and A/B analysis require Langfuse SDK/API or span processing; not required at quickstart | [046](../../history/046-otel-core-langfuse-recipe-prompt-domain-defer.md) |
| Customer Billing | Self-owned `ai_usage` domain | Business-critical data cannot depend on external system | [046](../../history/046-otel-core-langfuse-recipe-prompt-domain-defer.md) |
| Prompt management | Prompt provider contract + minimal self-hosted DB store (#451) | ADR 046's first trigger was met (non-developer editing without deploy). Only the persona is editable; the boundary tail stays in code. Langfuse rejected for operational burden; operators edit on `/admin/prompts` ([runbook](../../operations/prompt-management.md)) | [066](../../history/066-prompt-provider-contract.md) (amends [046](../../history/046-otel-core-langfuse-recipe-prompt-domain-defer.md)) |

### OTEL Backend Comparison

Teams choosing an OTLP backend:

| Backend | Self-host | Prompt mgmt | Evaluation | Best for |
|---------|-----------|-------------|------------|----------|
| **Langfuse** | Docker Compose (5 services) | Full when SDK/API is integrated; not from OTLP-only recipe | Datasets and scores when SDK/API is integrated | Full LLMOps (prompt iteration + eval loop) |
| Arize Phoenix | Docker (single container) | ❌ | ✅ basic | Trace inspection + drift detection |
| Grafana Tempo | Docker | ❌ | ❌ | Existing Grafana stack |
| Jaeger | Docker (single container) | ❌ | ❌ | Simple trace inspection |

All accept OTLP — only the exporter endpoint changes. No agent code modifications required when switching.

### Rejected Alternatives

- **LangChain**: Layer architecture conflict, heavy abstraction
- **Agno**: Non-OTEL tracing, not Pydantic-native
- **Direct SDK**: No abstraction, duplicated boilerplate across 10+ domains
- **LangSmith**: LangChain-centric, $39/user/month, limited self-hosting
- **Helicone**: Shallow tracing, proxy-based architecture
- **Langfuse as mandatory** (ADR 038): 5-component quickstart stack; violates ADR 042 opt-in principle

## Issue Dependencies

```
Issue #15 (PydanticAI Core) — COMPLETED
├──→ #74-A / #136 (OTEL core setup)                  ← SHIPPED PR #141
│       └──→ #74-B / #137 (Langfuse opt-in recipe)   ← SHIPPED PR #142
└──→ #75 (AI Usage Tracking Domain)                  ← SHIPPED PR #149
        └──→ #97 (simple-chatbot example)             ← OPEN (depends on #75)
```

## Key Design Decisions

1. **No BaseAgentProtocol** — PydanticAI Agent IS the abstraction. Double-wrapping adds complexity without value.
2. **No provider-switching Selector inside LLM adapters** — CoreContainer still uses an enabled/disabled Selector; PydanticAI handles provider switching internally via `model="provider:model-name"` string.
3. **No BaseAIService** — AI services are heterogeneous (classify, generate, query). No common CRUD interface to factor out.
4. **Hybrid DI** — dependency-injector for database/providers; LLMConfig is constructed inside the lazy factory; PydanticAI RunContext for per-request data (org_id, user_id).
5. **LLMConfig value object** — Domain layer cannot import Settings (infrastructure). `LLMConfig(model_name, api_key)` carries only what agents need.
6. **OTEL path independence** — OTEL→backend failure does not affect customer billing. Self DB failure does not affect tracing.
7. **Optional infrastructure** — `OTEL_ENABLED=false` (default) means zero overhead at quickstart. `uv sync --extra otel` enables tracing.
8. **Prompt provider, not a prompt domain** — `PromptProviderProtocol.get_active(name, *, default) -> PromptSnapshot` (ADR 066). `DbPromptProvider` (a plain `CoreContainer` Singleton, #451) serves the active stored version (`source="self"`) or the code persona; it reads once per call with no cache and degrades to the code persona (`inline`, `prompt_store_unavailable` log) on any failure. The store is limited to the minimum in ADR 066 Decision 5 (registered names only, append-only versions, save ≠ activate, `prompts` permission, audited writes); a full prompt editor remains rejected.
9. **prompt_version is metadata, not a registry** — Nullable `prompt_version` in `ai_usage_log` is a billing/analytics label. Real agent calls record `prompt_name` and `prompt_source`; inline calls leave `prompt_version` and `external_prompt_ref` null (ADR 066 Decision 4), and a stored version records `prompt_version=<n>` and `external_prompt_ref=name@<n>`.

## File Map by Issue

The [historical file map](../../history/archive/harness-context/ai-infrastructure-file-map.md) records issue-by-issue implementation history. Use current source links below for new work.

## Patterns to Follow

| Pattern | Reference Implementation | Key File |
|---------|--------------------------|----------|
| Optional infra (Settings + Selector) | Embedding provider | `src/_core/config.py` + `core_container.py` |
| Lazy import for optional extras | PydanticAI embedding adapter | [embedding adapter](../../../src/_core/infrastructure/embedding/pydantic_ai_embedding_adapter.py) |
| Bootstrap conditional init | `_mount_admin_if_available()` | [server bootstrap](../../../src/_apps/server/bootstrap.py) |
| Pydantic ValueObject (frozen, validated) | EmbeddingConfig or VectorQuery | `src/_core/domain/value_objects/` |
| Domain auto-discovery | discover_domains() | `src/_core/infrastructure/discovery.py` |
| Admin page (BaseAdminPage) | User admin | `src/user/interface/admin/` |
