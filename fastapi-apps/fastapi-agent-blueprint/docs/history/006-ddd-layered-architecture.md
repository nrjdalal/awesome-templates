# 006. Migration to Per-Domain Layered Architecture

- Status: Accepted
- Date: 2025-07 ~ 2025-08
- Related issues: #19, #10, #9
- Related PRs: #20, #14, #15
- Related commits: `f59e96b`, `e248abf`, `bad7a62`, `88afd88`, `1567ec3`

## Summary

To simplify code navigation and align naming with FastAPI conventions, we flattened `apps/` and `domains/` into per-domain top-level folders, renamed controllers to routers, and removed unused gateway code.

## Background

- **Trigger**: Tracing an issue in a single feature required navigating three separate directories (`apps/`, `domains/`, `core/`). Additionally, using "controller" naming conflicted with FastAPI's `APIRouter` convention.
- **Decision type**: Experience-based correction — the navigation overhead and naming inconsistency were felt during daily development.

In the early stages of the project, application code and domain code were separated into `src/apps/` and `src/domains/`.

```
src/
├── apps/
│   ├── monolith/app.py       # Monolith server
│   ├── gateway/app.py        # API gateway
│   └── microservices/
│       ├── user/app.py
│       └── chat/app.py
└── domains/
    ├── core/                  # Common infrastructure
    │   ├── application/
    │   ├── domain/
    │   └── infrastructure/
    └── user/
        ├── domain/
        └── server/
```

Additionally, FastAPI's routing handlers were named `controller`.

## Problem

### 1. Management Complexity of App/Domain Separation

With `apps/` and `domains/` separated, tracking down an issue in a specific feature
required navigating between two directories.
For example, to trace a problem in the user domain:
- `src/apps/microservices/user/` — app configuration
- `src/domains/user/` — business logic
- `src/domains/core/` — common infrastructure

Three locations had to be checked.

### 2. Controller Naming Inconsistency

In the FastAPI ecosystem, routing handlers are called `Router`.
Using `APIRouter` while naming the files `controller` caused confusion.

```python
# Inconsistency: using FastAPI's APIRouter while naming it controller
router = APIRouter()  # FastAPI convention: router
# Filename: user_controller.py  # Project convention: controller
```

### 3. Unnecessary Gateway App

An API gateway was created as a separate app (`apps/gateway/`),
but it was unused code in the current single-server architecture.

## Alternatives Considered

### A. Keep apps/domains separation
- Maintain the existing structure with `src/apps/` and `src/domains/` as separate top-level directories
- Clear separation between "application configuration" and "domain logic"
- Disadvantage: Navigating 3 locations for a single domain's issue; gateway app unused; naming inconsistency persists

### B. Per-domain flattening (chosen)
- Place each domain directly under `src/` — domain contains its own app config and logic
- Rename controllers to routers (align with FastAPI convention)
- Remove unused gateway code
- Disadvantage: Large refactoring (87 files), though mostly file moves with minimal logic changes

## Decision

The structure was improved in three stages.

### Stage 1: Rename Controller to Router (#10, 2025-07-16)

To align with FastAPI conventions, the `controllers/` directory was renamed to `routers/`, and filenames were changed to `*_router.py`.

### Stage 2: Add WebSocket Router (#9, 2025-07-16)

Along with adding WebSocket support, routers were separated by protocol:

```
routers/
├── api/           # HTTP REST routers
│   └── user/
└── websocket/     # WebSocket routers
    └── chat/
```

### Stage 3: Per-Domain Flattening (#19, 2025-08-24)

`apps/` and `domains/` were removed, and each domain was placed directly under `src/`.

```
# After: per-domain flattening
src/
├── app.py              # Main app (absorbed monolith)
├── core/               # Common infrastructure
│   ├── application/
│   ├── domain/
│   └── infrastructure/
├── user/               # user domain (app + domain unified)
│   ├── domain/
│   ├── infrastructure/
│   └── server/
└── chat/               # chat domain
    ├── domain/
    ├── infrastructure/
    └── server/
```

- Removed the gateway app (73 lines of unused code)
- Absorbed the monolith app into `src/app.py`
- Integrated microservices apps into their respective domains

## Rationale

