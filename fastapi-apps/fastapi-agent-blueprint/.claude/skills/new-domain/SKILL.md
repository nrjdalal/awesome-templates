---
name: new-domain
argument-hint: domain_name
description: |
  This skill should be used when the user asks to
  "create a new domain", "domain scaffolding",
  or mentions adding a new bounded context to the project.
---

# New Domain Scaffolding

Domain name: $ARGUMENTS

## Currently existing domains
Identify domains using Glob pattern `src/*/` and exclude `_core`, `_apps` prefixes

## Default Flow Position
- Step: `implement` (architecture commitment — `approach options` upstream is mandatory)
- Routes after: `/test-domain {name} run` (verify) → `/review-architecture {name}` (self-review) → `/sync-guidelines` if shared docs touched
- Recursion guard: do not invoke `/plan-feature` from inside this skill

## Procedure Overview
1. Pre-check — validate name, verify non-existence, ask key fields
2. Scaffolding — 6 layers in order (Domain → Application → Infrastructure → Interface → App Wiring → Tests)
3. Verification — import check, pre-commit, unit tests

Read `docs/ai/shared/skills/new-domain.md` for detailed steps.
Also refer to `docs/ai/shared/scaffolding-layers.md` for the detailed file list and import paths.
Read `.claude/rules/architecture-conventions.md` for object roles and data flow.
