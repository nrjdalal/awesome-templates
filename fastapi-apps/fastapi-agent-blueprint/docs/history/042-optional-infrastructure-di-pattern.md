# 042. Optional Infrastructure — Selector + Lazy Factory Pattern in CoreContainer

- Status: Accepted
- Date: 2026-04-21
- Related issue: #101 (Make CoreContainer infra truly optional)
- Precursor to: #82 (`fab init` CLI — unblocked by this ADR)
- Extends: [ADR 029](archive/029-broker-abstraction-selector.md) (broker Selector was the first instance of this pattern)

## Summary

Every non-DB infrastructure in `CoreContainer` (storage, DynamoDB, S3 Vectors, embedding, LLM) now follows a single pattern:

1. A module-scope `_<infra>_selector()` function reads `settings` at resolution time and returns `"enabled"` or `"disabled"`.
2. A module-scope `_build_<infra>()` factory does a **lazy import** of the real client inside its body, so removing an optional extra (`pydantic-ai-slim`, etc.) does not break app boot when the infra is not configured.
3. The container exposes the provider as `providers.Selector(_selector, enabled=..., disabled=...)`.
4. The **disabled branch** is per-infra:
   - Stub instance for infras where consumer domains need graceful degradation (`embedding_client` → `StubEmbedder`; `llm_model` → PydanticAI `TestModel` via `build_stub_llm_model`, or `None` if the `pydantic-ai` extra is not installed).
   - `providers.Object(None)` for data-storage infras (`storage_client`, `storage`, `dynamodb_client`, `s3vector_client`) where a fake client would mislead.

Broker continues to use its three-way Selector (`sqs` / `rabbitmq` / `inmemory`) as the original template.

## Background

Before this ADR, `core_container.py` imported every optional infra client at module top and instantiated each as an unconditional `providers.Singleton(...)`, regardless of whether the user had configured that infra. Two real-world failures followed:

1. **`pyproject.toml` optional extras were a lie.** Even though `pydantic-ai-slim`, `taskiq-aws`, `taskiq-aio-pika` were listed under `[project.optional-dependencies]`, uninstalling them caused `ImportError` at app boot. Users could not opt out.
2. **Disabled-but-instantiated dead clients.** `LLMConfig(model_name="")` and friends were constructed with empty credentials when `LLM_*` was unset. The first call down the chain (e.g. `Agent(model="")` inside `ClassificationService`) raised a deep PydanticAI error rather than a clear "this infra is not enabled" signal.

The broker already had the right shape (see [ADR 029](archive/029-broker-abstraction-selector.md)). This ADR generalises that shape to the remaining five optional infras and records the per-infra disabled-branch rule so future additions don't re-litigate.

