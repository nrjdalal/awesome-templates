# Bug Fix Workflow — Detailed Procedure

## Default Flow Position

This skill's four phases map 1:1 onto Default Coding Flow steps:

| /fix-bug Phase | Default Flow Step |
|---|---|
| Phase 1: Reproduce | `framing` |
| Phase 2: Trace | `plan` |
| Phase 3: Fix | `implement` |
| Phase 4: Verify | `verify` |

`approach options` is **conditionally mandatory**: required when the trace reveals that the fix could be implemented at multiple layers (e.g. validate at Service vs Router vs Schema) or that the bug indicates a missing architectural pattern. Skip for single-layer single-line fixes.

After verify, route to:
- `self-review` — `/review-architecture` if the fix changed layer interactions; `/security-review` if security-relevant
- `completion gate` — `/review-pr`

The `[hotfix]` / `[긴급]` exception token is the natural escape for genuinely time-critical fixes; verify is still mandatory under `[hotfix]`.

Recursion guard: do **not** invoke `/fix-bug` recursively. Do not invoke `/plan-feature` from inside this skill — `/fix-bug`'s Phase 1+2 already cover framing and plan.

## Phase 1: Reproduce
1. Analyze the bug description to identify the affected domain and layer
2. If a GitHub issue number is provided, check details with `gh issue view {number}`
3. Check existing tests for a reproducible test case
4. If no reproduction test exists, write one first (confirm red state)

## Phase 2: Trace
1. Locate the relevant code
2. Trace the call path: Router → UseCase → Service → Repository
3. Inspect conversion boundaries:
   - Is there data loss when passing Request → UseCase?
   - Is the field mapping correct during Model → DTO conversion?
   - Are the excluded fields correct during DTO → Response conversion?
4. Inspect DI wiring:
   - Is the correct implementation being injected?
   - Is the Singleton/Factory distinction correct?

## Phase 3: Fix
1. Fix at the lowest possible layer (prefer domain > infrastructure)
2. Follow existing patterns when fixing — do not introduce new patterns (Conversion Patterns: `docs/ai/shared/project-dna.md` §6, Router: §9)
3. Confirm compliance with `AGENTS.md` Absolute Prohibitions

## Phase 4: Verify
1. Confirm the reproduction test from Phase 1 now passes (green)
2. Confirm existing tests are not broken:
   ```bash
   pytest tests/unit/{domain}/ tests/integration/{domain}/ -v
   ```
3. Run pre-commit hooks:
   ```bash
   pre-commit run --files {changed files}
   ```

## Phase 5: Commit
Commit convention: `{type}: {description} (#{issue})`

Types:
- `fix` — bug fix
- `feat` — new feature
- `refactor` — refactoring
- `test` — add/modify tests
- `docs` — documentation
- `chore` — miscellaneous

If no related issue exists, omit the issue reference: `{type}: {description}`

Propose a commit message to the user and commit after confirmation.
