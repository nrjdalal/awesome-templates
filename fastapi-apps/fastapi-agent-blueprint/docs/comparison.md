# How it compares

This page expands the README comparison with more detail, honest trade-offs,
and the "why not X?" questions that come up on HN and Reddit.

---

## Feature matrix

| Feature | FastAPI Agent Blueprint | [tiangolo/full-stack](https://github.com/fastapi/full-stack-fastapi-template) | [s3rius/template](https://github.com/s3rius/FastAPI-template) | [teamhide/boilerplate](https://github.com/teamhide/fastapi-boilerplate) |
|---|:-:|:-:|:-:|:-:|
| Zero-boilerplate CRUD (8 methods) | **Yes** | No | No | No |
| Auto domain discovery | **Yes** | No | No | No |
| Architecture enforcement (pre-commit) | **Yes** | No | No | No |
| AI workflow skills (Claude + Codex) | **14 + 14** | 0 | 0 | 0 |
| Vector infrastructure (S3 Vectors) | **Yes** | No | No | No |
| Multi-interface (API + Worker + Admin + MCP) | **3 + 1 planned** | 2 | 1 | 1 |
| Architecture Decision Records | **18 active · 30 archived** | 0 | 0 | 0 |
| Type-safe generics across layers | **Yes** | Partial | Partial | No |
| IoC container DI | **Yes** | No | No | No |
| JWT auth + RBAC | **Yes** | Yes | Partial | No |
| Async worker integration | **Yes (Taskiq)** | No | No | Yes (Celery) |
| Admin UI | **Yes (NiceGUI)** | Yes (SQLAdmin) | No | No |
| OpenTelemetry | **Yes (opt-in)** | No | No | No |
| AI Usage Ledger | **Yes** | No | No | No |
| Pluggable DB backends | **4 (PG/MySQL/SQLite/DynamoDB)** | 1 (PG) | 2 (PG/SQLite) | 1 (PG) |
| Vector store | **Yes (S3 Vectors + InMemory)** | No | No | No |

---

## Why not Litestar or Robyn?

**Litestar** is an excellent alternative with strong typing and a rich plugin system. Choose Litestar if:
- You need first-class OpenAPI 3.1 (not 3.0)
- You prefer the Litestar DI system over dependency-injector

Choose this blueprint if you want the FastAPI ecosystem (Pydantic v2, Starlette middleware, extensive community) with DDD structure on top.

**Robyn** is a Rust-backed framework optimized for raw throughput. Choose Robyn if throughput at the edge is your primary constraint. This blueprint optimizes for developer velocity and architectural consistency, not raw requests/sec.

---

## Why not `fastapi/full-stack-fastapi-template`?

The official template is excellent for greenfield projects that need React frontend included. It does not include:
- DDD modular layer separation
- Zero-boilerplate CRUD generics
- Pre-commit architecture enforcement
- AI workflow skills
- Multi-backend infrastructure (DynamoDB, S3 Vectors, etc.)

If you want a full-stack starter (frontend included), use `tiangolo/full-stack`. If you want a backend-focused DDD architecture with AI workflow acceleration, use this blueprint.

---

## Why not cookiecutter-based templates?

Cookiecutter templates generate a project once and then diverge. This blueprint is a **live template** — you can pull upstream improvements into your project via git. The pre-commit architecture enforcement and skill system also require the tooling files (AGENTS.md, `.claude/`, `.codex/`) to remain in the project, which a cookie-cutter approach would strip.

---

## When NOT to use this blueprint

- **Micro-service with one endpoint**: The DDD layer overhead is not worth it for a single-purpose service.
- **You prefer FastAPI's native DI (Depends)**: This blueprint uses dependency-injector IoC container, which adds indirection. If you prefer Depends-everywhere, the cognitive overhead may not pay off.
- **Frontend-included starter**: You need `tiangolo/full-stack` instead.
- **Maximum throughput**: If you're benchmarking raw requests/sec, use Robyn or ASGI without the DDD layers.

---

## Adoption paths

This blueprint works for both greenfield and partial adoption:

- **Greenfield**: Use the GitHub template button (`Use this template`) — you get the full structure.
- **Partial import**: Copy `src/_core/` into your existing project and adopt one domain pattern at a time. See [`docs/adoption.md`](adoption.md) for the step-by-step guide.
