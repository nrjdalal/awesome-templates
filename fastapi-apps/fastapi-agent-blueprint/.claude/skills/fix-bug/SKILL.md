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
- Four canonical phases, 1:1 mapping: Reproduce → `framing`, Trace → `plan`, Fix → `implement`,
  Verify → `verify`. The names are pinned by `target-operating-model.md` — do not rename or add
  phases; the Bug Fix Report is an output section and Commit is an opt-in post-step
- `approach options` upstream conditional — required if multiple layer-fix candidates or missing pattern
- Routes after: self-review (`/review-architecture` if layer interactions changed; `/security-review`
  if security-relevant) → completion gate (`/review-pr`)
- `[hotfix]` / `[긴급]` is the natural escape for time-critical fixes; verify still mandatory.
  `[trivial]` / `[자명]` is **not** appropriate for a behaviour bug — a regression test is required
- Recursion guard: do not invoke `/fix-bug` recursively, and do not invoke `/plan-feature` for the
  bug's own framing/plan. **Not an ADR 050 exemption** — if the fix needs a capability the repo
  does not have, stop, report the gap, and route to `/plan-feature`

## Scope Boundary
- Emits **`Outcome`** (`fixed` / `partial` / `not-a-bug` / `cannot-reproduce`), never `Verdict` —
  that vocabulary belongs to `review-protocol.md` §4 and its three review-skill consumers
- Writes `update_goal_scope_plan(...)` only; **never** sets `workflow.stage` (owned by
  `/plan-feature` → `/execute-plan`)
- Decides *which* tests are owed; test shape comes from `test-patterns.md` / `/test-domain`
- The Bug Fix Report does not replace self-review or `/review-pr`

## Procedure Overview
1. **Reproduce** — triage the report (`observed` / `inferred` / `second-hand`), record
   `Reported As` vs `Observed` and the six `Reproduction Evidence` fields, then **branch before
   writing any test**: confirmed failure → write the red test asserting the *specific* failure
   mode; causal claim disproved (or a contract says the behaviour is intended) → exit `not-a-bug`;
   anything weaker → exit `cannot-reproduce`. Both exits terminate the skill and write **neither**
   production code nor a reproduction test; a disproved report's real finding goes to
   `Drift Candidates`
2. **Trace** — identify the actual entry point first (HTTP CRUD / worker / admin / provider
   Selector / harness hook / boot — most of these have no router), then record symptom site /
   propagation path / root cause as three separate things, check conversion boundaries and DI
   wiring, and build the **Cause Impact Matrix** (candidate → reachability evidence → disposition:
   `test added` / `already covered` / `not reached` / `deferred`). Search branches, Protocol
   implementations, config Selectors, **registration sets** (`Base.metadata`, `__all__`, registries),
   and the dialect / realm / harness-copy / app-process axes. `already covered` requires a test
   that actually runs; reachable-but-uncovered is `deferred` or open, never `not reached`
3. **Fix** — at the **earliest boundary that owns the broken invariant** (AGENTS.md
   § Responsibility Matrix — provider SDK calls, exception translation and DI stay in
   infrastructure; this is not a "push it to domain" rule); no new patterns; answer "why did
   existing tests miss this?"
4. **Verify** — reproduction test green, domain tests, `uv run pyright` (whole repo is in the
   gate), `pre-commit`; record deferred evidence for any gate that could not run
5. **Bug Fix Report** — always emitted, including on both Phase 1 exits
6. **Commit** (opt-in) — propose a `fix:` message and commit after confirmation

Small bugs use the documented **Small-Bug Lane** — not an exception token. It keeps all four
phases, the existence gate, red/green, one focused test (the Phase 1 reproduction test kept as the regression test), pyright + pre-commit,
self-review and `/review-pr`, and it must be **declared** as `Lane: small-bug` in the report; it drops the multi-row matrix, the unit-test-at-cause layer, the
risk-based gate sweep, the architecture/security review routing, and the report fields that are
empty by eligibility. The shared body carries the full delta table.

Read `docs/ai/shared/skills/fix-bug.md` for detailed steps, the six evidence fields, the matrix
search procedure, and the report template.
Also refer to `docs/ai/shared/project-dna.md` §6 for conversion patterns and §9 for router patterns.
