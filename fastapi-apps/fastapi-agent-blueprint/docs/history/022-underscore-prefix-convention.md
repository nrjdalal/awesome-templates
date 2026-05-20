# 022. Underscore Prefix Convention for Internal Modules

- Status: Accepted
- Date: 2025-10 ~ 2025-11
- Related ADR: [006](006-ddd-layered-architecture.md)(Per-Domain Architecture), [019](019-domain-auto-discovery.md)(Domain Auto-Discovery)

## Summary

To visually distinguish framework/infrastructure modules from business domain modules, we adopted the convention of prefixing internal modules with an underscore (`_core`, `_apps`) — repurposing Python's private convention for "framework vs domain" separation and enabling auto-discovery to exclude them by default.

## Background

- **Trigger**: After flattening the project structure to per-domain top-level directories (ADR 006), `core/` and `apps/` sat alongside business domains like `user/` in `src/`. Navigating the directory listing, it was not immediately clear which directories were framework infrastructure and which were business domains.
- **Decision type**: Upfront design — establishing a naming convention before adding more domains.

The rename happened in two stages:
1. `src/core/` → `src/_core/` (framework infrastructure)
2. Application entry points organized into `src/_apps/` (Server, Worker, Admin)

## Problem

### 1. Visual Ambiguity

In `src/`, `core/`, `apps/`, and `user/` all looked the same. A new developer could not tell at a glance which directories contain business logic and which are framework infrastructure.

```
src/
├── apps/        # framework or domain?
├── core/        # framework or domain?
├── user/        # business domain
└── order/       # business domain
```

### 2. Auto-Discovery Contamination

Without a naming convention, `discover_domains()` would need an explicit exclusion list (`EXCLUDED = ["core", "apps"]`). Every new infrastructure module would require updating this list.

### 3. Import Path Semantics

Python developers associate leading underscores with "internal" or "private." Having `core/` as a public-looking name obscures the fact that business domains should not reach into it directly (they use it via base classes and DI).

## Alternatives Considered

### A. Nested Directory (`src/framework/core/`, `src/framework/apps/`)

Group all infrastructure under a `framework/` parent directory.

Rejected: Adds an extra nesting level to every import path (`from src.framework.core.exceptions...`). Makes imports longer without adding clarity. The flat structure with prefix is more Pythonic.

### B. Explicit Exclusion List in discover_domains()

Keep names as `core/` and `apps/`, and maintain a `SKIP = {"core", "apps"}` set in the discovery function.

Rejected: Requires manual updates when adding infrastructure modules. The prefix convention is self-documenting — the filesystem itself communicates the rule.

### C. Move Infrastructure Outside src/

Place `core/` and `apps/` outside `src/` entirely (e.g., `lib/core/`).

Rejected: Breaks Python's package structure. All code under `src/` shares the same import root. Moving infrastructure outside would require complex import path configuration.

## Decision

Prefix all framework/infrastructure modules with `_`:

```
src/
├── _core/       # shared infrastructure (underscore = internal)
├── _apps/       # interface-specific applications (underscore = internal)
├── user/        # business domain (no underscore)
└── order/       # business domain (no underscore)
```

**Convention rules:**
- `_` prefix = framework/infrastructure module, not a business domain
- No `_` prefix = business domain, auto-discovered by `discover_domains()`
- `.` prefix = hidden (`.git`, etc.), also excluded

**Auto-discovery integration:**

```python
if item.name.startswith(("_", ".")):
    continue  # skip _core, _apps, .git, etc.
```

This single line in `discover_domains()` replaces any explicit exclusion list.

## Rationale

| Decision | Reason |
|----------|--------|
| `_` prefix over nested directories | Flat structure keeps import paths short. Python convention for "internal" aligns with the semantic meaning |
| Convention over configuration | The filesystem naming is the exclusion rule. No config file, no list to maintain |
| Applies to `_core` and `_apps` both | Both are infrastructure that domains should not be confused with. Consistent prefix for both |
| Auto-discovery enabled by convention | `discover_domains()` filters by prefix — adding new infrastructure modules with `_` prefix automatically excludes them |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
