# FastAPI Agent Blueprint — Shared Collaboration Rules

This file is the canonical source for project-shared AI collaboration rules.
Tool-specific harness files must reference this document instead of duplicating its contents.

## Tool-Specific Harnesses

- `CLAUDE.md` — Claude-specific hooks, plugins, slash skills, and tool usage guidance
- `.codex/config.toml` — Codex CLI project settings, profiles, feature flags, and MCP configuration
- `.codex/hooks.json` — Codex command-hook configuration
- `.agents/skills/` — repo-local Codex workflow skills
- `docs/ai/shared/` — shared workflow references consumed by both Claude and Codex
- `.mcp.json` — Claude-only MCP server configuration

### Process Governor Reference Documents

Issue #117 introduced a hybrid local process governor. The four documents below, indexed from [ADR 045](docs/history/045-hybrid-harness-target-architecture.md), define how default coding work is routed:

- [`docs/history/045-hybrid-harness-target-architecture.md`](docs/history/045-hybrid-harness-target-architecture.md) — top-level decisions + design-question resolutions
- [`docs/ai/shared/harness-asset-matrix.md`](docs/ai/shared/harness-asset-matrix.md) — living inventory of every harness asset and its bucket (Keep / Replace / Overlay / Drop)
- [`docs/ai/shared/target-operating-model.md`](docs/ai/shared/target-operating-model.md) — the target workflow, exception model, Claude/Codex alignment, and sample-workflow traces
- [`docs/ai/shared/migration-strategy.md`](docs/ai/shared/migration-strategy.md) — phased migration plan, rollback rules, and the asset-move ordering

### Hybrid Harness v1 status

