# 026. NiceGUI Adoption for Admin Dashboard

- Status: Accepted
- Date: 2026-04-08
- Related issue: #14

## Summary

To build an admin dashboard that backend developers can fully own without frontend expertise, we chose NiceGUI for its native FastAPI integration and zero JavaScript dependency.

## Background

- **Trigger**: The project needs an admin interface for non-dev operations team. The current `src/_apps/admin/` is an empty stub with no implementation. The original issue proposed Reflex, but a technology evaluation revealed significant concerns.
- **Decision type**: Upfront design — evaluated before implementation based on project constraints and team composition.

## Problem

The project requires an admin dashboard with:
1. CRUD operations for all domains
2. Progressive expansion to dashboards, statistics, and custom workflows
3. Custom views per domain with role-based access

Key constraints:
- **No frontend developers** on the team — must be Python-only
- Must integrate with existing FastAPI + DI container architecture
- Non-dev operations team will use it — UI must be intuitive
- Deployment complexity should not increase significantly

## Alternatives Considered

### A. Reflex

Python-native framework that transpiles to Next.js (React).

- **Pros**: Highest UI customization freedom, growing community (~28K stars), full SPA capability
- **Cons**:
  - **Beta (v0.x)** — not production-stable yet
  - Requires **Node.js + npm** at build time — adds frontend toolchain management
  - **Dual-process architecture** (FE port 3000 + BE port 8000) — increases deployment complexity
  - Reflex becomes the main app; existing FastAPI app must adapt to Reflex's structure
  - Requires **Redis** for production state management
- **Why not**: Adds the exact management overhead we're trying to avoid. The backend team would need to maintain Node.js builds, dual-process deployment, and Redis — effectively managing a frontend stack despite having no frontend expertise.

### B. Streamlit

Data-focused Python UI framework with the largest community (~44K stars).

- **Pros**: Lowest learning curve, excellent for data visualization, Pandas-native integration
- **Cons**:
  - **Script re-run model** — entire script re-executes on every interaction, making complex CRUD/workflows difficult
  - FastAPI integration only **experimental** (ASGI support since v1.53, Jan 2026)
  - Limited layout customization ("opinionated" framework)
  - Cannot share DI container or DB sessions with existing FastAPI app in production
- **Why not**: The re-run model is fundamentally mismatched for admin CRUD workflows that require complex state management (multi-step forms, inline editing, relationship handling).

### C. SQLAdmin / FastAPI-Admin

Lightweight admin libraries that auto-generate CRUD from SQLAlchemy models.

- **Pros**: Minimal setup, auto-generated from models
- **Cons**: Very limited customization for dashboards, statistics, custom workflows, and role-based views
- **Why not**: Cannot meet the progressive expansion requirements (dashboards, custom workflows).

### D. Jinja2 Templates

Server-side rendering with HTML templates.

- **Pros**: Unlimited freedom, no framework lock-in
- **Cons**: Requires writing HTML/CSS/JS directly — effectively frontend development
- **Why not**: Defeats the core constraint of Python-only development.

### E. React/Next.js (Separate Frontend)

Traditional frontend SPA.

- **Pros**: Maximum UI capability, industry standard
- **Cons**: Requires frontend developers, separate build pipeline, API contract management
- **Why not**: No frontend developers available.

## Decision

Adopt **NiceGUI** as the admin dashboard framework.

Key integration approach:
- Mount on existing FastAPI app via `ui.run_with(fastapi_app)`
- Share DI container, DB sessions, and service layer within the same process
- Admin pages served under `/admin/` path prefix

## Rationale

### 1. Architectural Fit — Same-Process Integration

NiceGUI is built on top of FastAPI/Uvicorn. Using `ui.run_with()`, it mounts directly onto the existing FastAPI application. This means:
- **DI container sharing**: Admin views can directly access domain services through the existing container
- **No API bridge needed**: Unlike Reflex or Streamlit, no HTTP/RPC layer between admin UI and business logic
- **Single deployment unit**: No additional processes, ports, or infrastructure

### 2. Zero Frontend Toolchain

NiceGUI bundles its frontend (Vue.js + Quasar) inside the pip package. From the backend team's perspective:
- `pip install nicegui` — done. No Node.js, no npm, no build step
- All UI code is Python. Debugging stays in Python
- CI/CD pipeline unchanged

### 3. Progressive Capability

