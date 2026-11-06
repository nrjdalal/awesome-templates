---
name: add-cross-domain
description: Wire one domain to another using Protocol-based dependency inversion instead of direct implementation imports.
metadata:
  short-description: Add cross-domain dependency
---

# Add Cross Domain

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-cross-domain` routing.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/add-cross-domain.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — identify consumer/provider, determine needed functionality
2. Implementation — verify provider Protocol → modify consumer Service → wire DI Container → verify app container
3. Verification — grep for prohibited imports, run tests for both domains
