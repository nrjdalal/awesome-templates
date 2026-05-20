# ADR 043 — Responsibility-Driven Refactor

**Status:** Accepted  
**Date:** 2026-04-22  
**Background:** Triggered by a routine review of `_build_*` factory placement in `core_container.py`; expanded into a full codebase audit finding 12 responsibility confusion points.

---

## Context

The project targets OSS blueprint quality: example code doubles as learning material. Therefore, layer responsibilities must be immediately readable from the code structure and must follow Python / FastAPI / `dependency_injector` / NiceGUI / PydanticAI idioms. Three categories of problems were identified:

1. **Misplaced code** — domain services importing provider SDKs (`pydantic_ai`) directly; exception mapping inside domain.
2. **Dead code** — unused return values, dead parameters, duplicate files.
3. **Missing contracts** — `Any`-typed service providers, no typed Protocol for classifier.

---

## Decisions

### Decision 1: Error Translation Belongs in Infrastructure

**Before:** Domain services had `try/except Exception as exc: map_llm_error(exc)` blocks, and `map_llm_error` lived in `_core/common/llm_utils.py`.  
**After:** Domain services let exceptions propagate. `src/_core/infrastructure/llm/error_mapper.py` is the canonical ACL. FastAPI's `generic_exception_handler` calls `try_map_llm_error` before falling through to 500.

**Why:** `map_llm_error` knew provider SDK class names — that's infrastructure knowledge. Domain services had no business importing it. The "all exceptions become LLM errors" problem (generic exceptions like DB errors being silently misclassified) is also fixed: `try_map_llm_error` returns `None` for unknown exceptions, letting them fall through to the generic 500 handler.

### Decision 2: Classifier Protocol + Adapter Pattern (ADR 040 Generalization)

**Before:** `ClassificationService.__init__` created `pydantic_ai.Agent` directly, violating the "no SDK imports from domain" rule.  
**After:** `ClassifierProtocol` (in `classification/domain/protocols/`) defines the contract. `PydanticAIClassifier` and `StubClassifier` (in `classification/infrastructure/classifier/`) implement it. `ClassificationContainer` uses `providers.Selector` to branch.

**Why:** Generalizes ADR 040 (RAG as reusable pattern) to all AI features. Every AI capability now follows: Domain Protocol → Infra Adapter → Selector. The classification domain can now boot without `LLM_*` env vars.

### Decision 3: Provider Helpers Centralized

**Before:** `parse_model_name` (prefix splitting) and `build_*_provider` repeated across `model_factory.py` and `pydantic_ai_embedding_adapter.py`.  
**After:** `src/_core/infrastructure/ai/providers.py` is the single home for all PydanticAI provider construction helpers.

### Decision 4: Admin Hybrid Approach

**Before:** `_resolve_query_service()` workaround in `docs_page.py` created a second container to get `docs_query_service`.  
**After:** `BaseAdminPage` gains `extra_services_config: dict[str, str]` (config-time declaration) and `_extra_services: dict[str, Callable]` (bootstrap-wired). `AdminCrudServiceProtocol` types the main service provider. Full decomposition of `BaseAdminPage` (Config/Renderer/Orchestrator split) is deferred — the Template Method pattern remains; dashboard pages are separate `@ui.page` handlers that don't need it.

---

## Tradeoffs

| Decision | Gained | Cost |
|----------|--------|------|
| Error translation to infra | Clean domain services; correct exception classification | Domain tests now test raw exception propagation (simpler, actually) |
| Classifier Protocol | ADR 040 symmetry; quickstart graceful degradation | 3 new files per AI feature |
| Provider helpers | Single place to add new providers | Extra indirection layer |
| Admin hybrid | Removes workaround, adds typed contract | `extra_services_config` is a new convention to learn |

---

## Consequences

- `rg "from pydantic_ai" src/` → only `_core/infrastructure/` and optional-extra guards
- `rg "map_llm_error" src/` → only `_core/infrastructure/llm/error_mapper.py` and exception handlers
- `rg "class.*Entity" src/` → empty (invariant preserved)
- Bootstrap: both server and worker bootstrap functions now read as an 8-step conductor with named private functions, matching the Makefile mental model

---

## Post-Decision Update

*To be filled in after 3–4 weeks of real usage.*
