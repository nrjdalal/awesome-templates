---
name: add-cross-domain
argument-hint: "from:consumer to:provider"
description: |
  This skill should be used when the user asks to
  "cross-domain dependency", "wire domain dependency", "domain reference",
  "connect domains", "Protocol dependency",
  or needs to wire one domain to depend on another domain's data via Protocol-based DIP.
---

# Cross-Domain Dependency Wiring

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-cross-domain` routing.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/add-cross-domain.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — identify consumer/provider, determine needed functionality
2. Implementation — verify provider Protocol → modify consumer Service → wire DI Container → verify app container
3. Verification — grep for prohibited imports, run tests for both domains
