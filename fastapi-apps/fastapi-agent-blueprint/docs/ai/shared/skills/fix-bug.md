# Bug Fix Workflow — Detailed Procedure

## Default Flow Position

This skill's four canonical phases map onto Default Coding Flow steps:

| /fix-bug Phase | Default Flow Step |
|---|---|
| Phase 1: Reproduce | `framing` |
| Phase 2: Trace | `plan` |
| Phase 3: Fix | `implement` |
| Phase 4: Verify | `verify` |

The four phase names are load-bearing: [`target-operating-model.md`](../target-operating-model.md)
pins `/fix-bug` Phase 1 to `framing` and Phase 2 to `plan`. Do not rename, re-order, or add to
them. The `Bug Fix Report` below is an **output section**, not a fifth phase, and `Commit` is an
**opt-in post-step**.

`approach options` is **conditionally mandatory**: required when the trace reveals that the fix
could be implemented at multiple layers (e.g. validate at Service vs Router vs Schema) or that the
bug indicates a missing architectural pattern. Skip for single-layer single-line fixes.

After verify, route to:
- `self-review` — `/review-architecture` if the fix changed layer interactions; `/security-review`
  if security-relevant
- `completion gate` — `/review-pr`

The `[hotfix]` / `[긴급]` exception token is the natural escape for genuinely time-critical fixes;
verify is still mandatory under `[hotfix]`. `[trivial]` / `[자명]` is **not** appropriate for a
behaviour bug, because a regression test is required (see `target-operating-model.md` Trace 2).

Recursion guard: do **not** invoke `/fix-bug` recursively. Do not invoke `/plan-feature` for the
*bug's own* framing or planning — `/fix-bug`'s Phase 1+2 already cover those steps.

