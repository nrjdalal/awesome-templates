# 038. LLM Observability — Dual-Path Architecture

- Status: Superseded by [046](../046-otel-core-langfuse-recipe-prompt-domain-defer.md)
- Date: 2026-04-15
- Related issue: #15 (design), subsequent issues for Langfuse and AI Usage implementation
- Related ADRs: [037](../037-pydanticai-agent-integration.md)(PydanticAI), [029](029-broker-abstraction-selector.md)(Selector pattern), [035](035-embedding-service-abstraction.md)(Embedding abstraction)

## Summary

To serve both ops team observability (tracing, prompt management) and customer-facing billing (usage history, cost tracking), we adopt a dual-path architecture: OTEL spans flow to self-hosted Langfuse for ops, while `result.usage()` data flows to a self-owned `ai_usage` domain for customer billing. Neither path depends on the other.

## Background

- **Trigger**: The platform is a SaaS product where multiple customer organizations use AI features. Three distinct audiences need different views of AI operations:

  | Audience | Needs | Data depth |
  |----------|-------|------------|
  | Ops team | Step-by-step tracing, debugging, prompt iteration | Full span waterfall, input/output at each step |
  | Prompt designers | Live prompt editing without deploy, version management | Prompt templates, A/B versions |
  | Customers (orgs) | Call history, real-time usage/cost, billing justification | Summary: call count, tokens, cost per period |

- **Decision type**: Upfront design — evaluated five observability platforms (Langfuse, LangSmith, Arize Phoenix, Helicone, self-built) before choosing the architecture.

### Constraint: customer-facing billing data must be self-owned

Billing data shown to customers is business-critical. If it lives only in an external system (Langfuse), then:
- Langfuse outage = billing dashboard outage
- Langfuse schema change = billing API breakage
- Langfuse data retention policy ≠ business data retention requirement

This constraint eliminates any single-system solution — the billing path must use the project's own database.

## Problem

### 1. Tracing self-build is cost-prohibitive

Building step-by-step span visualization (waterfall UI), span filtering/search, and prompt version management from scratch is a multi-week project. Langfuse already provides all of this with MIT-licensed open source.

### 2. Billing data in external system is risky

Langfuse's Metrics API (`GET /api/public/metrics/daily`, SDK `metrics.get()`) can aggregate cost by userId/tags. But making customer-facing billing depend on Langfuse API availability, query performance, and data format creates an unnecessary coupling for business-critical data.

### 3. Prompt management needs a dedicated tool

Prompt designers need to edit prompts in a UI without code deployment. Options: (a) build a prompt management UI, (b) use Langfuse's built-in prompt management. Option (b) is significantly less effort and already integrates with PydanticAI.

## Alternatives Considered

### A. Langfuse only (ops + billing from same source)

Route everything through Langfuse. Query Langfuse Metrics API for customer billing data.

**Rejected**: Couples customer-facing billing to observability infrastructure. Langfuse schema changes or outages would break billing. Additionally, Langfuse's multi-tenancy (Organization → Project) is designed for ops team access, not customer self-service — customers would never log into Langfuse.

### B. Self-build only (custom tracing + billing)

Build all tracing, prompt management, and billing in-house.

**Rejected**: Span waterfall visualization, prompt version management with live editing, and trace search/filtering represent months of development. The ops team would use a significantly inferior tool during this period. This is not the project's core value.

### C. Dual-path (chosen)

Langfuse for ops (tracing + prompt management), self-owned database for customer billing (usage history + cost tracking). The two paths are independent.

### Observability Platform Comparison

| Criterion | Langfuse | LangSmith | Arize Phoenix | Helicone |
|-----------|---------|-----------|---------------|----------|
| License | MIT (all features) | Proprietary | Apache 2.0 | Apache 2.0 |
| Self-hosting | Docker Compose (PG + ClickHouse) | Limited | Docker (single) | Docker |
| PydanticAI integration | `Agent.instrument_all()` one line | LangChain-centric | OTEL exporter | Proxy-based |
| Tracing depth | Span waterfall, step I/O | Deepest | Spans + drift detection | Basic |
| Prompt management | Version control + live edit + SDK fetch | Yes | **None** | **None** |
| Cost tracking API | Metrics API (SDK + REST) | REST API | Basic | Strong (proxy-accurate) |
| Multi-tenancy | Org → Project 3-tier hierarchy | Organization | Single project | Virtual keys |
| Community | 21k+ GitHub stars | N/A (proprietary) | 10k+ stars | 8k+ stars |
| Pricing (cloud) | Free tier + usage-based | $39/user/month | Free (self-host) | Free tier |

**Langfuse wins because it uniquely covers all three ops requirements**: tracing, prompt management, and cost API. Phoenix lacks prompt management. Helicone lacks tracing depth. LangSmith is LangChain-centric and primarily cloud-hosted.

## Decision

### 1. Dual-path architecture

```
PydanticAI Agent execution
│
├─ Path 1: OTEL spans ──→ Langfuse (self-hosted)
│   └─ Ops team only
│       ├─ Step-by-step tracing (span waterfall)
│       ├─ Prompt management (live edit, version control)
│       └─ Model-level cost analysis
│
└─ Path 2: result.usage() ──→ Self DB (ai_usage_log table)
    └─ Customer-facing + ops monitoring
        ├─ Per-org AI call history
        ├─ Real-time usage/cost dashboard
        └─ Billing justification data
```

### 2. Langfuse integration (ops path)