`#82` (interactive `fab init` CLI) was blocked on this: a CLI that "removes DynamoDB" would otherwise have to physically rewrite `core_container.py`. After this ADR lands, the CLI becomes a thin `.env` scaffolder (or is unnecessary — see #82 re-evaluation).

## Decision

### 1. Pattern shape (all five infras)

```python
# module scope
def _dynamodb_selector() -> str:
    return "enabled" if settings.dynamodb_access_key else "disabled"


def _build_dynamodb_client(access_key, secret_access_key, region_name, endpoint_url):
    # Lazy import — removing the matching optional extra (boto3 in this case,
    # pydantic-ai-slim for llm/embedding) does not break import of this module.
    from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_client import (
        DynamoDBClient,
    )
    return DynamoDBClient(
        access_key=access_key or "",
        secret_access_key=secret_access_key or "",
        region_name=region_name or "ap-northeast-2",
        endpoint_url=endpoint_url,
    )


# in CoreContainer class body
dynamodb_client = providers.Selector(
    _dynamodb_selector,
    enabled=providers.Singleton(
        _build_dynamodb_client,
        access_key=settings.dynamodb_access_key,
        secret_access_key=settings.dynamodb_secret_key,
        region_name=settings.dynamodb_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    ),
    disabled=providers.Object(None),
)
```

Key discipline:

- Selector functions read `settings` **at call time**, not at import time, so tests can monkeypatch a settings field to flip the branch.
- Factory imports live **inside the function body**, never at module top. `try/except ImportError` with an install hint is used only where the dependency itself might be missing (`pydantic-ai` for embedding/LLM — see `broker.py` for the original template).
- Factory signatures type settings fields as `str | None` (their real type) and use `value or default` fallbacks, since pyright cannot see the Selector invariant that guarantees non-None in the enabled branch.

### 2. Per-infra disabled-branch strategy

| Infra | Disabled branch | Reason |
|---|---|---|
| `storage_client`, `storage` | `providers.Object(None)` | No current consumer; fake storage would make saved uploads silently vanish. Future consumers must guard or declare storage mandatory. |
| `dynamodb_client` | `providers.Object(None)` | A fake DynamoDB client would accept writes that never persist; user debugging would blame the wrong layer. |
| `s3vector_client` | `providers.Object(None)` | Same as DynamoDB. The `docs` domain already falls back to in-memory via its own `chunk_vector_store` selector, so the S3 client genuinely goes unused when disabled. |
| `embedding_client` | `Singleton(StubEmbedder, dimension=...)` | Consumer domains (`docs`) need to answer questions even without an embedding provider. `StubEmbedder` already exists (keyword bag-of-words). |
| `llm_model` | `Singleton(build_stub_llm_model)` — returns PydanticAI `TestModel` when `pydantic-ai` is installed, otherwise `None` | `classification` / `docs` need graceful degradation. The `None` fallback preserves #101's "uninstall optional extra → still boots" acceptance criterion: when `pydantic-ai` is absent, the stub itself cannot exist either, and the only domain that could have used it (`ClassificationService`) is already gated by its own `pydantic-ai` ImportError at construction time. |

The rule of thumb: **stub when the disabled path must still serve traffic; None when the disabled path should never be touched.** Data stores fall in the second bucket because a fake that accepts writes is worse than a `NoneType` error at the call site.

### 3. Drop `llm_config` / `embedding_config` as standalone providers

Previously each infra exposed both a config VO (`LLMConfig` / `EmbeddingConfig`) and the client it configured. Nothing outside `core_container.py` referenced the config providers. The new build functions construct the VO locally and return the client directly, removing two unused entries from the container's public surface. The VO classes themselves are unchanged and still used inside the infra layer.

### 4. Selector functions read computed Settings properties

`settings.llm_model_name` and `settings.embedding_model_name` are `str | None` computed properties that already return `None` when provider + model are not both set. Selectors use these (not raw `llm_provider` fields) as the single source of truth for "is this infra enabled?", matching the semantics already established by the `docs` domain's embedder selector.

### 5. Graceful degradation may layer — Core stub + Domain Selector can coexist

Once CoreContainer's `embedding_client` returns `StubEmbedder` on disable, the domain-level Selector in [`docs_container.py:59-63`](../../src/docs/infrastructure/di/docs_container.py#L59-L63) is, strictly speaking, redundant — `core_container.embedding_client` already resolves to `StubEmbedder` when the embedding group is unset. The same applies to `answer_agent` once #101 Part B lands.

**Decision: keep the domain-level Selector in `docs` anyway.** Two reasons:

1. **Self-contained reference pattern.** `docs_container.py` is cited in both the [`/new-domain` skill](../../.claude/skills/new-domain/SKILL.md) and [AGENTS.md's Optional Infrastructure Toggles section](../../AGENTS.md) as the canonical template for domain-level Selector wiring. Stripping it out would force future contributors to infer the pattern from absence, which is fragile.
2. **Core fallback is not guaranteed to exist for every optional infra.** Storage, DynamoDB, and S3 Vectors deliberately return `None` at the Core layer (no stub — fake data stores mislead, see Decision 2). Domains that consume those infras must either declare them mandatory or add a domain-level guard. Keeping the `docs` pattern visible means the guard shape is obvious when the next contributor faces a `None`-returning core provider.

**Corollary for future domains:** a domain that consumes an optional infra SHOULD add a domain-level Selector if (a) graceful degradation matters to its workflow AND (b) the core layer returns `None` (no stub). If the core layer already stubs (embedding, LLM-after-Part-B), a second-level Selector is optional — add it for readability, skip it for brevity. The `/new-domain` skill generates the full pattern by default; trim as needed.

## Alternatives Considered

### A.1 — `providers.Selector` + `providers.Object(None)` with top-level imports kept

Replace the unconditional `providers.Singleton` with a Selector, but keep the `from ... import DynamoDBClient` at module top. Rejected: acceptance criterion for #101 was "boot with optional extras uninstalled → no ImportError". Top-level imports survive that uninstall and violate it. This is the minimum-viable rewrite and it does not satisfy the goal.

### A.2 — Lazy factory without Selector (bare `providers.Singleton(_factory)` that returns `None` when disabled)

```python
def _build_dynamodb_client():
    if not settings.dynamodb_access_key:
        return None
    from ... import DynamoDBClient
    return DynamoDBClient(...)

dynamodb_client = providers.Singleton(_build_dynamodb_client)
```

Rejected: dependency-injector introspection (`.provided`, `.override`, `.reset`) becomes awkward when the Singleton can return `None` — `.provided.<attr>` on `None` fails silently. Selector encodes the branch choice in the DI graph, which is what downstream overrides expect. Also, having the disabled path be a `providers.Object(None)` (not a Singleton call) means zero allocation — the `None` literal is returned directly.

### A.3 — Selector + lazy factory (chosen)

Combines (1) lazy import inside the factory with (2) Selector for branch encoding. Satisfies acceptance criterion and keeps DI introspection honest. Mirrors the existing `broker` pattern (ADR 029) and the lazy imports already present in `build_llm_model` / `broker.create_sqs_broker`.

### B — Single StubClient class per infra (`StubDynamoDBClient`, `StubS3VectorClient`)

Considered and rejected for data stores. Stubs for "write-then-read" data stores must decide whether to persist in memory or to silently drop — both mislead. A user who writes a row and queries it back, receiving it intact, will not suspect that real DynamoDB was never touched. `None` plus an explicit guard at the call site ("this domain requires DYNAMODB to be configured") is honest. Stubs make sense only where the consumer's workflow is still meaningful without a real backend — currently that's embedding (similarity over random vectors approximates keyword overlap) and LLM (templated response from retrieved chunks).

## Testing Strategy

The two new test files establish a reusable pattern that every future optional-infra addition should follow.

### Selector unit tests — monkeypatch + call-time read

Selectors read `settings` at call time, so flipping a branch is a single `monkeypatch.setattr` call:

```python
def test_dynamodb_disabled_when_access_key_unset(monkeypatch):
    monkeypatch.setattr(settings, "dynamodb_access_key", None)
    assert _dynamodb_selector() == "disabled"

def test_dynamodb_enabled_when_access_key_set(monkeypatch):
    monkeypatch.setattr(settings, "dynamodb_access_key", "AKIA_TEST")
    assert _dynamodb_selector() == "enabled"
```

This works because Settings is a non-frozen pydantic-settings model and each selector does a live attribute read per invocation. See [`tests/unit/_core/infrastructure/di/test_core_container_selectors.py`](../../tests/unit/_core/infrastructure/di/test_core_container_selectors.py) (13 tests, one class per infra).

### Boot regression — `clean_optional_env` fixture + container resolution

The acceptance criterion is "app boots with only `DATABASE_ENGINE` set". The [`clean_optional_env` fixture](../../tests/integration/_core/infrastructure/test_optional_infra.py) monkeypatches every optional settings field to its disabled value, then asserts the documented disabled-branch behavior:

```python
@pytest.fixture
def clean_optional_env(monkeypatch):
    for field in ("storage_type", "dynamodb_access_key", "s3vectors_access_key",
                  "embedding_provider", "embedding_model", "llm_provider", "llm_model"):
        monkeypatch.setattr(settings, field, None)
    monkeypatch.setattr(settings, "broker_type", None)

def test_dynamodb_client_returns_none(clean_optional_env):
    container = CoreContainer()
    assert container.dynamodb_client() is None

def test_embedding_client_returns_stub(clean_optional_env):
    assert isinstance(CoreContainer().embedding_client(), StubEmbedder)
```

### App-boot smoke — real `bootstrap_app` with clean env

A separate smoke test imports the full FastAPI app under `clean_optional_env` to catch the failure mode where a domain container or bootstrap hook eagerly imports an optional dep. If adding a new optional infra, extend this test's assertions to cover your provider.

### Why not test the `enabled` branch exhaustively?

`providers.Singleton(_build_<infra>, kwarg=settings.<field>)` captures its kwargs at class-definition time. Monkeypatching `settings` after the container class has been imported does not re-evaluate those kwargs. Testing "enabled produces a real client" would require reloading the module — brittle and slow. Build functions are instead tested in isolation (`_build_dynamodb_client(access_key="fake", ...)`), and the Selector's branch-choice logic is validated separately. Together they cover the real failure modes without module-reload gymnastics.

## Consequences

- **Boot-time guarantee:** with only `DATABASE_ENGINE=sqlite` set and all optional extras uninstalled (`pydantic-ai-slim`, `taskiq-aws`, `taskiq-aio-pika`), the app imports cleanly and `/docs` serves OpenAPI. Regression-guarded by `tests/integration/test_optional_infra.py`.
- **Domain degradation is localised.** `docs` already degrades via its domain-level Selector (kept in place as a self-contained example). `classification` now degrades the same way: when `LLM_*` is unset, CoreContainer returns a PydanticAI `TestModel` via `build_stub_llm_model`, which `ClassificationService` accepts as its `Agent(model=...)` argument and uses to return a schema-valid placeholder `ClassificationDTO`. If `pydantic-ai` itself is uninstalled, the stub cannot be constructed and `llm_model()` falls back to `None` — `ClassificationService.__init__` then raises its own "install pydantic-ai" ImportError, which is the correct signal for that scenario.
- **Every new optional infra uses this pattern by default.** The `/new-domain` skill templates (`/claude/skills/new-domain/`, `.codex/new-domain`) will be updated in #101 Part B so scaffolded domains ship with Selector + stub where they declare an LLM or Embedding dependency.
- **`#82` unblocked.** Any future CLI that offers "remove DynamoDB" only needs to unset `DYNAMODB_*` in the scaffolded `.env`; no source rewriting. `#82` scope may shrink to "thin `.env` scaffolder" or be closed entirely — decision deferred to post-merge re-evaluation.
- **`pyproject.toml` cleanup (nicegui, boto3 → optional extras) is out of scope** for this ADR. Filed as a separate follow-up issue; it is a user-facing UX change (admin dashboard mount decision, aws-installation matrix) and deserves its own design pass.

> **AGENTS.md alias note (PR-B.4a):** The AGENTS.md section for this pattern was renamed from `§ Optional Infrastructure` to `§ Optional Infrastructure Toggles` for clarity. Cross-references should use the new heading name.
