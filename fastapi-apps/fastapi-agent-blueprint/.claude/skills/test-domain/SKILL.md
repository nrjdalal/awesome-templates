---
name: test-domain
argument-hint: "domain_name generate|run"
description: |
  Generate or run tests for a specific domain.
  Use when the user asks to "generate tests", "run tests for domain",
  "unit test", "integration test", "pytest run", "write test code",
  or wants to create or run tests for a specific domain.
---

# Domain Test Generation/Execution

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `test-domain` routing.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/test-domain.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Determine mode — generate or run (ask if unclear)
2. Generate mode — identify Service/UseCase methods, check existing tests, generate missing files
3. Run mode — execute pytest with appropriate scope, analyze failures
4. Verification — verify imports, run tests, run pre-commit
