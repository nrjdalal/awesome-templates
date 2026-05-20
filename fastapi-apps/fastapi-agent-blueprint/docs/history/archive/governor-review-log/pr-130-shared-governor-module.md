# PR #130 — Phase 5: shared governor module + thin shims

## Summary

- Repo: fastapi-agent-blueprint
- PR: https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/130
- Branch: `feat/124-shared-governor-module`
- Issue: [#124](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/124)
- ADR: [ADR 045](../../045-hybrid-harness-target-architecture.md)
- Phase: **5 of 5** — closes the [#117](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/117) "Hybrid Harness v1" milestone
- Inherited constraints: pr-125 IC-1 ~ IC-10, pr-126 IC-11 (Phase 2 marker schema + safety-block-first), pr-127 verify-log freshness contract, pr-128 IC-11 resolution (Option A read-and-delete) + IC-12 marker lifecycle

Phase 4 retrospective surfaced four duplication sites that turned governor sync into a footgun: `_within_24h` ×4, the marker reader ×4, `EXPLORATION_TOKENS` ×2, the canonical Korean reminder strings ×2. This PR consolidates governor *policy* into a single Tier B `.agents/shared/governor/` Python package consumed by all six hook scripts as thin shims, while keeping tool-specific runtime adapters (`.codex/hooks/_shared.py` git/subprocess helpers, Codex `session_id()` / verify-log writer / `cleanup_stale_verify_logs`) per-tool. The hybrid governance model itself — escape-token vocabulary, dual-tool adapters, governor-review-log discipline — is permanent; only the implementation moved.

Acceptance proof: 202 unit tests pass (93 baseline + 107 added) including a three-tier fail-open suite that defends the R0-A.1 invariant (importing a shim under `contextlib.suppress(Exception)` MUST NOT raise `SystemExit` — would crash `.codex/hooks/stop-sync-reminder.py`).

Key files:
- `.agents/shared/governor/{__init__,paths,time_window,tokens,markers,safety,verify,completion_gate}.py` — 8 new modules
- `.{claude,codex}/hooks/{user_prompt_submit,verify_first,completion_gate}.py` — 6 hooks rewritten as thin shims
- `tests/unit/agents_shared/{test_time_window,test_governor_phase2,test_governor_phase3,test_governor_phase4,test_shared_module_parity,test_fail_open,test_marker_lifecycle_exhaustive,test_governor_boundary}.py` — 8 new test modules
- `pyproject.toml` — `pythonpath = [".agents/shared"]`
- `docs/ai/shared/{harness-asset-matrix,repo-facts,target-operating-model}.md` + `AGENTS.md` — Tier 1 row + status announcements

## Review Rounds

### Round 0 — plan stage (2026-04-27)

Prompt split into 3 short shots to avoid the hung pattern observed in Phase 4 Round 0. All three returned within ~3 minutes each.

**R0-A — module API design** (`codex exec -m gpt-5.5 --sandbox read-only`)
- Verdict: needs follow-up.

> Original reviewer verdict (ko, verbatim): 보완 필요
> English normalised verdict: needs follow-up.
- Surfaced points:
  - **R0-A.1 (merge-block)**: shim modules must NOT carry top-level `sys.exit` / `raise SystemExit`. `.codex/hooks/stop-sync-reminder.py` imports siblings inside `contextlib.suppress(Exception)`, which does NOT catch `SystemExit` (BaseException subclass). Top-level exits would crash the entire Stop hook.
  - **R0-A.2**: Codex-only assets (`session_id`, verify-log writer/reader, `cleanup_stale_verify_logs`, `_shared.py`) should stay per-tool, not migrate.
  - **R0-A.3**: `GateResult` should expose structured fields (`status`, `governor_changing`, `pr`) instead of returning a stdout string. Rendering belongs to hooks.
- All three integrated into the plan before any code shipped (plan §D2/D3 + §Verification Strategy).

**R0-B — invariance + fail-open**
- Verdict: needs follow-up.

> Original reviewer verdict (ko, verbatim): 보완 필요
> English normalised verdict: needs follow-up.
- Surfaced points:
  - **R0-B.1**: parity baseline must capture `pytest --collect-only -q` nodeids + count + skip/xfail/warning + exit code, not only `PASSED` lines.
  - **R0-B.2**: parity 5 scenarios must be named explicitly (empty/invalid stdin / NFKC + Korean marker / Codex safety-block-first / verify-first exploration·stale / completion-gate four branches).
  - **R0-B.3**: fail-open coverage must include both top-level import failure AND in-call `ImportError`, plus the R0-A.1 SystemExit invariant.
- Integrated into the plan §Verification Strategy + Step 5 test list.

**R0-C — HC-1 + IC-12 + cascade**
- Verdict: needs follow-up.

> Original reviewer verdict (ko, verbatim): 보완 필요
> English normalised verdict: needs follow-up.
- Surfaced points:
  - **R0-C.1**: HC-1 must be enforced by a single-entry function (`safe_parse_exception_token(prompt) -> Blocked | ParsedToken`), not a callable-injection signature like `check_safety_first(prompt, then_parse)`. The latter leaves a bypass surface where a shim can call the parser without ever invoking safety.
  - **R0-C.2**: `MarkerLifecycle` must be a closed enum with an exhaustive coverage test so adding a new variant fails the build until `read_latest_token` is wired and the test updated.
  - **R0-C.3**: `__init__.py` must declare `__all__` for cascade defence, hooks must not redeclare reminder strings or governor-paths globs inline, and a boundary test must enforce both bans.
- Integrated; the boundary test (`test_governor_boundary.py`) actively forbids future inline redeclaration.

### Round 1 — implementation review (2026-04-27)

Three prompts on the 7-commit branch (pre-fix-commit), focused on commit-level diff vs `main`, fail-open coverage, and documentation accuracy.

**R1-A — diff + invariance**
- Verdict: needs follow-up (no merge block).

> Original reviewer verdict (ko, verbatim): 보완 필요 (no merge block)
> English normalised verdict: needs follow-up (no merge block).
- Surfaced points:
  - **R1-A.1 (parity restore)**: `markers.read_latest_token` introduced a `if not data.get('matched')` filter that pre-Phase-5 readers did not have. Even though `write_marker` only persists matched payloads, the filter is a behaviour delta vs the frozen contract.
  - **R1-A.2**: `GateResult.status` should be a closed `Literal` rather than a free-form `str` to prevent invalid status drift.
  - **R1-A.3**: parity suite should include malformed marker / `matched`-missing / timezone-offset timestamp scenarios.
- All three applied in the `fix(governor): apply Round 1 R-points` commit (parity restore + `GateStatus = Literal[...]` + new stale/malformed scenarios).

**R1-B — fail-open + tests**
- Verdict: OK (no merge block).
- Top recommendations: extend `test_fail_open` Tier 2 to `verify_first.read_latest_token_marker` and the `completion_gate` entry; include stale-marker scenario directly in parity 5; reinforce boundary heuristic with import-existence checks.
- Stale-marker scenario was added in the same R1 fix commit. The Tier 2 / boundary reinforcements are tracked but not shipped here — they tighten the existing safety net rather than add new coverage; deferred to a follow-up if needed.

**R1-C — docs + cascade**
- Verdict: needs follow-up (no merge block).

> Original reviewer verdict (ko, verbatim): 보완 필요 (no merge block)
> English normalised verdict: needs follow-up (no merge block).
- Surfaced points:
  - **R1-C.1 (stale figures)**: `~86/14`, `58 assets` figures left over in `target-operating-model.md` and matrix verification checklist. Updated to `~80/20` and `64 active assets` in the R1 fix commit.
  - R1-C.2: Tier 1 placement of the shared package is sensible if the boundary note ("policy package, not passive reference") is preserved — kept.
  - R1-C.3: future-governor-addition rule is now explicitly stated in `AGENTS.md` and `target-operating-model.md`: policy goes to `.agents/shared/governor/`, runtime/state adapters stay per-tool.

### Round 2 — gate-on-gate (2026-04-27)

Single Codex prompt (`gpt-5.5 --sandbox read-only`) targeting the merged shape of this PR + Round 0/1 absorption + cascade-risk re-evaluation. Final Verdict: **minor fixes recommended (no merge block)**.

> Original reviewer verdict (ko, verbatim): 마이너 fix 권장 (no merge block)
> English normalised verdict: minor fixes recommended (no merge block).

Surfaced points:

- **R2.1**: this entry's Round 2 placeholder + Self-Application Proof checkboxes were unfilled at PR-open. Backfilled in this commit (the Round 2 outcome is recorded inline below).
- **R2.2**: completion-gate shims (`.claude/hooks/completion_gate.py`, `.codex/hooks/completion_gate.py`) keep a manual orchestration of `_changed_files → is_log_only_backfill → _read_latest_token → parse_trigger_globs → is_governor_changing → match_log_entry → render` rather than calling the shared `evaluate_gate` + `render_reminder` pair directly. The choice is intentional — existing tests in `tests/unit/agents_shared/test_completion_gate.py` monkeypatch `_changed_files` / `_read_latest_token` / `pr_number_from_branch` on the shim module, and routing through `evaluate_gate` would bypass those patches. Cascade risk: if a future PR adds a new `GateStatus` variant the shim flow must learn the new branch. **Mitigation shipped in this commit**: `tests/unit/agents_shared/test_governor_boundary.py::test_gatestatus_variants_referenced_by_completion_gate_shims` lock-steps `GateStatus.__args__` against an expected-branch-signal map for both shims; adding a variant fails the build until the shim is updated.
- **R2.3**: `harness-asset-matrix.md` row for `.agents/shared/governor/` cited "200 unit tests"; PR + log say "202". Synced to 202 in this commit (R1 stale/malformed scenarios added two).

Cascade-risk verdict: **sufficient for v1 closure**. The shared module + boundary tests + closed `GateStatus` Literal jointly produce a build-time signal whenever a future governor change tries to land outside the shared package or skip a shim flow update.

### Round 2 backfill commit

This commit applies R2.1/R2.2/R2.3 in a single PR-extending commit (not a follow-up PR) because all three are documentation/test-only and would otherwise trigger a Phase-4-style log-only-backfill mini-PR loop.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0A | R0-A.1: shims must not carry top-level SystemExit | Fixed | Fail-open invariant added and tested. |
| Round 0A | R0-A.2: Codex-only runtime assets should stay per-tool | Fixed | Runtime adapters remained outside the shared policy package. |
| Round 0A | R0-A.3: GateResult should expose structured fields | Fixed | Shared completion gate returns structured `GateResult`. |
| Round 0B | R0-B.1: parity baseline too shallow | Fixed | Collect-only and scenario baselines were added to the plan. |
| Round 0B | R0-B.2: parity scenarios not explicit | Fixed | Five scenario families were named and tested. |
| Round 0B | R0-B.3: fail-open coverage incomplete | Fixed | Top-level, in-call, and SystemExit fail-open invariants were covered. |
| Round 0C | R0-C.1: safety parser callable-injection bypass | Fixed | Single-entry `safe_parse_exception_token` adopted. |
| Round 0C | R0-C.2: marker lifecycle should be closed enum | Fixed | `MarkerLifecycle` added with exhaustive tests. |
| Round 0C | R0-C.3: shared API and cascade boundary risk | Fixed | `__all__`, reminder-string, and governor-path boundary tests added. |
| Round 1A | R1-A.1: matched-marker filter parity delta | Fixed | Parity restored against the frozen contract. |
| Round 1A | R1-A.2: free-form GateResult status | Fixed | Status narrowed to a closed literal type. |
| Round 1A | R1-A.3: missing malformed marker scenarios | Fixed | Malformed, missing-matched, and timezone-offset marker cases added. |
| Round 1B | Tier 2 and boundary reinforcements | Deferred-with-rationale | Initial R1-B review accepted no merge block; extra reinforcements were tracked for later polish. |
| Round 1C | R1-C.1: stale asset figures | Fixed | Figures synced in the R1 fix commit. |
| Round 1C | R1-C.2: Tier 1 placement of shared policy package | Rejected | Review judged the placement sensible when boundary notes are preserved. |
| Round 1C | R1-C.3: future-governor-addition rule | Fixed | AGENTS.md and target-operating-model gained the policy-vs-runtime rule. |
| Round 2 | R2.1: unfilled Round 2 and self-application proof | Fixed | Round 2 section and proof were populated. |
| Round 2 | R2.2: completion-gate shim cascade risk | Fixed | Boundary test locks GateStatus variants to both shims. |
| Round 2 | R2.3: stale 200-test figure | Fixed | Matrix figure updated to 202. |
| Round 2 | R1-B leftover absorption | Fixed | Tier 2 fail-open and positive import-shape tests were added. |

## Inherited Constraints

This PR carries the following constraints forward into any subsequent governor-changing PR. Future PRs must cite these by **IC-tag** when their review trail interacts with them.

- **IC-1 ~ IC-10** — preserved verbatim from pr-125.
- **IC-11** (pr-126 + pr-128) — Phase 2 marker schema (`{matched, token, rationale_required, ts}`) + safety-block-first ordering (Codex). Phase 4 resolution: read-and-delete on Stop. **Phase 5 implementation**: enforced inside `.agents/shared/governor/markers.py` (lifecycle as `MarkerLifecycle` enum) + `.agents/shared/governor/safety.py` (single-entry `safe_parse_exception_token` returning `Blocked | ParsedToken` — callable-injection rejected as bypass-prone, R0-C.1).
- **IC-12** (pr-128) — marker lifecycle policy. **Phase 5 implementation**: closed `MarkerLifecycle` enum (`READ_ONLY` / `READ_AND_DELETE`); future variants are guarded by `tests/unit/agents_shared/test_marker_lifecycle_exhaustive.py::test_marker_lifecycle_enum_has_exactly_known_variants`.
- **IC-13 (NEW)** — *No top-level `sys.exit` / `raise SystemExit` in shim modules under `.{claude,codex}/hooks/`*. They are imported by `.codex/hooks/stop-sync-reminder.py` inside `contextlib.suppress(Exception)`, which does NOT catch `SystemExit` (BaseException subclass). Top-level exits would crash the Stop hook. Enforced by `tests/unit/agents_shared/test_fail_open.py::test_tier3_*`.
- **IC-14 (NEW)** — *Hooks must not redeclare reminder strings, governor-paths globs, or token vocabulary inline*. The shared module is the single source of truth. Enforced by `tests/unit/agents_shared/test_governor_boundary.py`.
- **IC-15 (NEW)** — *`.agents/shared/governor/__init__.__all__` is contract*. Removing a name requires a deliberate test update (failing build by default). Adding names is free.
- **IC-16 (NEW)** — *Future governor additions belong in `.agents/shared/governor/`, not in per-tool hook scripts*. Tool-specific runtime adapters (Codex session tracking, Codex `_shared.py` git utilities, the verify-log writer/reader) stay per-tool — they depend on `CODEX_THREAD_ID` or process-lifetime state that is intrinsically tool-bound. Recorded in `AGENTS.md` § Process Governor Reference Documents and `target-operating-model.md` § Shared exception-token alignment.

## Self-Application Proof

The following self-application steps were executed in the same branch on which this PR was raised. The proof is required by ADR 045 §Self-Application Recovery — the governor must follow its own rules.

- **`/review-architecture all`** — domain audit invariants (Domain → Infrastructure imports, Mapper class, Entity pattern) all `clean`. No regression in any of the 3 active domains (`user`, `classification`, `docs`). The shared governor package itself sits outside the application architecture (Tier B governance asset, not a runtime DI participant), so the standard audit does not apply to it; the boundary tests (`test_governor_boundary.py`) and parity tests (`test_shared_module_parity.py`) substitute for the architecture pass on the new package.
- **`/sync-guidelines`** — drift candidates: zero new ones from this PR; `harness-asset-matrix.md` Update Log row added (Phase 5 / #124), `repo-facts.md` Shared Workflow Asset Map gains `.agents/shared/governor/` entry, `AGENTS.md` § Process Governor Reference Documents gains a Status (2026-04-27) line announcing Hybrid Harness v1 completion, `target-operating-model.md` § Shared exception-token bullet rewritten to reflect the shipped state. R1-C.1 cleaned up stale `~86/14` / `58 assets` figures in the R1 fix commit. **Sync Required: false** — all four canonical sources are current.
- **`/review-pr 130`** — drift-candidate detection on this PR itself: zero new candidates (all governance-relevant docs updated in commit 7 + R1 fix). Test invariance asserted by 202 unit tests. The PR description carries the test plan and acceptance criteria explicitly per the Governor-Changing PR template.

## Behaviour-invariance proof (Plan §Verification §"Behavior invariance proof", R0-B.1 — backfilled 2026-04-27)

Plan §Verification mandated a 4-artifact pre/post diff, not a single PASSED count. Captured after Round 2 commit (10 commits on the branch), against `main` at `e00c2bf`:

| Artifact | pre (`main`) | post (`feat/124-shared-governor-module`) | Result |
|---|---|---|---|
| `pytest --collect-only -q` nodeids | 91 unique | 201 unique | **OK — every baseline nodeid is a subset of post** (`comm -23 pre post` = 0 missing) |
| `pytest -v --tb=no` PASSED nodeids | 86 unique | 182 unique | **OK — 0 regressions** (`comm -23 pre-passed post-passed` = 0) |
| Exit code | 0 (`93 passed in 0.91s`) | 0 (`206 passed in 2.31s`) | **OK** |
| warning / skip / xfail line count | 1 (`test_corrupt_marker_skipped`) | 3 (two new test names containing `skip` token) | **OK — no actual SKIPPED/warning/xfail; difference is purely test-name lexical** |

(Unique-nodeid counts under raw counts because `pytest -v` lists parametrized cases on individual lines and the simple regex used for capture does not deduplicate the parametrized ID brackets. The relevant invariant — "no baseline nodeid is missing from post" — holds in both columns and is the actual invariance proof.)

## Round 2 results

- **Round 2 prompt focus**: cascade risk validation (does future governor-asset addition land naturally in `.agents/shared/governor/`?); R1 leftover R-points re-evaluation; dual-system window closure documentation.
- **Outcome**: Final Verdict — **minor fixes recommended (no merge block)**. Three R-points (R2.1 / R2.2 / R2.3) all absorbed in the same commit that records this section, per Round 2's own "minor fixes" classification.

> Original reviewer verdict (ko, verbatim): 마이너 fix 권장 (no merge block)
> English normalised verdict: minor fixes recommended (no merge block).
- **R2.1 — log entry backfill**: Round 2 §Round 2 review section above is now populated; Self-Application Proof checkboxes verified.
- **R2.2 — cascade-risk lock**: `tests/unit/agents_shared/test_governor_boundary.py::test_gatestatus_variants_referenced_by_completion_gate_shims` lock-steps `GateStatus.__args__` against the shim manual-orchestration map. Adding a new variant requires updating both shims and this test in the same PR.
- **R2.3 — figure sync**: `harness-asset-matrix.md` migration risk row updated 200 → 202.
- **R1-B leftover absorption (post-Round-2 polish)**: R1-B.1 added two Tier 2 fail-open scenarios (`test_tier2_verify_first_read_latest_token_marker_safe_default`, `test_tier2_completion_gate_entry_points_safe_default`) so the entry-point degradation contract is exercised end-to-end on both verify-first and completion-gate. R1-B.3 added `test_hooks_import_expected_shared_symbols` to assert the *positive* import shape per shim, complementing the existing inline-redeclaration ban.
- **Cascade-risk verdict**: sufficient for v1 closure. The shared module + boundary tests + closed `GateStatus` Literal + per-shim positive-import assertion jointly produce a build-time signal whenever a future governor change tries to land outside the shared package or skip a shim flow update.
