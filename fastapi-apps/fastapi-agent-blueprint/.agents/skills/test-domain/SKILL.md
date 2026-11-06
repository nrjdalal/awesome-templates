---
name: test-domain
description: Generate or run tests for a domain using the repository's established factory, unit, integration, and admin test patterns.
metadata:
  short-description: Generate or run domain tests
---

# Test Domain

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `test-domain` routing.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/test-domain.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Determine mode — generate or run (ask if unclear)
2. Generate mode — identify Service/UseCase methods, check existing tests, generate missing files
3. Run mode — execute pytest with appropriate scope, analyze failures
4. Verification — verify imports, run tests, run pre-commit