**Settings** (`src/_core/config.py`):
```python
langfuse_enabled: bool = Field(default=False, validation_alias="LANGFUSE_ENABLED")
langfuse_public_key: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
langfuse_secret_key: str | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
langfuse_host: str | None = Field(default=None, validation_alias="LANGFUSE_HOST")
```

Validation: when `langfuse_enabled=true`, all three key/host fields must be set (partial config group pattern).

**Infrastructure** (`src/_core/infrastructure/langfuse/`):
```
langfuse_client.py     # Langfuse SDK wrapper (lazy import, get_prompt, flush/shutdown)
otel_setup.py          # OTLPSpanExporter → Langfuse OTEL endpoint, Agent.instrument_all()
prompt_service.py      # Prompt fetch + cache + graceful fallback (None when disabled)
exceptions.py          # LangfuseException hierarchy
```

**Bootstrap**: `Agent.instrument_all()` called at server/worker startup when `LANGFUSE_ENABLED=true`. When disabled, agents function normally without tracing.

**Docker Compose**: Separate `docker-compose.langfuse.yml` (PostgreSQL:5433, ClickHouse, Redis:6380, MinIO:9090, langfuse-worker, langfuse-web:3000). Port collision avoided with existing dev services.

**Prompt management pattern**:
```python
# Prompt designer edits in Langfuse UI → no deploy needed
prompt = prompt_service.get_system_prompt("classification-v1")
agent = Agent(model=..., system_prompt=prompt or "default fallback...")
```

Future extensibility: per-org prompt overrides from self DB (not built now, but `PromptService` architecture accommodates adding a DB-first lookup later).

### 3. AI Usage Tracking domain (customer path)

**Domain**: `src/ai_usage/` — full domain with auto-discovery, following `user/` domain pattern.

**Data model** (`ai_usage_log` table):

| Field | Type | Purpose |
|-------|------|---------|
| id | BigInteger PK | High-volume table |
| org_id | Integer, indexed | Organization identifier (customer query key) |
| agent_name | String(100), indexed | Which AI feature (classification, chat, ...) |
| model | String(100) | LLM model name |
| input_tokens | Integer | Input token count |
| output_tokens | Integer | Output token count |
| total_tokens | Integer | Total token count |
| estimated_cost_usd | Float | Estimated cost (USD) |
| status | String(20) | success / error / timeout |
| request_summary | Text, nullable | Request summary (no sensitive data) |
| error_message | String(500), nullable | Error details |
| duration_ms | Integer, nullable | Response latency |
| created_at | DateTime, server_default | Timestamp |

**API endpoints**:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/usage` | Per-org call history (filtered, paginated) |
| GET | `/v1/usage/summary` | Per-org aggregation (tokens, cost totals) |
| GET | `/v1/usage/{id}` | Single record detail |

**Usage recording mechanism** (`src/_core/common/usage_tracker.py`):
```python
async with track_agent_usage(ai_usage_service, org_id=1, agent_name="chat") as tracker:
    result = await agent.run("Hello", deps=deps)
    tracker.set_result(result)
```

Records `result.usage()` to self DB after each agent call. DB write failure is logged but does not affect the main agent execution.

**Admin dashboard**: Standard `BaseAdminPage` pattern for ops team monitoring (per-org cost comparison, usage trends).

### 4. Optional infrastructure pattern

Both Langfuse and AI Usage follow the project's optional infrastructure convention:

| Component | Toggle | Graceful degradation |
|-----------|--------|---------------------|
| Langfuse | `LANGFUSE_ENABLED=false` | No tracing, agents work normally, prompts use hardcoded defaults |
| AI Usage | Domain auto-discovered when present | Without `ai_usage` domain, `track_agent_usage` is simply not called |

### 5. OTEL as the abstraction boundary

PydanticAI emits OTEL-standard spans. The project configures an OTEL exporter targeting Langfuse. If the team later needs to switch to Phoenix, Jaeger, or Datadog, only the exporter configuration changes — no agent code modifications.

## Rationale

### Why dual-path instead of single-source?

| Concern | Langfuse path | Self DB path |
|---------|---------------|--------------|
| Data ownership | Langfuse controls schema/retention | Project controls everything |
| Audience | Ops team (internal) | Customers (external) |
| Data granularity | Full spans, step I/O | Summary (tokens, cost, status) |
| Availability SLA | Langfuse outage = no tracing (acceptable) | DB outage = no billing (unacceptable) |
| Query pattern | Complex traces, span filtering | Simple aggregation by org_id + date |

The two paths serve fundamentally different audiences with different data needs and different availability requirements. Merging them into one system forces compromises on both sides.

### Cost estimation approach

`estimated_cost_usd` is computed from model-specific token pricing tables (`_MODEL_COSTS` dict) at write time. This is an estimate — actual provider billing may differ slightly. For customer-facing display, recommend showing "X tokens at $Y/1K tokens" with the estimated total as a reference, not as an invoice amount.

## Trade-offs Accepted

- **Two systems to operate**: Langfuse self-hosted (6 Docker services) + project database. The Langfuse stack is opt-in and separate from the base dev environment (`docker-compose.langfuse.yml`), so developers who don't need tracing don't pay the startup cost.
- **Dual data recording**: Each agent call writes to both OTEL (automatic via instrumentation) and self DB (explicit via `track_agent_usage`). The OTEL path is fire-and-forget; the DB path is a single INSERT. Neither meaningfully impacts agent call latency.
- **Langfuse as a dependency for ops features**: If Langfuse is discontinued, the project loses tracing UI and prompt management. Mitigation: OTEL standard means the tracing data format is portable. Prompt management could be rebuilt or migrated to another tool. Customer-facing features are unaffected.

## Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
