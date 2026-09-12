# Adoption Guide

Two ways to adopt this blueprint — greenfield or partial import into an existing project.

---

## Path A — Greenfield (recommended)

Use the GitHub template button to start a fresh project with the full structure:

1. Click **"Use this template"** on the [GitHub repository page](https://github.com/Mr-DooSun/fastapi-agent-blueprint).
2. Clone your new repository and run:

```bash
make quickstart   # verify it boots
```

3. From another terminal in the same directory, run `make demo` and `make demo-rag`.
   The RAG demo uses deterministic stubs; it does not call an external model.
4. After evaluation, stop the server and run `make setup` to install development
   dependencies and commit hooks. Follow the [first-domain tutorial](tutorial/first-domain.md)
   or [PostgreSQL development setup](reference.md#local-development-with-postgresql).

DI, domain discovery, and repository-local skills are supplied by the template.
Commit hooks are installed by `make setup`; AI tools have their own
[setup steps](ai-development.md). `make quickstart` is an evaluation command:
it syncs only the admin extra and may remove other installed extras. Restore
development dependencies with `make setup` after returning from evaluation.

---

## Path B — Partial import into an existing FastAPI project

If you have an existing FastAPI project and want to adopt the DDD pattern incrementally:

### Step 1 — Copy `_core/`

```bash
cp -r src/_core /your-project/src/_core
```

This brings in:
- `BaseService` + `BaseRepository` generics
- `CoreContainer` (DI wiring)
- `BaseRequest` / `BaseResponse` / `SuccessResponse` schemas
- Optional infrastructure (embedding, LLM, vectors, storage) behind Selectors

### Step 2 — Add dependencies

```bash
uv add dependency-injector pydantic-settings structlog asgi-correlation-id
# Optional — copy the exact version pins from pyproject.toml [project.optional-dependencies]:
uv add nicegui                                     # admin
uv add aioboto3 boto3                              # aws (S3 / DynamoDB / S3 Vectors)
uv add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc  # otel
```

Or copy the relevant `[project.optional-dependencies]` sections verbatim from `pyproject.toml` to pin to the tested versions.

### Step 3 — Adopt one domain pattern

Use `src/user/` as the reference domain:
- Copy the 4-layer structure (`domain/`, `infrastructure/`, `interface/`, `application/`)
- Wire the domain container into `CoreContainer` via `DynamicContainer` (or manually)
- The `discover_domains()` auto-discovery will pick it up if you place it under `src/{name}/`

See [ADR 004](history/004-dto-entity-responsibility.md) (DTO/Entity responsibility) and [ADR 006](history/006-ddd-layered-architecture.md) (layer structure) before adopting — these are the load-bearing rules.

### Step 4 — Add the pre-commit guard (optional but recommended)

The architecture enforcement hook prevents Domain → Infrastructure imports from creeping in:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: no-domain-infra-import
      name: Prohibit Domain → Infrastructure import
      entry: python tools/check_domain_infra_import.py
      language: python
      types: [python]
```

### What you get per domain

| Layer | Files | Purpose |
|---|---|---|
| `domain/services/` | `{name}_service.py` | Business logic, inherits `BaseService` |
| `domain/dtos/` | `{name}_dto.py` | Data transfer objects |
| `domain/protocols/` | `{name}_repository_protocol.py` | Repository interface (DIP) |
| `infrastructure/repositories/` | `{name}_repository.py` | DB access, inherits `BaseRepository` |
| `infrastructure/database/models/` | `{name}_model.py` | SQLAlchemy ORM model |
| `infrastructure/di/` | `{name}_container.py` | Domain DI container |
| `interface/server/routers/` | `{name}_router.py` | FastAPI router |
| `interface/server/schemas/` | `{name}_schema.py` | Request/Response Pydantic models |

---

## Compatibility

See [`docs/compatibility.md`](compatibility.md) for the full Python / FastAPI / tool version matrix.

## Questions

If you hit friction during adoption, open a [Discussion](https://github.com/Mr-DooSun/fastapi-agent-blueprint/discussions) with your existing project structure — the community can suggest the least-invasive path.
