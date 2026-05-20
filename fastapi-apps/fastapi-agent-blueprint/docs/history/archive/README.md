# Archived Decision and Evaluation History

These ADRs and archived evaluation memos are preserved for the historical
record but are **not required reading** for contributing to the codebase as it
stands today. Archiving
does not mean "wrong" — it means one of the following:

- **Superseded** by a later decision (the later decision is the source of
  truth; the original is kept so "why did we try X first?" is still
  answerable).
- **Reversed** — the decision was adopted, then explicitly undone. The
  archived record explains both the motivation and the retreat.
- **Operational / tooling** — a genuine choice was made, but it does not
  constrain how domain code is written (e.g. linter selection, package
  manager migration, dashboard framework pick). Useful context, but not
  something a new contributor must internalize to ship a domain.
- **Meta / governance** — decisions about how we run the project or
  write ADRs themselves, distinct from architectural shape.
- **Evaluation / discussion trail** — an archived investigation or synthesis
  memo kept for continuity, even when it intentionally stops short of a final
  decision.

The core reading order lives in [`../README.md`](../README.md).

## Buckets

### Superseded / reversed decisions

| # | Title | Superseded / reversed by |
|---|-------|--------------------------|
| [000](000-rabbitmq-to-celery.md) | Migration from RabbitMQ to Celery | [001](001-celery-to-taskiq.md) |
| [001](001-celery-to-taskiq.md) | Migration from Celery to Taskiq | Still the current broker toolkit — archived as migration context, not a load-bearing architectural rule. |
| [002](002-serena-adoption.md) | Serena MCP Adoption | [030](030-serena-removal-pyright-rules.md) |
| [010](010-code-quality-tools.md) | Code Quality Tooling Systematization | [012](012-ruff-migration.md) |
| [018](018-domain-event-removal.md) | Domain Event Infrastructure Removal | — (removal decision; no current consumer depends on it) |
| [030](030-serena-removal-pyright-rules.md) | Serena Removal → pyright-lsp + `.claude/rules/` | — (reversal of [002](002-serena-adoption.md)) |
| [035](035-embedding-service-abstraction.md) | Embedding Service Abstraction (Selector) | [039](../039-pydantic-ai-embedder-transition.md) |
| [034](034-s3vectors-vectorstore-pattern.md) | S3 Vectors VectorStore Pattern | Layout superseded by [041](../041-vector-backends-consolidation.md); pattern itself still informs vector storage design. |

### Operational / tooling

| # | Title |
|---|-------|
| [005](005-poetry-to-uv.md) | Poetry → uv package manager migration |
| [012](012-ruff-migration.md) | Ruff adoption (pre-commit linting consolidation) |
| [013](013-why-ioc-container.md) | Why IoC container over inheritance (rationale doc) |
| [014](014-omc-vs-native-orchestration.md) | OMC vs native orchestration decision |
| [015](015-rebrand-agent-platform.md) | Rebrand to "AI Agent Backend Platform" |
| [016](016-worker-payload-schema.md) | Worker payload schema convention |
| [023](023-object-storage-unification.md) | Object storage unification (S3/MinIO via aioboto3) |
| [024](024-session-lifecycle-management.md) | Session lifecycle — context manager over factory |
| [026](026-nicegui-admin-dashboard.md) | NiceGUI for admin dashboard |
| [027](027-flexible-rdb-configuration.md) | Flexible RDB multi-engine configuration |
| [028](028-environment-config-validation.md) | Environment-aware config validation |
| [029](029-broker-abstraction-selector.md) | Broker abstraction via `providers.Selector` |
| [036](036-text-chunking-semantic-text-splitter.md) | Text chunking library choice |
| [038](038-llm-observability-dual-path.md) | LLM observability dual-path (Langfuse + `ai_usage`) — not yet implemented (issues #74/#75) |

### Meta / governance

| # | Title |
|---|-------|
| [008](008-deploy-env-separation.md) | Deployment env separation and configuration management |
| [020](020-aidd-skills-governance.md) | AIDD methodology and skills governance |
| [021](021-architecture-governance-hooks-ci.md) | Architecture governance via pre-commit hooks and CI |
| [025](025-oss-preparation-strategy.md) | OSS preparation and internationalization strategy |
| [031](031-shared-rules-tool-harness.md) | Shared rules and tool-specific harnesses |
| [032](032-codex-native-workflow-assets.md) | Codex native workflow assets |
| [033](033-hybrid-c-skill-split-convention.md) | Hybrid C skill split convention |

### Evaluation / discussion trail

| # | Title |
|---|-------|
| [044](044-superpowers-gstack-process-governor-evaluation.md) | Superpowers / gstack / process governor evaluation memo |

### Project status snapshots

| File | Description |
|------|-------------|
| [project-status/project-status-pre-v0.4.0.md](project-status/project-status-pre-v0.4.0.md) | Major changes v0.2.0 → v0.4.0 (26 rows archived 2026-05-06) |
| [project-status/project-status-v0.4.0-v0.5.0.md](project-status/project-status-v0.4.0-v0.5.0.md) | Major changes v0.4.0 → v0.5.0 (18 rows archived 2026-05-11, PR #187) |

### Governor review log (closed archive)

| Directory | Description |
|-----------|-------------|
| [governor-review-log/](governor-review-log/) | 18 per-PR cross-tool review entries from PR #125 to PR #158. Closed historical archive (ADR 047 D6). New reviews use PR-description Governor Footer blocks instead. |
