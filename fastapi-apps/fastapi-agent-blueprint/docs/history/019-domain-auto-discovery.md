# 019. Domain Auto-Discovery System

- Status: Accepted
- Date: 2026-03
- Related ADR: [006](006-ddd-layered-architecture.md)(Per-Domain Architecture), [007](007-di-container-and-app-separation.md)(DI Container and App Separation), [022](022-underscore-prefix-convention.md)(Underscore Prefix Convention)

## Summary

To enable zero-modification domain scaling, we introduced `discover_domains()` — a convention-based auto-discovery system that detects domain packages under `src/` and dynamically loads their DI containers and bootstrap functions, eliminating the need to edit `container.py` or `bootstrap.py` when adding a new domain.

## Background

- **Trigger**: After establishing per-domain DI containers (ADR 007) and the 3-app architecture (Server/Worker/Admin), adding a new domain required editing 6 files: 3 `container.py` files (one per app) and 3 `bootstrap.py` files. For a project targeting 10+ domains, this manual registration was error-prone and created merge conflicts when multiple developers added domains simultaneously.
- **Decision type**: Upfront design — solving a scaling problem before it caused pain, informed by the target scale (10+ domains, 5+ team members).

Before auto-discovery, each app's container had explicit imports:

```python
# _apps/server/di/container.py (before)
from src.user.infrastructure.di.user_container import UserContainer
from src.order.infrastructure.di.order_container import OrderContainer  # manual

class ServerContainer(DeclarativeContainer):
    user_container = Container(UserContainer)
    order_container = Container(OrderContainer)  # manual
```

## Problem

### 1. Manual Registration Doesn't Scale

Each new domain required 6 file modifications. With 10+ domains being developed in parallel, this becomes a merge conflict hotspot and a checklist that developers forget.

### 2. Boilerplate Duplication

Every domain registration follows the same pattern: import container, wire modules, register router/task. The pattern is mechanical — a strong signal that it should be automated.

### 3. Inconsistency Risk

If a developer registers the container but forgets to register the bootstrap, or registers in Server but forgets Worker, the domain partially works — a silent failure mode.

## Alternatives Considered

### A. Explicit Registration with a Manifest File

Use a `domains.json` or `DOMAINS` config file listing active domains.

Rejected: Still requires manual editing when adding a domain. Adds another file to maintain. The filesystem itself is the most authoritative manifest — if a domain directory exists with the right structure, it should be loaded.

### B. Python Entry Points / Plugin System

Use `setuptools` entry points or a plugin registry to discover domains.

Rejected: Over-engineered for an internal monorepo. Entry points require `pyproject.toml` changes per domain and a package rebuild cycle. The project's convention-based structure makes filesystem scanning simpler and more reliable.

### C. Decorator-Based Registration

Use a `@register_domain` decorator on container classes.

Rejected: Requires importing all domain modules to trigger decorator execution — defeating the purpose of lazy discovery. Also introduces import-time side effects.

## Decision

Implement `discover_domains()` in `_core/infrastructure/discovery.py` with convention-based detection:

```python
def discover_domains() -> list[str]:
    src_path = Path(__file__).parent.parent.parent  # src/
    domains = []
    for item in sorted(src_path.iterdir()):
        if item.name.startswith(("_", ".")) or not item.is_dir():
            continue
        if not (item / "__init__.py").exists():
            continue
        container_file = item / "infrastructure" / "di" / f"{item.name}_container.py"
        if container_file.exists():
            domains.append(item.name)
    return domains
```

**Detection rules** (a directory is a valid domain if):
1. Name does not start with `_` or `.` (excludes `_core`, `_apps`, `.git`)
2. Contains `__init__.py` (is a Python package)
3. Contains `infrastructure/di/{name}_container.py` (has a DI container)

**Dynamic loading**: `load_domain_container()` uses `importlib.import_module()` to load the container class at runtime.

**App-level usage**: Each app's `DynamicContainer` factory calls `discover_domains()` and builds the container tree automatically:

```python
# No need to modify when adding a new domain
server_container = create_server_container()  # auto-discovers all domains
```

**Bootstrap discovery**: `bootstrap.py` iterates over discovered domains and imports each domain's bootstrap function by convention:

```python
for name in discover_domains():
    module = importlib.import_module(f"src.{name}.interface.server.bootstrap.{name}_bootstrap")
    bootstrap_fn = getattr(module, f"bootstrap_{name}_domain")
```

## Rationale

| Decision | Reason |
|----------|--------|
| Convention over configuration | Filesystem structure is the single source of truth. No manifest, no decorator, no config file to maintain |
| `_` prefix exclusion | Aligns with ADR 022 (underscore prefix convention) — `_core` and `_apps` are infrastructure, not domains |
| Container file as proof | A directory with just `__init__.py` might be a utility package. Requiring `{name}_container.py` ensures only properly structured domains are loaded |
| Alphabetical sorting | Deterministic discovery order prevents environment-dependent behavior |
| Same pattern for all apps | Server, Worker, and Admin all use `discover_domains()` — domains are guaranteed to be registered consistently across all interfaces |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
