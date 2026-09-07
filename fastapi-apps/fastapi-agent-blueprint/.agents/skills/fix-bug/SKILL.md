---
name: fix-bug
description: Investigate, reproduce, fix, and verify a bug while staying inside existing repository patterns and architecture rules.
metadata:
  short-description: Structured bug-fix workflow
---

# Fix Bug

## Default Flow Position
- Four canonical phases, 1:1 mapping: Reproduce → `framing`, Trace → `plan`, Fix → `implement`,
  Verify → `verify`. The names are pinned by `target-operating-model.md` — do not rename or add
  phases; the Bug Fix Report is an output section and Commit is an opt-in post-step
- `approach options` upstream conditional — required if Trace reveals multiple layer-fix candidates
  or a missing architectural pattern
- Routes after: self-review (`/review-architecture` if layer changes; `/security-review` if
  security-relevant) → completion gate (`/review-pr`)
- `[hotfix]` / `[긴급]` is the natural escape for time-critical fixes; verify still mandatory.
  `[trivial]` / `[자명]` is **not** appropriate for a behaviour bug — a regression test is required
- Recursion guard: do not invoke `$fix-bug` recursively, and do not invoke `$plan-feature` for the
  bug's own framing/plan. **Not an ADR 050 exemption** — if the fix needs a capability the repo
  does not have, stop, report the gap, and route to `$plan-feature`

## Scope Boundary
- Emits **`Outcome`** (`fixed` / `partial` / `not-a-bug` / `cannot-reproduce`), never `Verdict` —
  that vocabulary belongs to `review-protocol.md` §4 and its three review-skill consumers
- Writes `update_goal_scope_plan(...)` only; **never** sets `workflow.stage` (owned by
  `$plan-feature` → `$execute-plan`)
- Decides *which* tests are owed; test shape comes from `test-patterns.md` / `$test-domain`
- The Bug Fix Report does not replace self-review or `$review-pr`

## Procedure

1. **Reproduce** — triage the report (`observed` / `inferred` / `second-hand`), record `Reported As`
   vs `Observed` plus the six `Reproduction Evidence` fields (command, expected vs actual,
   environment + config, prerequisite state, isolation mode, repeat count), then **branch before
   writing any test**. A confirmed failure — and only a confirmed failure — obliges a reproduction
   test that is red **for the claimed reason** (assert the specific failure mode; mandatory, not
   best-effort). Exit `not-a-bug` when a contract says the behaviour is intended or the reported
   causal claim is disproved in the same environment and code path; exit `cannot-reproduce` for
   anything weaker, listing the evidence still needed. Both exits write neither production code nor
   a test and never lead to a speculative fix; a disproved report's real finding goes to
   `Drift Candidates`.
2. **Trace** — identify the actual execution path before assuming one (HTTP CRUD, worker/scheduler,
   admin page, provider Selector, harness hook, or boot/config — most contain no router), record
   symptom site / propagation path / root cause separately, inspect conversion boundaries and DI
   wiring, then build and close the **Cause Impact Matrix**: candidate → reachability evidence →
   disposition (`test added` / `already covered` / `not reached` / `deferred`). Search other
   branches, other Protocol implementations, config Selectors, **registration sets** that must be
   complete (`Base.metadata`, `__all__`, registries), and the dialect / realm / harness-copy /
   app-process axes. `already covered` requires a test that actually runs; a reachable-but-uncovered
   candidate is `deferred` with a cited accepted limit, or it stays open and the `Outcome` is
   `partial`.
3. **Fix** — at the earliest boundary that **owns** the broken invariant (`AGENTS.md`
   § Responsibility Matrix); provider SDK calls, SDK exception translation and DI stay in
   infrastructure. No new patterns; answer why the existing tests missed it.
4. **Verify** — reproduction test green, focused tests, `uv run pyright`, `pre-commit`; record
   deferred evidence for any gate that could not run.
5. **Bug Fix Report** — always emitted, including on both Phase 1 exits.
6. **Commit** (opt-in) — if the user wants one, propose a `fix:` message after verification.

Read `AGENTS.md` and `docs/ai/shared/skills/fix-bug.md` for the full procedure, the six evidence
fields, the matrix search procedure and termination condition, and the report template.

Small bugs use the documented Small-Bug Lane in the shared procedure rather than an exception
token. It keeps all four phases, the existence gate, red/green, one focused test (the Phase 1 reproduction test kept as the regression test),
pyright + pre-commit, self-review and `$review-pr`, and it must be **declared** as `Lane: small-bug` in the report; it drops the multi-row matrix, the
unit-test-at-cause layer, the risk-based gate sweep, the architecture/security review routing, and
the report fields that are empty by eligibility. The shared body carries the full delta table.