| Criteria | apps/domains Separation (before) | Per-Domain Flattening (current) |
|----------|--------------------------------|-------------------------------|
| Code navigation | Must check 3 locations (apps, domains, core) | Just open one domain folder |
| Naming | controller (Spring convention) | router (FastAPI convention) |
| Unused code | gateway app present | Removed |
| Domain independence | App config separated from logic | Domain contains its own app config |

1. Placing domain folders at the top level enables quick navigation directly to the relevant domain folder when issues arise
2. Following FastAPI's `APIRouter` naming convention keeps framework documentation and code consistent
3. Removing unused gateway code prevents confusion
4. Although it was a large-scale refactoring involving 87 files, most changes were file moves, keeping logic changes minimal

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Follow-up

- DI container and shared infrastructure design proceeded based on this structure -> [007](007-di-container-and-app-separation.md)
- A domain auto-discovery system was later introduced, eliminating the need to modify `container.py` when adding new domains

## Post-decision Update (2026-10-12): Record Correction and Current Rationale

This ADR was written retrospectively on 2026-03-19, seven months after the change. A re-read of the git history shows that its Background describes a short-lived intermediate state rather than the layout the project actually ran on, and that it omits the rationale recorded on the night of the change. The decision stands. This section corrects the record and states what keeps the decision in place, because the motivation recorded that night, microservice readiness, has since lapsed.

### Correction 1: The Layout Before the Change Was Layer-First

From the first `src/` commit (`df85886`, 2025-02-12) until 2025-08-24, application code lived in two packages, `core/` and `server/`, each split into `application/`, `domain/` and `infrastructure/`, with a per-feature folder repeated inside each layer (a `consumer/` package was added beside them on 2025-08-18). On `0b20559` (2025-08-22), the last commit before the change, the user feature was nine files (excluding `__init__.py`) in nine folders across both packages:

```
src/core/application/dtos/user/users_dto.py
src/core/domain/entities/user/users_entity.py
src/core/infrastructure/database/models/user/users_model.py
src/server/admin/views/user/users_view.py
src/server/application/routers/api/user/users_router.py
src/server/application/use_cases/user/users_use_case.py
src/server/domain/services/user/users_service.py
src/server/infrastructure/di/containers/user_container.py
src/server/infrastructure/repositories/user/users_repository.py
```

The `src/apps/` + `src/domains/` layout shown in Background existed for under three hours, on the `refac/19-rafac_ddd` branch merged as `e8e578c`:

| Time (+09:00) | Commit | Change |
|---|---|---|
| 2025-08-24 22:25 | `af8ef31` | Layer-first → `src/apps/` (monolith, gateway, per-domain microservice apps) + `src/domains/<domain>/<layer>/`. **This is the layer-first → domain-first decision.** |
| 2025-08-24 22:38 | `a176217` | Import fixes |
| 2025-08-24 23:50 | `39a5814` | Per-domain `app.py` moved from `src/apps/microservices/<domain>/` into `src/domains/<domain>/` |
| 2025-08-25 01:06 | `378effd` | `src/domains/*` flattened to `src/*`; gateway deleted (73 lines); monolith app became `src/app.py` |
| 2025-08-25 01:13 | `cf2b598` | `run_microservice.py` process handling; per-domain app `root_path` and docs URLs changed (`/user`, `/chat` → `/api`) |
| 2025-08-25 01:23 | `bd38436` | README rewritten with the rationale (Correction 2) |
| 2025-08-27 | `f776074`, `eca91b0` | User entity, DTO and model moved from `src/core/` into `src/user/`; the model then moved from `src/user/server/infrastructure/models/` to `src/user/infrastructure/database/models/` |

Stage 3 above accurately describes `39a5814` and `378effd`. What this ADR omits is `af8ef31`.

### Correction 2: The Rationale Recorded at the Time

The README written that night (`bd38436:README.md`, translated from Korean) lists five reasons for the architecture (L9–L15): scalability, maintainability, testability, domain-centric design, and "microservice readiness: a structure that can move from a monolith to microservices" (L15). Each domain carried an `app.py` described as that domain's microservice entrypoint (L129). The README documented `python -m src.user.app` as the way to run one domain as an independent FastAPI app (L446), although the module only built the app and did not start a server; `run_microservice.py` served each domain's app through Uvicorn (L280). The navigation cost in Background was real, as the nine-file spread above shows, but microservice readiness was an explicitly stated motivation, and this ADR does not mention it.

