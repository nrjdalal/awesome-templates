---
name: add-api
argument-hint: "Add METHOD /path to a domain"
description: |
  This skill should be used when the user asks to
  "add endpoint", "add route", "add API",
  or wants to add a new route to an existing domain.
---

# Add API Endpoint

Request: $ARGUMENTS

## Default Flow Position
- Step: `implement` (`approach options` upstream is conditional — required for non-trivial response shape, cross-domain access, or new validation patterns)
- Routes after: `/test-domain {name} run` (verify) → `/review-architecture {name}` only if layer interactions changed
- Recursion guard: do not invoke `/plan-feature` from inside this skill

## Procedure Overview
1. Analysis — identify domain, method, path; check existing code; determine needed changes
2. Implementation (bottom-up) — Repository → Service → UseCase(conditional) → Schema → Router
3. Post-completion verification — pre-commit, tests, Swagger check

Read `docs/ai/shared/skills/add-api.md` for detailed steps.
Also refer to `docs/ai/shared/project-dna.md` §6 for conversion patterns and §9 for router pattern.
