> Historical per-issue file map from `docs/ai/shared/ai-infrastructure-overview.md` at cd5e6b5.
> Paths and statuses below record the original snapshot, not current recommendations.

## File Map by Issue

### Issue #15: PydanticAI Core (COMPLETED)

**Modified**:
- `src/_core/config.py` — LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BEDROCK_* fields + validation
- `src/_core/infrastructure/di/core_container.py` — `llm_config` Singleton provider
- `pyproject.toml` — `pydantic-ai` optional dependency group
- `_env/local.env.example` — LLM environment variables

**New**:
- `src/_core/domain/value_objects/llm_config.py` — `LLMConfig` frozen dataclass
- `src/_core/infrastructure/llm/exceptions.py` — `LLMException` hierarchy. **Removed in #331**: it had become a pure re-export facade that nothing imported through; the hierarchy itself lives at `src/_core/exceptions/llm_exceptions.py`
- `src/classification/` — Prototype AI domain (full domain scaffold)
- `docs/history/037-pydanticai-agent-integration.md`
- `docs/history/archive/038-llm-observability-dual-path.md` ← superseded by ADR 046

### Issue #74-A / #136: OTEL Core Setup (SHIPPED — PR #141)

**Modified**:
- `src/_core/config.py` — `otel_enabled`, `otel_exporter_otlp_endpoint` fields + partial-config validator
- `src/_apps/server/bootstrap.py` — `maybe_configure_otel(settings, service_name)` call
- `src/_apps/worker/bootstrap.py` — `maybe_configure_otel(settings, service_name)` call
- `pyproject.toml` — `otel` optional extra (`opentelemetry-api/sdk/exporter-otlp-proto-grpc >=1.40.0`)

**New**:
- `src/_core/infrastructure/observability/otel_setup.py` — `configure_otel(settings, service_name)` + `Agent.instrument_all()`
- `_env/local.env.example` + `_env/quickstart.env.example` — `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`
- `docs/operations/observability-otel.md` — Jaeger/Tempo/Phoenix quickstart + HTTP exporter swap

### Issue #74-B / #137: Langfuse Opt-in Recipe (SHIPPED — PR #142)

**New**:
- `docker-compose.langfuse.yml` — Langfuse stack (PG:5433, ClickHouse, Redis:6380, MinIO:9090, web:3000)
- `Makefile` — `observability-langfuse` target
- `docs/operations/observability-langfuse.md` — OTLP endpoint config + note: prompt linking requires Langfuse SDK in addition to OTLP

### Issue #75: AI Usage Tracking Domain (SHIPPED — PR #149)

**New**:
- `src/ai_usage/` — Full domain (auto-discovered):
  - `domain/dtos/ai_usage_dto.py` — AiUsageDTO
  - `domain/protocols/ai_usage_repository_protocol.py` — Extended with aggregate queries
  - `domain/services/ai_usage_service.py` — BaseService + custom summary/org queries
  - `infrastructure/database/models/ai_usage_model.py` — ai_usage_log table (nullable prompt ref columns, no FK)
  - `interface/server/routers/ai_usage_router.py` — GET /v1/usage, /usage/summary, /usage/{id}
  - `interface/admin/` — BaseAdminPage config + pages
- `src/_core/common/usage_tracker.py` — `track_agent_usage` async context manager
- `src/_core/domain/value_objects/prompt_snapshot.py` — `PromptSnapshot` Pydantic ValueObject
- Alembic migration for `ai_usage_log` table (with nullable prompt_name/version/source/external_prompt_ref)

**ai_usage_log schema changes vs ADR 038**:

| ADR 038 (removed) | ADR 046 (replaced with) | Reason |
|-------------------|-------------------------|--------|
| `prompt_id` FK | `prompt_name String(200) nullable` | No FK lock-in before prompt domain exists |
| — | `prompt_version String(50) nullable` | Langfuse-compatible label string (not integer) |
| — | `prompt_source String(20) nullable` | `"inline"` / `"langfuse"` / `"self"` / None |
| — | `external_prompt_ref String(500) nullable` | Langfuse prompt UUID or other external ref |

### Issue #97: simple-chatbot Example (OPEN, depends on #75 — now shipped)

- Inline `SYSTEM_PROMPT` constant — no prompt domain dependency
- `tokens_used` in response for educational purposes
- Comment: "Production usage tracking: see ai_usage domain (#75)"


## Original sentences corrected during the move

The following source statements are retained as historical evidence; current
source links and corrected prose take precedence.

2. **No providers.Selector for LLM** — PydanticAI handles model switching internally via `model="provider:model-name"` string.
4. **Hybrid DI** — dependency-injector for singletons (LLMConfig, database) + PydanticAI RunContext for per-request data (org_id, user_id).
| Lazy import for optional extras | OpenAI embedding client | `src/_core/infrastructure/embedding/openai_embedding_client.py` |
| Bootstrap conditional init | `_maybe_bootstrap_admin()` | `src/_apps/server/bootstrap.py` |
