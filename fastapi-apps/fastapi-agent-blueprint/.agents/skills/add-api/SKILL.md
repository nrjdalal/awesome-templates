---
name: add-api
description: Add an API endpoint to an existing domain using the repository's bottom-up layering, DTO rules, and router conventions.
metadata:
  short-description: Add API endpoint
---

# Add API

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-api` routing.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/add-api.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — identify domain, method, path; check existing code; determine needed changes
2. Implementation (bottom-up) — Repository → Service → UseCase(conditional) → Schema → Router
3. Post-completion verification — pre-commit, tests, Swagger check
