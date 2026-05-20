---
name: new-domain
description: Scaffold a new domain that follows the repository's layered architecture, naming rules, DI pattern, and test layout.
metadata:
  short-description: New domain scaffolding
---

# New Domain

## Default Flow Position
- Step: `implement` (architecture commitment — `approach options` upstream is mandatory)
- Routes after: verify (`/test-domain {name} run`) → self-review (`/review-architecture {name}`) → completion gate (`/sync-guidelines` if shared docs reference the new domain)
- Recursion guard: do not invoke `/plan-feature` from inside this skill

## Procedure
1. Read `AGENTS.md` and `docs/ai/shared/skills/new-domain.md` for the full procedure.
2. Read `docs/ai/shared/scaffolding-layers.md` for the detailed file list and import paths.
3. Validate the domain name and confirm `src/{name}/` does not already exist.
4. Use `src/user/` as the reference implementation.
5. Follow the layer order: Domain → Application → Infrastructure → Interface → App Wiring → Tests.
6. Preserve the shared prohibitions and verify imports after completion.