- **CRUD**: AG Grid built-in with inline editing, sorting, filtering
- **Dashboards**: Plotly/ECharts integration for charts and statistics
- **Custom views**: Full layout control with Quasar components + Tailwind CSS
- **Custom workflows**: Event-based state management (not script re-run)

### 4. Production Readiness

- Stable release (v3.x) with active maintenance (~2-3 week release cycle)
- Single-worker constraint mitigated by full async support
- Horizontal scaling via load balancer with sticky sessions + Redis storage

### Trade-offs Accepted

- **Single worker limitation**: NiceGUI requires `workers=1`. Acceptable for admin (not high-traffic), and async handles concurrent users well
- **UI polish ceiling**: Quasar-based UI is functional but less visually refined than custom React. Acceptable for internal operations tool
- **Smaller community** (~15K stars) than Streamlit or Reflex. Mitigated by stable API and active maintenance

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Post-decision Update (2026-04-08): Admin Page Architecture Patterns

### Context

The original ADR covered *why* NiceGUI was chosen (technology selection). During implementation, several architectural pattern decisions emerged that define *how* admin pages are structured, wired, and secured. These patterns became the standard for all domain admin pages.

### 1. Template Method Pattern for BaseAdminPage

Rather than each domain building its own admin UI from scratch, we introduced `BaseAdminPage` as a dataclass-based Template Method:

- **Config declaration**: Domains declare a `BaseAdminPage` instance with `ColumnConfig` entries — pure data, no code
- **Hook methods**: `render_list()` and `render_detail()` define the algorithm structure. Subclasses can override `render_list_header()`, `render_search_bar()`, `render_grid()` for customization
- **Field masking**: `ColumnConfig.masked=True` renders sensitive fields as `"****"` server-side — the actual value never reaches the browser

**Why Template Method over composition**: Admin pages follow a rigid structure (list → detail → back). The variation is in *what columns to show* and *how to render them*, not in the page flow itself. Template Method captures this fixed-algorithm-with-variable-steps pattern directly.

### 2. DI Pattern Unification Across All Interfaces

Admin pages initially used a closure-based `register_pages(service)` pattern, where the bootstrap function passed services as closure variables. This was replaced with `@inject` + `Provide[Container.service]` — the same pattern used by Server routers and Worker tasks.

```python
# Before (closure-based — admin-specific, hard to test)
def register_pages(user_service: UserService):
    @ui.page("/admin/user")
    async def user_list():
        data = await user_service.get_datas(...)

# After (unified with server/worker — testable, consistent)
@ui.page("/admin/user")
@inject
async def user_list(
    user_service: UserService = Provide[UserContainer.user_service],
):
    data = await user_service.get_datas(...)
```

**Why**: Three interfaces (Server, Worker, Admin) sharing one DI pattern means one mental model for the team. Onboarding cost drops because the pattern is learned once.

### 3. Service Resolution Internalization in BaseAdminPage

Initially, the bootstrap function resolved services and passed them to each page handler. This was refactored so that `BaseAdminPage` resolves its own service via an injected `_service_provider` callable:

```python
# bootstrap.py — injects provider once
page_config._service_provider = getattr(admin_container, f"{domain}_service")

# BaseAdminPage — resolves on demand
def _get_service(self):
    return self._service_provider()
```

**Why**: Aligns with the "thin interface" convention where routers and tasks don't manage service construction. The admin interface follows the same principle — page handlers are thin, service resolution is infrastructure's job.

### 4. Security Hardening

- **Server-side field masking**: `ColumnConfig.masked` fields are replaced with `"****"` before data reaches the browser. This is distinct from client-side masking (CSS `password` input), which still sends the real value over the network.
- **Timing-safe authentication**: `hmac.compare_digest()` used for both username and password comparison in `AdminAuthProvider`. Using it for username too (unusual) prevents a timing side-channel that could reveal valid usernames.
- **Session storage**: NiceGUI's `app.storage.user` with `storage_secret` for session management — simple, no external session store dependency.

### 5. Auto-Discovery Integration

Admin bootstrap follows the same `discover_domains()` pattern as Server and Worker. Per domain, it:
1. Imports `{domain}_admin_page` from `interface/admin/configs/`
2. Injects the service provider from the admin DI container
3. Imports page routes (triggering `@ui.page` registration)
4. Silently skips domains without admin pages (`ModuleNotFoundError`)

**Why silent skip**: Not all domains need admin pages. Forcing every domain to have an admin stub would create empty boilerplate — contrary to the project's YAGNI principle.
