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

Target: $ARGUMENTS (domain name + "generate" or "run")

## Default Flow Position
- Step: **`verify`** (canonical owner). `run` mode is the standard post-`implement` action.
- `generate` mode itself is an `implement`-style action; resulting tests must be exercised with `run` afterward.
- Routes after: `/review-architecture {name}` (self-review) if layer interactions changed → `/review-pr` (completion gate)
- Recursion guard: n/a (verify-step skill, not a planning step)

## Procedure Overview
1. Determine mode — generate or run (ask if unclear)
2. Generate mode — identify Service/UseCase methods, check existing tests, generate missing files
3. Run mode — execute pytest with appropriate scope, analyze failures
4. Verification — verify imports, run tests, run pre-commit

Read `docs/ai/shared/skills/test-domain.md` for detailed steps and required test file list.
Also refer to `docs/ai/shared/test-patterns.md` for factory patterns and test examples.
