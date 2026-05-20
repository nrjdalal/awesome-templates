---
name: fix-bug
argument-hint: "bug description or issue number"
description: |
  This skill should be used when the user asks to
  "fix bug", "resolve issue", "fix error", "troubleshoot",
  "debug", or reports a specific bug or error that needs investigation and fixing.
---

# Bug Fix Workflow

Bug description: $ARGUMENTS

## Default Flow Position
- 4-phase 1:1 mapping: Reproduce → `framing`, Trace → `plan`, Fix → `implement`, Verify → `verify`
- `approach options` upstream conditional — required if multiple layer-fix candidates or missing pattern
- Routes after: self-review (`/review-architecture` if layer interactions changed; `/security-review` if security-relevant) → completion gate (`/review-pr`)
- `[hotfix]` / `[긴급]` exception is the natural escape for time-critical fixes; verify still mandatory
- Recursion guard: do not invoke `/fix-bug` recursively. Do not invoke `/plan-feature` from inside

## Procedure Overview
1. Reproduce — identify affected domain/layer, write failing test (Phase 1)
2. Trace — follow call path, inspect conversion boundaries and DI wiring (Phase 2)
3. Fix — fix at lowest layer, follow existing patterns (Phase 3)
4. Verify — confirm test passes, run domain tests and pre-commit (Phase 4)
5. Commit — propose conventional commit message (Phase 5)

Read `docs/ai/shared/skills/fix-bug.md` for detailed steps.
Also refer to `docs/ai/shared/project-dna.md` §6 for conversion patterns and §9 for router patterns.