### The Microservice-Readiness Rationale Has Lapsed

- `f46127b` (2025-09-10) removed the chat microservice module as unused.
- [007](007-di-container-and-app-separation.md) (2025-09 ~ 2025-11) made the interface the runtime unit (Server / Worker / Admin apps sharing one set of domains), not the domain.
- `run_microservice.py` was deleted in `09cf1e2` (2026-03-25). `src/user/app.py` was deleted in `f1ee37a` (2026-04-02) as an unused standalone microservice entrypoint; when deleted, it still wired `src.user.server.application.routers`, a package that no longer existed.

No per-domain entrypoint remains in the repository; the runtime units are the Server, Worker and Admin apps under `src/_apps/`.

### What Keeps the Decision in Place

The layout outlived that motivation because later decisions came to depend on it; the navigation benefit recorded under Rationale still holds.

| Dependent | What it relies on |
|---|---|
| [007](007-di-container-and-app-separation.md) per-domain DI containers | `src/<domain>/infrastructure/di/<domain>_container.py`; this is what resolved single-container bloat and the User ↔ Video circular reference |
| [019](019-domain-auto-discovery.md) auto-discovery | `discover_domains()` returns every `src/<name>/` package (name not starting with `_` or `.`, with an `__init__.py`) that holds that container file, and the apps load the containers and bootstrap functions of what it returns, so adding a domain edits no shared file |
| Example copy-flow (#260) | Copying an example folder into `src/` (`cp -r examples/todo src/todo`) is enough for auto-discovery to pick it up; [examples/README.md](../../examples/README.md) documents the remaining quickstart steps |
| [049](049-admin-identity-realm-separation.md) and Protocol-based cross-domain dependencies (#237) | A bounded context is one folder, so a dependency on another domain is visible at the import site |

Change locality was measured on 2026-10-12 over the 88 non-merge commits on `main` that touch `src/<domain>/<layer>/` since `ab03b03` (2025-09-10, the first commit with today's `domain` / `application` / `infrastructure` / `interface` layers):

| Commit shape | Commits | Domain/layer paths confined to one top-level folder under |
|---|---|---|
| One domain, one layer | 41 (47%) | either layout |
| One domain, two or more layers | 27 (31%) | domain-first only |
| One layer, two or more domains | 8 (9%) | layer-first only |
| Two or more of each | 12 (14%) | neither |

Only `src/<domain>/<layer>/` paths are counted; the same commits often change other files as well (24 of the 27 in the second row do, 18 of them under `src/_core/`, `src/_apps/`, `tests/` or `docs/`). Where the two layouts differ, domain-first keeps a commit's domain code in one folder 27 times against 8 for layer-first, about 3.4 to 1.

### Known Cost

Layers are not visible at the top level, so layer rules cannot be scoped by directory. They are enforced by tooling instead: the `no-domain-infra-import`, `no-domain-infra-import-examples` and `no-entity-pattern` pre-commit hooks and the CI `architecture` job. Agent instructions that differ by layer should follow the same rule: scoped by glob (`src/*/domain/**`) rather than placed per directory, which would need 53 copies across `src/` and `examples/` (proposed in #414, B1). This was re-evaluated on 2026-10-12, when per-directory instruction files were considered: a layer-first layout would make directory scoping possible, but it would give up the locality above and break every dependent in the table.

### Commit and Issue References

- `88afd88` and `1567ec3` in the header do not resolve in this repository.
- `f59e96b`, `e248abf` and `bad7a62` resolve only to commits outside `main`'s history. Their tree-identical counterparts on `main` are `6518b50`, `c0ecbfc` and `5512243`.
- The issue and PR numbers in the header (#9, #10, #14, #15, #19, #20) come from the repository's earlier numbering. Today #9, #10, #14, #15 and #19 point to unrelated issues and pull requests opened on 2026-03-25, and #20 does not resolve. The merge commits keep the original references (for example `e8e578c` for #20 and `981f5ff` for #14).