- **Phase 5 shipped** (#124 — 2026-05-03): governor *policy* consolidated into [`.agents/shared/governor/`](.agents/shared/governor/); Claude / Codex hook scripts are thin shims enforced by `tests/unit/agents_shared/test_governor_boundary.py`; future governor changes must go into the shared package, not per-tool inline copies.
- **[ADR 047](docs/history/047-governor-review-provenance-consolidation.md) / [ADR 048](docs/history/048-independent-review-generalization.md) steady state**: independent review provenance lives in the PR description `## Governor Footer` block (CI-linted); durable governance constraints promoted to ADR Consequences (`ADR{NNN}-G{N}` slots); `governor-review-log/` archive frozen as closed historical record.
- **Permanent governance model**: escape-token vocabulary, dual-tool adapters, and scope-of-impact-driven independent review remain permanent (target-operating-model §3 / §7).

## Project Scale

This project is an AI Agent Backend Platform targeting enterprise-grade services with 10+ domains and 5+ team members.
All proposals and designs must consider scalability, maintainability, and team collaboration at this scale.

## Absolute Prohibitions

- No Infrastructure imports from the Domain layer
- No exposing Model objects outside the Repository
- No separate Mapper classes (inline conversion is sufficient)
- No Entity pattern — unified to DTO (background: [ADR 004](docs/history/004-dto-entity-responsibility.md))
- No modifying or deleting shared rule sources without cross-reference verification
  - Shared rule sources: `AGENTS.md`, `docs/ai/shared/`, `.claude/`, `.codex/`, and `.agents/`
  - Before changing them, verify no dependent tool configs or skills reference the changed content

Note: Domain → Interface **schema** imports (Request/Response types) are permitted.
When fields match, Request is passed directly to Service — creating a separate DTO is prohibited per ADR 004.

## Language Policy

Tier 1 paths are **English-only prose**. Korean prose is hard-blocked by the pre-commit hook (`tier1-language-policy`, invoking `tools/check_language_policy.py`).

### Tier 1 paths (canonical scope of `tools/check_language_policy.py::TIER1_GLOBS`)

- `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- `docs/ai/shared/**`, `docs/history/**`
- `.claude/rules/**`, `.claude/hooks/**`, `.claude/skills/**`
- `.codex/rules/**`, `.codex/hooks/**`, `.agents/**`
- `.github/pull_request_template.md`, `.github/workflows/**`

### Two narrowly-scoped exceptions

1. **Bilingual escape tokens** — `[trivial]/[자명]`, `[hotfix]/[긴급]`, `[exploration]/[탐색]` — scoped per-file via `tools/check_language_policy.py::TOKEN_LITERALS_BY_FILE`. Token literals and parser references are permitted; other Korean prose is not.
2. **Locale data files** — listed in `tools/check_language_policy.py::LOCALE_DATA_FILES` (currently `.agents/shared/governor/locale.py`). Korean permitted only in language-mapping values; comments, docstrings, and English table must remain ASCII. Adding a new locale file requires updating `LOCALE_DATA_FILES` and adding a regression test.

### AI-when-editing rule

All new prose, comments, log strings, and terminal output in Tier 1 paths **must be English** regardless of the conversational language. If instructed to add non-English content, refuse and translate; cite this section. Hidden Korean rationale (HTML comments, backtick-quoted attributes) also violates policy intent even if not currently detected.

Enforcement: (1) pre-commit `tier1-language-policy`; (2) CI `architecture` job; (3) `tests/unit/agents_shared/test_language_policy.py`; (4) review skills Phase 0 sync-check.

## Default Coding Flow

> Source of truth: [ADR 045](docs/history/045-hybrid-harness-target-architecture.md) + [`docs/ai/shared/target-operating-model.md`](docs/ai/shared/target-operating-model.md). Edit those first, then sync this section via `/sync-guidelines`.

Coding work proceeds through seven steps by default. Mandatory-by-default steps must be either performed or explicitly skipped via an escape token (see below). Other steps are conditional.

```
problem framing → approach options → plan → implement
                → verify → self-review → completion gate
```

Mandatory-by-default for implementation-class work: `framing`, `plan`, `verify`, `self-review`.
Conditionally mandatory (architecture commitment present): `approach options`.
Mandatory-by-default; non-blocking reminder via Phase 4 hook + Governor Footer Lint CI: `completion gate`.

### Precedence

The Default Coding Flow ranks **below** the following four layers, in this order:

1. Active sandbox / approval policy / explicit user scope (e.g. read-only, review-only)
2. `.codex/rules/*` prefix rules (`forbidden` / `prompt`)
3. Safety hooks (security checks, destructive-command guards)
4. `## Absolute Prohibitions` (this document)

Escape tokens never override any of these four layers; they only reduce process burden inside the Default Coding Flow itself.

### Exception Tokens

A prompt may opt out of mandatory-by-default steps by carrying a leading exception token on its first line. Tokens are recognised after NFKC normalisation, case-insensitive, only as the leading bracketed token followed by whitespace or end-of-line.

| Token (English) | Token (Korean) | Meaning |
|---|---|---|
| `[trivial]` | `[자명]` | Self-evident change (typo, comment, rename); skip framing / approach / plan |
| `[hotfix]` | `[긴급]` | Urgent fix; skip approach options; verify still required |
| `[exploration]` | `[탐색]` | Read-only investigation or spike; nothing produces a commit |

Recognition regex: `^\s*\[(trivial|hotfix|exploration|자명|긴급|탐색)\](?:\s|$)`.

> The bilingual entries above (`[자명]`, `[긴급]`, `[탐색]`) and the locale-data carve-out (§ Language Policy → Exemptions → `LOCALE_DATA_FILES`) are the two narrowly-scoped exceptions to § Language Policy. The bilingual entries are machine-parseable and pinned by the regex; the per-file allowlist in `tools/check_language_policy.py` keeps Korean token references scoped to the files that legitimately need them.

Use of an exception token carries a follow-up obligation: the next commit message must record the rationale (one line is enough).

Auto-escapes (no token required): `changed_files == 0`, *general* doc-only changes, comment-only changes.

> **Doc-only carve-out** (Pillar 3 / Codex review R8 — added to prevent governance loosening). The doc-only auto-escape applies only to **general docs** such as `README.md`, `CHANGELOG.md`, contributor guides, and `docs/` content that is not policy or harness governance. The auto-escape does **not** apply to any path classified under Tier A of [`docs/ai/shared/governor-paths.md`](docs/ai/shared/governor-paths.md). Such changes go through normal `framing` → `plan` → `verify` → `self-review` even though they look doc-only, because they redefine the rules of the system.

### Self-Review Step — Independent Review Trigger (Pillar 2)

`self-review` is mandatory by default. When the change touches any path classified under **Tier A or Tier B (or Tier C)** of [`docs/ai/shared/governor-paths.md`](docs/ai/shared/governor-paths.md) — and is not entirely covered by an exclusion in the same file — `self-review` must include an **independent review** as a mandatory sub-step.

**Independent review modes (one is sufficient; record the mode in the footer's `reviewer` field):**

| Mode | When to use | `reviewer` field value |
|---|---|---|
| `cross-tool` | Another AI tool (e.g. `codex exec --sandbox read-only "<review prompt>"`, escalating model/effort only when warranted) reads the change set | `codex-cli`, `claude-code`, or tool name |
| `self-structured` | Single-tool environment — apply the structured self-review checklist in `docs/ai/shared/skills/review-pr.md` § "Self-Structured Review Checklist"; include a checklist evidence summary (checked items and any deferred rationale) in the PR body | `self-structured` |
| `human` | A human reviewer (not the PR author) reviews the governor-changing surface | `human:<github-handle>` |

**Round cap guidance:** resolve each R-point within 2 rounds (initial + follow-up). If a third round is needed, treat it as a signal to split the PR. Each round is counted in the footer's `rounds` field.

- capture the resulting `Findings` / `Drift Candidates` / `Sync Required` / Final Verdict in the **PR description's `## Governor Footer` block** (post-ADR-047 — `tools/check_governor_footer.py --require-governor-footer` enforces presence + shape via the `Governor Footer Lint` CI workflow). Durable governance constraints derived from the review are added to the relevant ADR's Consequences section (e.g. ADR 047 §"Durable Governance Constraints (ADR047-G1 ~ ADR047-G27)"); durable domain invariants go to `project-dna.md` or the relevant domain doc;
- address surfaced R-points or explicitly defer with rationale (closure label vocabulary `Fixed` / `Deferred-with-rationale` / `Rejected` per AGENTS.md guard G — the linter parses the footer's `r-points-*` counts);
- the existing `docs/history/archive/governor-review-log/` directory is a **closed historical archive** for entries written before PR #158 (ADR 047) — see [`governor-review-log/README.md`](docs/history/archive/governor-review-log/README.md) for the alias map back to ADR 047 G-slots.

Non-governor-changing PRs are **exempt** from independent review (issue #117 Non-Goals: avoid heavy ceremony).

### Skill Mapping

Each step routes to one or more skills. The shared procedure for each skill (under [`docs/ai/shared/skills/`](docs/ai/shared/skills/)) carries a "Default Flow Position" section documenting which step(s) the skill participates in, and tool-specific wrappers (`.claude/skills/`, `.agents/skills/`) mirror the same position. See [`target-operating-model.md`](docs/ai/shared/target-operating-model.md) §1 for the canonical mapping.

### Claude / Codex Alignment

This document is canonical. Tool-specific enforcement adapters are defined per migration phase in [`migration-strategy.md`](docs/ai/shared/migration-strategy.md). In particular, Codex enforcement is built around prompt-time routing and changed-file completion checks, not Bash-only `PostToolUse` matchers — skill-body instructions alone are insufficient because Codex does not read a skill until it is invoked.

## Reasoning-Level Consistency Guards

> Canonical body: this AGENTS.md section (ADR047-G23). CLAUDE.md § Claude Collaboration Rules and `.codex/hooks/session-start.py` carry pointer cross-refs. When adding guards, extend AGENTS.md first and record a new `ADR{NNN}-G{N}` slot in the relevant ADR.

Applies to **every reasoning step** — conversation, cross-review, document generation — across all tools. Complements the PR-level governor; these guards address conversation-level miss patterns the file-level governor does not cover.

**Application order:** H (intent classification) → F (evidence verification) → [if challenged] I (self-licensing check) → [for review output] G (closure classification).

### F. Volatile Workspace Facts — Verify Before Consequential Assertion

Before making corrective claims, user-premise challenges, or exact line/path/PR-number/test-count assertions: **re-verify with tools** (`git status`, `gh pr view`, `Read`, `find`). System-prompt snapshots and prior-round summaries are evidence pointers, not current facts. Does not fire on exploratory questions — only on consequential assertions.

### G. Cross-Review Results — Closure Classification

Every R-point must be closed as one of: **Fixed** / **Explicitly deferred with rationale** / **Rejected as non-issue**. "Preserve / maintain / leave as-is" are **not** closure categories. Record in `r-points-fixed` / `r-points-deferred` / `r-points-rejected` footer fields.

### H. Effect vs Process Question Discrimination

Classify each question: **effect** (is it working? what's the result?) vs **process** (what should we do? what's next?). Effect questions must be answered with evidence, not process content. Mixed questions: effect-first with evidence, then process options separately. In multi-round conversations, restate the original question before proposing process changes.

**Review-skill enforcement:** `/review-pr`, `/review-architecture`, `/security-review` require a mandatory `Effect Answer` field (1–3 sentence evidence-based summary of what the change *actually* does) before `Findings`. Skipping this field violates Guard H. See `docs/ai/shared/skills/review-pr.md` § Review Contract.

### I. Self-Licensing Detection — Sanity Check Before Defending a Challenged Conclusion

Fires when the user pushes back on a stated conclusion (correction, challenge, or evidence request). Before defending, explicitly check: (1) Was the premise stale or incorrect? (2) Is the reasoning circular? (3) Could the user's intuition be a real domain signal? State the check result first, then proceed. General follow-up questions do not fire this guard.

## Layer Architecture (3-Tier Hybrid)

- Default: Router → Service (extends `BaseService`) → Repository (extends `BaseRepository`)
- DynamoDB domain: Router → Service (extends `BaseDynamoService`) → Repository (extends `BaseDynamoRepository`)
- Complex logic: Router → UseCase (manually written) → Service → Repository
- UseCase criteria: multiple Service composition, cross-transaction boundaries, or other orchestration complexity
- When in doubt: start without UseCase, add it when complexity grows

## Responsibility Matrix

Each concern has exactly one home. Do not duplicate or split these across layers.

| Concern | Location | Rule |
|---------|----------|------|
| Pure business logic | `{domain}/domain/services/` | No SDK imports, no infra |
| Domain contracts (AI) | `{domain}/domain/protocols/` or `_core/domain/protocols/` | `typing.Protocol` + `@runtime_checkable` |
| Provider SDK calls | `_core/infrastructure/{llm,embedding,classifier,rag}/` | PydanticAI, boto3 SDK isolated here |
| Provider SDK exception translation | `_core/infrastructure/llm/error_mapper.py` | ACL — infra only, never domain |
| Provider helpers | `_core/infrastructure/ai/providers.py` | `parse_model_name`, `build_*_provider` |
| DI container, lazy factories | `{domain}/infrastructure/di/{domain}_container.py` | `_build_*` factories belong here |
| Bootstrap orchestration | `_apps/{server,worker}/bootstrap.py` | Private `_configure_*`, `_install_*`, `_setup_*` functions |
| Admin service contract | `_core/domain/protocols/admin_service_protocol.py` | `AdminCrudServiceProtocol` |
| Test DI overrides | `_apps/server/testing.py` | Public `override_database` / `reset_database_override` |

## Error Translation

Provider SDK exceptions (PydanticAI, boto3, openai, anthropic) must be translated to domain LLM exceptions in the **infrastructure layer**, never inside domain services.

- **Domain services**: let exceptions propagate — no `try/except` around provider calls
- **Infrastructure adapters** (e.g. `PydanticAIEmbeddingAdapter`): catch SDK exceptions and call `map_llm_error(exc)` (NoReturn — always raises a domain exception)
- **FastAPI `generic_exception_handler`**: catches all unhandled exceptions, calls `try_map_llm_error(exc)` (returns `Optional`) before falling through to 500
- **ACL module**: `src/_core/infrastructure/llm/error_mapper.py` — the only place that knows provider SDK class names

```
Provider SDK exception
  → propagates through domain service untouched
  → caught by FastAPI generic_exception_handler
  → try_map_llm_error(exc) → LLMException (mapped HTTP status)
  OR → 500 Internal Server Error (unrecognised exception)
```

## Optional AI Infra: Protocol + Selector Pattern

All AI features (LLM classification, RAG answering, embedding) follow the same Protocol + Infra Adapter + Selector pattern. Background: [ADR 040](docs/history/040-rag-as-reusable-pattern.md) + [ADR 042](docs/history/042-optional-infrastructure-di-pattern.md).

**Pattern:**
1. `{domain}/domain/protocols/{feature}_protocol.py` — `typing.Protocol` contract
2. `_core/infrastructure/{feature}/pydantic_ai_{feature}.py` — real adapter (or domain-specific if DTO coupling is tight)
3. `_core/infrastructure/{feature}/stub_{feature}.py` — deterministic stub for quickstart/no-LLM
4. Domain container uses `providers.Selector(real=..., stub=...)` to branch

**Reference implementations:**
- RAG: `AnswerAgentProtocol` → `PydanticAIAnswerAgent` / `StubAnswerAgent` (in `_core/infrastructure/rag/`)
- Classifier: `ClassifierProtocol` → `PydanticAIClassifier` / `StubClassifier` (in `classification/infrastructure/classifier/`)

**Selector selector function convention:** `def _classifier_selector() -> str: return "real" if settings.llm_model_name else "stub"`

Deeper non-canonical reference: [docs/ai/shared/ai-infrastructure-overview.md](docs/ai/shared/ai-infrastructure-overview.md) — current status of AI infra issues (#74/#75/#97) and OTEL backend comparison.

## Admin Service Contract

Admin pages consume domain services through `AdminCrudServiceProtocol` (`_core/domain/protocols/admin_service_protocol.py`). Any `BaseService` subclass satisfies this protocol automatically.

- `_service_provider: Callable[[], AdminCrudServiceProtocol]` — main CRUD service, wired by bootstrap
- `extra_services_config: dict[str, str]` — declare additional services by alias → container attr name
- `_get_extra_service(alias: str)` — resolve and call an extra service (e.g. `"query"` → `docs_query_service`)

**Example** (docs domain needing a query service alongside the main CRUD service):
```python
docs_admin_page = BaseAdminPage(
    domain_name="docs",
    extra_services_config={"query": "docs_query_service"},
)
# In page handler:
service = docs_admin_page._get_extra_service("query")
```

## Optional Infrastructure Toggles

Every non-DB infra in `CoreContainer` is optional — toggle via env vars, no code change. When a group is disabled, the provider returns a stub (where graceful degradation matters) or `None` (for data stores). Background: [ADR 042](docs/history/042-optional-infrastructure-di-pattern.md).

| Infra | Enable flag | Disabled behavior |
|---|---|---|
| Storage (S3 / MinIO) | `STORAGE_TYPE=s3` or `minio` | `storage_client()` / `storage()` return `None` |
| DynamoDB | `DYNAMODB_ACCESS_KEY` set | `dynamodb_client()` returns `None` |
| S3 Vectors | `S3VECTORS_ACCESS_KEY` set | `s3vector_client()` returns `None` |
| Embedding | `EMBEDDING_PROVIDER` + `EMBEDDING_MODEL` both set | `embedding_client()` returns `StubEmbedder` (keyword bag-of-words) |
| LLM | `LLM_PROVIDER` + `LLM_MODEL` both set | `llm_model()` returns PydanticAI `TestModel` via `build_stub_llm_model` when `pydantic-ai` is installed, `None` otherwise |
| Broker | `BROKER_TYPE=sqs` / `rabbitmq` / `inmemory` | Defaults to `inmemory` — no external broker required |

**Consumer rule:** data-store clients (`None`-returning) require an explicit guard at the call site when your domain needs them; stub-returning infras just work (but signal "stub" via startup warning logs). Use `providers.Selector` in your domain container to branch between real and stub paths if needed — `src/docs/infrastructure/di/docs_container.py` is the reference pattern.

**Package-level extras:** optional runtime infras are also gated at the `pyproject.toml` level. Install only what you need — `uv sync --extra admin` for the NiceGUI dashboard, `--extra aws` for object storage / DynamoDB / S3 Vectors (boto3 + aioboto3 + type stubs), `--extra sqs` / `--extra rabbitmq` for those broker backends, `--extra pydantic-ai` for LLM / Embedding, etc. When an extra is absent, the matching bootstrap path silently skips and the server continues to boot — the 4 AWS client modules (`ObjectStorageClient`, `ObjectStorage`, `DynamoDBClient`, `S3VectorClient`) import cleanly via `TYPE_CHECKING` + lazy `__init__` imports, and `CoreContainer` resolves the matching Selector to `None` when the env var is unset. `make setup` installs `--extra admin --extra aws` by default for full dev coverage; `make quickstart` only needs `--extra admin` (SQLite + InMemory broker). Every other extra opts in explicitly.

## Structured Logging

Logging is always-on (unlike Optional Infrastructure Toggles) and shared across server + worker. Pipeline: `structlog` ProcessorFormatter + `asgi-correlation-id`. Background: #9.

- **Logger acquisition** — all new code uses `structlog.stdlib.get_logger(__name__)`; legacy `logging.getLogger(__name__)` calls still flow through the same pipeline via the ProcessorFormatter bridge but new modules should not add more.
- **Renderer switching** — `LOG_JSON_FORMAT` env var (None → auto: dev/local/quickstart → console, stg/prod → JSON; True/False force override). Controlled by `settings.effective_log_json`.
- **Sensitive-field logging is prohibited** — `password`, `token`, `access_key`, `secret_key`, `api_key`, and any field that Response `model_dump(exclude={...})` strips must NOT appear in `logger.info(event, password=...)`, `logger.bind(...)`, or `structlog.contextvars.bind_contextvars(...)`. The JSON renderer ships structlog kwargs verbatim to aggregators.
- **SQLAlchemy echo** — `DATABASE_ECHO=true` is translated to `logging.getLogger("sqlalchemy.engine").setLevel(INFO)` (not a separate handler) to avoid double-emit between stdlib and structlog pipelines. Do not enable in stg/prod unless secret filtering is in place — bound query parameters reach the log stream.
- **Bootstrap entrypoints** — server: `configure_logging()` → `RequestLogMiddleware` + `CorrelationIdMiddleware` (Starlette adds late-registered middleware as the outermost layer, so CorrelationId is registered last intentionally). Worker: `configure_logging()` → `StructlogContextMiddleware` binds task id / correlation id into contextvars.
- **Env vars** — `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR), `LOG_JSON_FORMAT` (None/True/False).

## Terminology

- **Request/Response**: API communication schema (`interface/server/schemas/`)
- **Payload**: Worker message contract schema (`interface/worker/payloads/`) — background: [ADR 016](docs/history/archive/016-worker-payload-schema.md)
- **DTO**: Internal data carrier between layers — Repository → Router (`domain/dtos/`)
- **Model**: DB table mapping, never exposed outside Repository (`infrastructure/database/models/`)
- **DynamoModel**: DynamoDB table mapping, never exposed outside Repository (`infrastructure/dynamodb/models/`)

## Conversion Patterns

### Write Direction (Request → DB)

- Router → Service: `entity=item` (pass Request directly)
- Service → Repository: pass entity as-is, or transform via `entity.model_copy(update={...})` when domain logic requires it
- Repository → DB: `Model(**entity.model_dump(exclude_none=True))`

### Read Direction (DB → Response)

- DB → Repository: `DTO.model_validate(model, from_attributes=True)`
- Repository → Service → Router: pass DTO as-is
- Router → Client: `Response(**dto.model_dump(exclude={"password"}))`

### Worker Direction (Message → Service)

- Message → Task: `Payload.model_validate(kwargs)`
- Task → Service: pass payload as-is when fields match
- Task → Service: `DTO(**payload.model_dump(), extra=...)` when fields differ

## Write DTO Creation Criteria

- When fields match Request: pass Request directly, no separate Create/Update DTO needed
- When fields differ (auth context injection, derived fields, etc.): create a separate DTO in `domain/dtos/`
  - Example: `CreateUserDTO(**item.model_dump(), created_by=current_user.id)`

## CRUD Write Validation

RDB CRUD writes use Service-owned validation hooks, not Router checks, Repository business rules, or a central validation registry.

- `BaseService` calls protected async hooks before all write paths:
  - `_validate_create(entity)`
  - `_validate_create_many(entities)`
  - `_validate_update(data_id, entity)`
  - `_validate_delete(data_id)`
- Default hooks are no-ops. Domain Services override only the hooks that have explicit business rules.
- Reusable helpers live in `_core/domain/validation.py`; domain-specific composition belongs in `{domain}/domain/validators.py` when the rules are non-trivial.
- Repository read primitives used by validation belong on `BaseRepositoryProtocol` / `BaseRepository`: `exists_by_id`, `exists_by_fields`, and `existing_values_by_field`.
- Database constraints remain the final integrity guard, but user-facing field validation should run in the Service layer first.

## Security Principles

- Do not expose internal details (traceback, DB schema, raw query) in production error responses
- Prevent OWASP Top 10 violations when writing code

## Common Commands

### Run

```bash
make quickstart   # zero-config evaluation (SQLite + InMemory broker)
make demo         # curl walkthrough against running quickstart
make dev          # real local dev (PostgreSQL via docker-compose)
make worker
make diagrams     # regenerate SVGs under docs/assets/architecture/
```

### Test

```bash
make test
make test-cov
make check        # fast local alias for check-core
make check-core   # lint + format check + core tests
make check-full   # CI-parity checks; requires admin + aws extras and dynamodb-local
make check-minimal
```

### Lint / Format

```bash
make lint
make format
make pre-commit
```

### Migration

```bash
make migrate
make migration
uv run alembic downgrade -1
uv run alembic current
```

## Drift Management

> Full rules and Skill Split Convention (Hybrid C): [`docs/ai/shared/drift-checklist.md`](docs/ai/shared/drift-checklist.md) § Drift Management Rules. Entry point: `/sync-guidelines` (Claude) · `$sync-guidelines` (Codex).

- `AGENTS.md` is the canonical source for shared rules — tool-specific harness docs point here, never re-copy
- Shared rule sources: `AGENTS.md`, `docs/ai/shared/`, `.claude/`, `.codex/`, `.agents/`
- Update related docs in the same change when shared rules or harness behavior changes (see drift-checklist.md for the full sync checklist)
- Language drift: new prose in Tier 1 paths must be English — run `python3 tools/check_language_policy.py` before closing work
