# 007. DI Container Layering and Interface-Specific App Separation

- Status: Accepted
- Date: 2025-09 ~ 2025-11
- Related Issues: #21, #49
- Related PRs: #23, #50
- Related Commits: `5b96e3b`, `aafdcd4`

## Summary

To resolve single-container bloat, circular references between domains, and different dependency requirements per interface, we introduced per-domain DI containers and separated Server/Worker/Admin into independent apps sharing the same business logic.

## Background

- **Trigger**: After the per-domain architecture migration ([006](006-ddd-layered-architecture.md)), the single DI container grew unbounded as domains increased, circular references between domains (e.g., User ↔ Video) were hard to resolve, and Server/Worker/Admin had different middleware and routing needs but were forced into a single app.
- **Decision type**: Experience-based correction — the container scalability and circular reference issues emerged as new domains were added.

After transitioning to a domain-based layered architecture ([006](006-ddd-layered-architecture.md)),
two problems emerged with the DI container and application configuration.

1. All domain business logic and data logic were concentrated in a single container
2. Server, Worker, and Admin all ran within the same app, making interface-specific separation impossible

## Problem

### 1. Single Container Bloat

As domains grew, a single container ended up containing all Use Cases, Services, and Repositories for every domain,
making the container itself increasingly heavy.

### 2. Circular References Between Domains

For example, the User domain needed to use functionality from the Video domain,
and the Video domain also needed to reference the User domain.
Resolving this circular dependency was difficult within a single container.

### 3. Different Requirements Per Interface

Server (API), Worker (async tasks), and Admin (management tools) each required:
- Different routers/tasks/views
- Different middleware configurations
- Shared business logic (Service, Repository)

Handling all of this in a single app loaded unnecessary dependencies.

## Alternatives Considered

### A. Single container + single app (status quo)
- All domains' Use Cases, Services, and Repositories in one container
- One app handles Server, Worker, and Admin
- Simple to understand but: container bloat as domains grow, circular references hard to resolve, unnecessary dependencies loaded for each interface

### B. Per-domain container + single app
- Each domain gets its own container, resolving bloat and circular references
- Still one app — different interface requirements (middleware, routes) not addressed
- A stepping stone, not the final solution

### C. Per-domain container + per-interface app separation (chosen)
- Each domain has its own DI container (DeclarativeContainer)
- Server, Worker, Admin each have independent app, bootstrap, and top-level container
- Business logic (Service/Repository) shared across all interfaces
- More management points (3 apps) but eliminates duplication of sharable logic

## Decision

### Phase 1: Per-Domain Container + Top-Level ServerContainer (#21, 2025-09)

Each domain was given its own DI container,
and a top-level container (`ServerContainer`) was introduced in the `_shared/` folder to compose them.

```python
# src/_shared/infrastructure/di/server_container.py (commit 5b96e3b)
class ServerContainer(containers.DeclarativeContainer):
    core_container = providers.Container(CoreContainer)
    user_container = providers.Container(
        UserContainer, core_container=core_container
    )
```

- Domain containers were separated to manage each domain's dependencies independently
- Circular references were resolved by injecting dependencies from the parent container
- The scalability weakness of layered architecture was compensated through container layering

### Phase 2: _shared to _apps Refactoring, Interface-Specific App Separation (#49, 2025-11)

The `_shared/` folder was restructured into `_apps/` to separate Server, Worker, and Admin into distinct apps.

```
# Before (_shared structure)
src/
├── _shared/infrastructure/di/server_container.py
├── app.py              # Single app
└── celery_app.py       # Celery app (separate)

# After (_apps structure)
src/
├── _apps/
│   ├── server/         # API server
│   │   ├── app.py
│   │   ├── bootstrap.py
│   │   └── di/container.py
│   ├── worker/         # Async task worker
│   │   ├── app.py
│   │   ├── bootstrap.py
│   │   └── di/container.py
│   └── admin/          # Management tools
│       ├── app.py
│       ├── bootstrap.py
│       └── di/container.py
└── user/
    └── interface/
        ├── server/     # API routers
        └── worker/     # Worker tasks (renamed from consumer to worker)
```

Each app has its own independent container and bootstrap,
while sharing the domain's Service/Repository layers.

## Rationale

| Criterion | Single Container + Single App | Per-Domain Container + App Separation |
|-----------|-------------------------------|---------------------------------------|
| Container size | Unbounded bloat as domains grow | Isolated per domain, loads only what's needed |
| Circular references | Hard to resolve | Resolved via dependency injection from parent container |
| Business logic sharing | N/A (single app) | Server/Worker/Admin reuse the same Services |
| Management points | Few (1 app) | More (3 apps) |
| Independent deployment | Not possible | Each interface can run independently |

1. **Business logic sharing is the key benefit**: Server, Worker, and Admin can share simple CRUD code and common business logic. Since Worker and Admin need to be built separately anyway, managing them within the same architecture actually reduces management overhead.
2. **Container layering**: Compensates for the scalability weakness of layered architecture through DI containers.
3. **Increased management points are acceptable**: The number of apps grows to 3, but eliminating duplication of sharable logic provides a greater benefit.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Supplementary: DynamicContainer vs DeclarativeContainer

The project uses two different container types for different purposes:

| Level | Container Type | Reason |
|-------|---------------|--------|
| Domain (`user_container.py`) | `DeclarativeContainer` | Static structure — each domain's dependencies are known at definition time. Schema is explicit and type-checkable |
| App (`_apps/*/di/container.py`) | `DynamicContainer` via factory function | Dynamic structure — the set of domains is determined at runtime by `discover_domains()`. Cannot be declared statically since domain count is not fixed |

The factory function (`create_server_container()`) calls `discover_domains()`, dynamically loads each domain's `DeclarativeContainer`, and attaches it to a `DynamicContainer`:

```python
def create_server_container():
    container = containers.DynamicContainer()
    container.core_container = providers.Container(CoreContainer)
    for name in discover_domains():
        domain_container_cls = load_domain_container(name)
        setattr(container, f"{name}_container",
                providers.Container(domain_container_cls, core_container=container.core_container))
    return container
```

**Why not `DeclarativeContainer` for apps too?** `DeclarativeContainer` requires all sub-containers to be declared as class attributes at import time. Since the domain list is discovered at runtime, a declarative approach would need code generation or manual registration — exactly what auto-discovery was designed to eliminate ([019](019-domain-auto-discovery.md)).

## Follow-up

- Celery was later replaced with Taskiq ([001](archive/001-celery-to-taskiq.md)), which also changed the Worker app structure
- consumer was renamed to worker (done together in commit `aafdcd4`)
- Domain auto-discovery system introduced in #57, eliminating the need to modify containers in `_apps/` when adding new domains ([019](019-domain-auto-discovery.md))
