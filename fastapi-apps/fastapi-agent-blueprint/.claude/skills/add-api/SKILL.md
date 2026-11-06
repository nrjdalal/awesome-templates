---
name: add-api
argument-hint: "Add METHOD /path to a domain"
description: |
  This skill should be used when the user asks to
  "add endpoint", "add route", "add API",
  or wants to add a new route to an existing domain.
---

# Add API Endpoint

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-api` routing.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/add-api.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — identify domain, method, path; check existing code; determine needed changes
2. Implementation (bottom-up) — Repository → Service → UseCase(conditional) → Schema → Router
3. Post-completion verification — pre-commit, tests, Swagger check
