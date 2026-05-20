---
name: fix-bug
description: Investigate, reproduce, fix, and verify a bug while staying inside existing repository patterns and architecture rules.
metadata:
  short-description: Structured bug-fix workflow
---

# Fix Bug

## Default Flow Position
- 4-phase 1:1 mapping: Reproduce → `framing`, Trace → `plan`, Fix → `implement`, Verify → `verify`
- `approach options` upstream conditional — required if Trace reveals multiple layer-fix candidates or a missing architectural pattern
- Routes after: self-review (`/review-architecture` if layer changes; `/security-review` if security-relevant) → completion gate (`/review-pr`)
- `[hotfix]` / `[긴급]` exception is the natural escape for time-critical fixes; verify still mandatory
- Recursion guard: do not invoke `/fix-bug` recursively, do not invoke `/plan-feature` from inside

## Procedure
1. Read `AGENTS.md` and `docs/ai/shared/skills/fix-bug.md` for the full procedure.
2. Reproduce the bug first. If no failing test exists, add one when feasible.
3. Trace the path from interface to persistence, inspecting conversion boundaries and DI wiring.
4. Fix the issue at the lowest sensible layer without introducing new patterns.
5. Verify with focused tests, then broader checks as needed.
6. If the user wants a commit, propose a conventional commit message after verification.
