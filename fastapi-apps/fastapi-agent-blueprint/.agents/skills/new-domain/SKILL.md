---
name: new-domain
description: Scaffold a new domain that follows the repository's layered architecture, naming rules, DI pattern, and test layout.
metadata:
  short-description: New domain scaffolding
---

# New Domain

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `new-domain` routing.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/new-domain.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Pre-check — validate name, verify non-existence, ask key fields
2. Scaffolding — 6 layers in order (Domain → Application → Infrastructure → Interface → App Wiring → Tests)
3. Verification — import check, pre-commit, unit tests