That guard is **not** an exemption from [ADR 050](../../../history/050-midtask-scope-expansion-gate.md).
If the trace shows the fix requires a capability the repository does not have — a new pattern, a
new infra surface, a new domain — that is new implementation-class work: **stop, report the gap,
and route to `/plan-feature`** ([`AGENTS.md`](../../../../AGENTS.md#mid-task-scope-expansion-adr-050)
§ Mid-Task Scope Expansion). Scope expansion is not recursion.

## Scope Boundary — authorities this skill does not own

Bug fixing sits next to several existing contracts. This skill consumes them and must not
redefine them:

| Concern | Owner | This skill |
|---|---|---|
| Review dimensions, finding basis, `Verdict` (`PASS`/`FAIL`/`CANNOT CERTIFY`/`N/A`) | [`review-protocol.md`](../review-protocol.md) §1–§4 / [ADR 053](../../../history/053-shared-review-protocol.md) — consumed by the three **review** skills only | emits **`Outcome`**, never `Verdict`; is not a fourth protocol consumer |
| `workflow.stage` transitions | `/plan-feature` → `/execute-plan` + `.agents/shared/work_ledger.py` | writes `update_goal_scope_plan(...)` only; never sets `stage` |
| Commit type vocabulary | `.pre-commit-config.yaml` (`conventional-pre-commit`) + [`project-dna.md`](../project-dna.md) §7 | recommends `fix:`; cites those two, not `AGENTS.md` |
| Test file layout, factories, patterns | [`test-files.md`](../test-files.md) / [`test-patterns.md`](../test-patterns.md) / `/test-domain` | decides *which* tests are owed, never their shape |
| Conversion patterns, router patterns | [`project-dna.md`](../project-dna.md) §6 / §9 | referenced during Trace |

The `Bug Fix Report` does **not** replace `self-review` or `/review-pr` — it is the evidence a
reviewer reads, not a review. Its `Drift Candidates` / `Sync Required` fields deliberately match
the shape [`sync-guidelines.md`](sync-guidelines.md) consumes, and that skill lists `/fix-bug` as a
producer; the review skills' own contract ([`review-protocol.md`](../review-protocol.md) §3) does
not reference this report, so do not expect them to consume it automatically.

## Small-Bug Lane

Most bugs are small, and this repository's direction is advisory-first
([`project-dna.md`](../project-dna.md) §0). The lane below is the documented light path — it is
**not** a substitute for an exception token, and a token is not a substitute for it.

Eligible only when **all** hold:
- reproduction is confirmed (Phase 1 completed, not skipped);
- a single root cause in a single layer;
- no external contract, security, migration, shared-base (`_core`), concurrency, or dialect
  fan-out;
- the Cause Impact Matrix (Phase 2) closes locally — every candidate is either the fixed site or
  demonstrably not reached.

The delta from the full lane is explicit — the lane is not "the same thing, faster":

| Step | Full lane | Small-Bug Lane |
|---|---|---|
| Phases 1–4 | all four | all four — **unchanged** |
| Existence gate (Phase 1 step 6) | required | required — **unchanged**; eligibility starts at a confirmed reproduction |
| Cause Impact Matrix | all axes searched, multi-row | **one row** — the fixed site — plus the axes checked and found local; step 5 (fan-out) is skipped by the eligibility test itself |
| Tests | regression at the external contract **and** unit tests at the cause | **one** focused test — the Phase 1 reproduction test, kept as the regression test — and **no** separate unit-at-cause test |
| `approach options` | conditional | **not applicable** — single layer is an eligibility condition |
| Verify gates | focused tests + `pyright` + `pre-commit` + the risk-based sweep (`check-core`, `test-pg`, …) | focused tests + `pyright` + `pre-commit` only; **no sweep** |
| `/review-architecture` / `/security-review` | routed when applicable | **skipped** — no layer interaction, not security-relevant, both by eligibility |
| Bug Fix Report | all fields | `Lane: small-bug` (+ the conditions met), `Scope`, `Reproduction Evidence`, `Root Cause`, the **one-row** `Cause Impact Matrix` (+ the axes checked and found local), `Fix`, `Verification`, `Outcome`, `Sync Required`; `Reported vs Observed` may collapse into `Scope`; `Drift Candidates` / `Next Actions` are `N/A` when empty |
| self-review + `/review-pr` | required | required — **unchanged** |

What the lane drops is breadth. What it never drops is the existence gate, red → green evidence,
and the report.

**The lane must be declared, not merely taken.** A `Lane: small-bug` line in the report, with the
eligibility conditions it met, is what separates a lane run from a full-lane run that simply wrote
one matrix row and stopped — those two are otherwise byte-identical in the output. Every other
reduced path in this repository carries a visible marker (an exception token needs a prompt-line
token *and* a commit-message rationale); the lane is not an exception to that.

## Phase 1: Reproduce

The purpose of this phase is **not** to see a failure. It is to establish that the reported bug
exists and that it fails for the reported reason. A fix built on a misread symptom is the failure
mode this phase exists to prevent (see #401 / PR #402 — an issue filed for a defect that did not
exist, because the end state of `sys.modules` was read as what an earlier test had received).

1. **Triage the report.** Classify it and record the classification:
   - `observed` — a failure was witnessed, with output;
   - `inferred` — derived from reading code, not from a run;
   - `second-hand` — reported by someone else, evidence not attached.
   Record `Reported As` (the claim) separately from `Observed` (what a run shows). They are
   different things and the difference is the finding in a `not-a-bug` case.
2. If a GitHub issue number is provided, read it with `gh issue view {number}`.
3. Check existing tests for a reproduction case before writing one.
4. **Record `Reproduction Evidence`** — all six fields, or say which is unavailable and why:

   | Field | Example |
   |---|---|
   | exact command | `pytest tests/integration/auth/ -k refresh_token -x` |
   | expected vs actual | expected 200 + body; actual `IntegrityError` |
   | environment + config | `TEST_DB_ENGINE=postgresql`; `admin` extra installed; `BROKER_TYPE=inmemory` |
   | prerequisite state | database already holds the schema; one existing row |
   | isolation mode | whole suite / this directory / this test alone / isolated subprocess |
   | repeat count | 1 of 1, or 3 of 10 for an intermittent failure |

   Environment and isolation are not bureaucracy: #374 reproduced only against a pre-existing
   PostgreSQL schema with a partial `Base.metadata`, and #401 depended on `sys.modules` ordering
   inside one shared pytest process. A report without these fields is often irreproducible for the
   next reader, not wrong.
5. **Match the strategy to the bug's determinism.** For a non-deterministic, order-dependent,
   global-state, or concurrency bug, a single green or red run proves nothing. Require whichever
   applies: an isolated subprocess, a solo test run, a repeat count, or a barrier-controlled test.
6. **Branch on what the attempt actually showed.** This decision comes *before* any test is
   written — a report that is disproved or unreproducible cannot honestly produce a red test, and
   demanding one first is how a speculative fix gets written.

   | What the attempt showed | Go to |
   |---|---|
   | the failure occurs, and for the reported reason | step 7 |
   | the reported causal claim is disproved, or a contract says the behaviour is intended | exit `not-a-bug` |
   | anything weaker — no failure observed, evidence insufficient | exit `cannot-reproduce` |

   Both exits are legitimate terminations of this skill. **Neither edits production code, and
   neither writes a reproduction test.**

   - **`not-a-bug`** — permitted only when one of these is true, and the evidence is recorded:
     (a) an authoritative contract (a schema, an ADR, a documented non-goal, a pinned test) says
     the observed behaviour is intended; or
     (b) the reported **causal claim is disproved** in the same environment and the same code
     path — the #401 shape, where reading the existing test showed it already did the thing it was
     accused of not doing.
     Nothing weaker qualifies. "I could not make it fail" is **not** (b) — that is
     `cannot-reproduce`.
   - **`cannot-reproduce`** — an environment gap, a missing precondition, an intermittent failure
     that did not recur, a report without enough detail. List the exact evidence still needed.
     **Never** proceed to a speculative fix from here.
   - A disproved report often still leaves a real finding (in #401: the tests' correctness rested
     on an unstated `pop` + `sys.path` pair). That belongs in `Drift Candidates` / `Next Actions`,
     not in a fix.
7. **Only on a confirmed failure: write the reproduction test and confirm red for the claimed
   reason.** Assert the specific failure mode — the exception type and message, the wrong value,
   the missing row — not merely that something failed. A test that is red for an unrelated reason
   will go green on an unrelated fix.

## Phase 2: Trace

1. **Identify the actual execution path before assuming one.** Start from the real entry point,
   then the state or decision boundaries it crosses, then the failing operation. Pick the template
   that matches — this skill is triggered for any bug, and most of these paths contain no router:

   | Surface | Path to trace |
   |---|---|
   | HTTP CRUD | Router → UseCase → Service → Repository |
   | Worker / scheduler | broker message → `@broker.task` → Service → Repository (+ middleware order) |
   | Admin (NiceGUI) | `@ui.page` handler → Admin Page Config → `_get_service()` → Service |
   | Optional infra / provider | `providers.Selector` → adapter → SDK (+ the stub branch) |
   | Harness / hook | tool event → per-tool shim → `.agents/shared/governor/` policy |
   | Boot / config | `Settings` validator → container wiring → `bootstrap_app` |

2. **Record three distinct things.** Conflating them is what produces symptom-only fixes:
   - **symptom site** — where the failure becomes visible;
   - **propagation path** — how the bad state travelled there;
   - **root cause** — the earliest point where the invariant broke.
3. Inspect conversion boundaries ([`project-dna.md`](../project-dna.md) §6):
   - Is there data loss when passing Request → UseCase?
   - Is the field mapping correct during Model → DTO conversion?
   - Are the excluded fields correct during DTO → Response conversion?
4. Inspect DI wiring:
   - Is the correct implementation being injected?
   - Is the Singleton/Factory distinction correct?

### Cause Impact Matrix

The question this answers is: **if I fix this one site, what else that shares this root cause
stays broken?** Enumerating "edge cases" in the abstract is unbounded and unverifiable;
enumerating what the *recorded root cause reaches* is finite and checkable.

Record one row per candidate:

Worked example — the real #374 matrix, so every cell is a citation you can check:

| candidate | reachability evidence | disposition | evidence |
|---|---|---|---|
| `Base.metadata` completeness under any test selection | `tests/conftest.py:32` calls `load_models()`; without it the metadata holds only what the selected tests happened to import | test added | `tests/unit/_core/infrastructure/persistence/rdb/test_metadata_completeness.py`, run by both legs of the CI `test` matrix |
| PostgreSQL dialect | `KNOWN_ENGINES` (`src/_core/config.py:9`) includes it, and `func.date` returns `date` there but `str` on SQLite | already covered | `tests/unit/_core/infrastructure/persistence/rdb/test_base_repository_contract.py` — its `repository` fixture takes `test_db` (line 69), and the `postgresql` leg of the CI `test` matrix runs it |
| MySQL dialect | `KNOWN_ENGINES` accepts it, so a fork can select it | **deferred** | no MySQL runs in CI — an accepted limit (ADR 058; `ci.yml`: "MySQL is deliberately absent") |
| DynamoDB-backed tables | `drop_all` runs over `Base.metadata`, which is SQLAlchemy-only; `DynamoModel` (`src/_core/infrastructure/persistence/nosql/dynamodb/dynamodb_model.py:72`) subclasses pydantic `BaseModel`, never `Base` | not reached | [`architecture-review-checklist.md`](../architecture-review-checklist.md) §9 pins that inheritance, so a table that is never registered in the metadata cannot be reached by a metadata-completeness bug |

`disposition` is one of:

| disposition | Meaning | Requirement |
|---|---|---|
| **test added** | a new test now covers it | cite the test |
| **already covered** | an existing test covers it **and that test actually runs** | cite the test *and* what runs it |
| **not reached** | the root cause provably cannot reach it | cite why — reachable-but-uncovered is **never** this |
| **deferred** | reachable and supported, but not verifiable here (no MySQL/Docker/credentials) | cite the accepted limit (an ADR or a CI comment). Without such a citation the candidate stays **open**, and an open candidate makes the `Outcome` `partial`, not `fixed` |

The `already covered` requirement is not pedantry. `BaseRepository.count_datas_by_day` documents
the MySQL leg as resting "on documentation rather than a test"
(`src/_core/infrastructure/persistence/rdb/base_repository.py`), so citing a *supported* engine as
covered — the mistake this table used to model — closes a candidate that nothing exercises.

**Search procedure** — work outward from the root cause, in this order:
1. other branches of the same function (empty, `None`, zero, boundary, error path);
2. other implementations of the same `Protocol` or base class;
3. configuration Selectors that resolve to a *different* implementation
   (`providers.Selector` per [ADR 042](../../../history/042-optional-infrastructure-di-pattern.md) —
   the stub branch is a real candidate);
4. **registration / collection sets** — anything that must be *complete* for the operation to be
   correct: model registries (`Base.metadata`), `__all__` exports, Selector maps, hook registries,
   the domain auto-discovery list. Enumerate the **registrars**, not only the call sites: #374's
   root cause was that `Base.metadata` held whatever the selected tests happened to import, so no
   amount of tracing the failing `drop_all` call would have found it;
5. known fan-out axes in this repository:
   - **engine / dialect** — SQLite vs PostgreSQL vs MySQL (the #368 class: `cast(col, Date)` fails
     on SQLite and `func.date` returns `str` there but `date` on PostgreSQL);
   - **realm** — customer (`user`) vs admin (`admin_identity`) token realms;
   - **harness copy** — the same basename living in `.claude/` / `.codex/` / `.antigravity/` /
     `.agents/` (the #401 class);
   - **app process** — server vs worker vs scheduler vs admin.

**Termination condition**: every candidate reachable in code or configuration carries a
disposition. The matrix is closed when no candidate is `open` — not when the list "feels long
enough". A candidate that is reachable but uncovered is `deferred` (with a cited accepted limit)
or `open`; it is never `not reached`, because reachability is exactly what `not reached` denies.

If the matrix shows the fix could land at more than one layer, `approach options` is now mandatory
(see Default Flow Position).

## Phase 3: Fix

1. **Fix at the earliest boundary that owns the broken invariant**, per
   [`AGENTS.md`](../../../../AGENTS.md#responsibility-matrix) § Responsibility Matrix — "each concern
   has exactly one home". This is an *ownership* rule, not a "push it down to domain" rule:
   provider SDK calls, SDK exception translation (`error_mapper.py`), DI wiring and bootstrap
   orchestration are owned by **infrastructure**, and moving such a fix into a domain service
   breaks both the dependency direction and the § Error Translation contract.
2. **The fix must address the recorded root cause**, not the symptom site. If the edit site
   differs from the symptom site, state why — that sentence is what distinguishes a fix from a
   patch.
3. Follow existing patterns — do not introduce new ones (Conversion Patterns:
   [`project-dna.md`](../project-dna.md) §6, Router: §9).
4. Confirm compliance with [`AGENTS.md`](../../../../AGENTS.md) Absolute Prohibitions.
5. **Answer the prevention question**: why did the existing tests not catch this? The answer is
   either a test that is now owed, or a recorded rationale for why the gap is acceptable. This is
   the highest-leverage output of the whole workflow — a bug class that stays invisible recurs.
6. **Distinguish the two test roles** and know which you are adding:
   - a **regression test** pinning the symptom at an external contract or public entry point, so
     the user-visible failure cannot return;
   - **unit tests at the root cause**, so the mechanism is pinned where it broke.
   Shape and location come from [`test-patterns.md`](../test-patterns.md) /
   [`test-files.md`](../test-files.md) / `/test-domain` — not from this skill.

## Phase 4: Verify

1. Confirm the Phase 1 reproduction test now passes (green). Reverting the fix to re-observe red
   is **optional** confirmation — the Phase 1 red evidence already recorded that. Use it when the
   test's precision is in doubt, not as a routine mutation of a working tree.
2. Confirm existing tests are not broken:
   ```bash
   pytest tests/unit/{domain}/ tests/integration/{domain}/ -v
   ```
3. Run the type gate — it covers the whole repository since #394–#399, so a fix can pass the two
   commands above and still fail CI:
   ```bash
   uv run pyright
   ```
4. Run pre-commit hooks:
   ```bash
   pre-commit run --files {changed files}
   ```
5. **Risk-based scope.** State which broader gates were run (`make check-core`, `make test-pg`,
   `make test-dynamo`, `make smoke-examples`) and, for any gate that *could not* run — no Docker,
   no credentials, a missing extra — record it as **deferred evidence** with the reason. A gate
   that was skipped silently reads identically to a gate that passed.

## Output: Bug Fix Report

Always emitted, including on the two Phase 1 exits (where most fields are short or `N/A`).
Guards F / G / H / I in [`AGENTS.md`](../../../../AGENTS.md#reasoning-level-consistency-guards) apply
to this report as to any other reasoning step.

```text
Lane
- full | small-bug (+ the eligibility conditions met)

Scope
- <bug, issue #, affected domain/layer, and what was excluded>

Reported vs Observed
- Reported As: <the claim, and its triage class: observed | inferred | second-hand>
- Observed:    <what a run actually shows>

Reproduction Evidence
- command / expected vs actual / environment + config / prerequisite state /
  isolation mode / repeat count

Root Cause
- symptom site:     <file:line>
- propagation path: <how the bad state travelled>
- root cause:       <file:line — the earliest broken invariant>

Cause Impact Matrix
- <candidate> — reachability: <evidence> — disposition: <test added | already covered | not reached | deferred> — <evidence>
- termination: <closed | open, with what remains>

Fix
- <what changed, and why the edit site differs from the symptom site if it does>
- prevention: <why existing tests missed it → test owed, or rationale>

Verification
- <commands run and results; deferred evidence with reasons>

Outcome
- fixed | partial | not-a-bug | cannot-reproduce

Drift Candidates
- <target, reason, auto-fix, sync-required>

Next Actions
- <follow-up fixes, tests owed, review routing, sync request>

Sync Required
- true | false
```

`Outcome` vocabulary — this is the skill's own field, distinct from the review skills' `Verdict`:

| `Outcome` | Meaning |
|---|---|
| `fixed` | root cause fixed, matrix closed, verification green |
| `partial` | fixed for the reproduced path; matrix has open candidates, each named in `Next Actions` |
| `not-a-bug` | Phase 1 exit (a) or (b), with the evidence recorded |
| `cannot-reproduce` | Phase 1 exit, with the exact evidence still needed |

Record the work in the shared ledger for cross-session context (goal / scope / plan only — this
skill does not own `workflow.stage`):

```python
from work_ledger import update_goal_scope_plan

update_goal_scope_plan(
    goal="<one-line bug and intended outcome>",
    scope="<affected domains/files, and exclusions>",
    plan="<the phase plan, incl. the matrix candidates>",
    updated_by="skill:fix-bug",
)
```

## Post-step: Commit (opt-in)

Only when the user wants a commit. Propose the message and commit after confirmation.

Convention: `fix: {description} (#{issue})` — omit the issue reference when none exists. The type
vocabulary is owned by `.pre-commit-config.yaml` (`conventional-pre-commit`) and
[`project-dna.md`](../project-dna.md) §7; use `fix` for a bug fix and `test` when the change is
only a test that pins an already-correct behaviour.

If an exception token was used on the prompt, the commit message must carry a one-line rationale
([`AGENTS.md`](../../../../AGENTS.md#exception-tokens)).
