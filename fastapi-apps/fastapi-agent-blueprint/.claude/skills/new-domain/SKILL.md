---
name: new-domain
argument-hint: domain_name
description: |
  This skill should be used when the user asks to
  "create a new domain", "domain scaffolding",
  or mentions adding a new bounded context to the project.
---

# New Domain Scaffolding

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `new-domain` routing.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/new-domain.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Pre-check — validate name, verify non-existence, ask key fields
2. Scaffolding — 6 layers in order (Domain → Application → Infrastructure → Interface → App Wiring → Tests)
3. Verification — import check, pre-commit, unit tests
