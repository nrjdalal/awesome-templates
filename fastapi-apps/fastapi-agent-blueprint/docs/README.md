# Documentation

Quick index for the `docs/` folder.

---

## Getting started

| Page | What it covers |
|---|---|
| [quickstart.md](quickstart.md) | Boot the server in 60 seconds — SQLite, no external infra |
| [canonical-demo.md](canonical-demo.md) | End-to-end walkthrough: JWT auth, RBAC, worker, RAG, OTEL, tests |
| [tutorial/first-domain.md](tutorial/first-domain.md) | Build your first domain from scratch — both AI-assisted and manual paths |
| [ai-development.md](ai-development.md) | Set up Claude Code and Codex CLI, install skills |

## Adopting the blueprint

| Page | What it covers |
|---|---|
| [adoption.md](adoption.md) | Greenfield template vs. partial import into an existing FastAPI project |
| [compatibility.md](compatibility.md) | Python / FastAPI / tool version matrix, OS support, DB and broker backends |
| [comparison.md](comparison.md) | How it compares to tiangolo/full-stack, s3rius/template, teamhide/boilerplate |

## Reference

| Page | What it covers |
|---|---|
| [reference.md](reference.md) | Full env var list, tech stack, project tree, `make` targets, roadmap |
| [frontend-handoff.md](frontend-handoff.md) | OpenAPI contract, camelCase wire format, JWT flow, Orval / Bruno / Hey API recipes |

## Operations

| Page | What it covers |
|---|---|
| [operations/observability-otel.md](operations/observability-otel.md) | OpenTelemetry — Jaeger / Tempo / Phoenix setup |
| [operations/observability-langfuse.md](operations/observability-langfuse.md) | Langfuse opt-in for LLM prompt tracing |
| [operations/performance-locust.md](operations/performance-locust.md) | Locust performance-test harness — `make perf-test`, scenarios, reading output |

## Architecture decisions

The [history/](history/) folder contains Architecture Decision Records (ADRs).

- 18 active ADRs in `history/` — open and in effect
- 30 archived ADRs in `history/archive/` — superseded or historical

Start at [history/README.md](history/README.md) for the index.

---

Project root docs: [README.md](../README.md) · [CONTRIBUTING.md](../CONTRIBUTING.md) · [SUPPORT.md](../SUPPORT.md) · [CHANGELOG.md](../CHANGELOG.md)
