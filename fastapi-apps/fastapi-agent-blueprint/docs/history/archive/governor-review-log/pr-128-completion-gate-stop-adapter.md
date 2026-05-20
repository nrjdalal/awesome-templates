# PR #128 — Hybrid Harness Phase 4: completion-gate Stop adapter

- GitHub PR: <https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/128>
- Closes: #123
- Branch: `feat/123-completion-gate-stop-adapter` → `main`
- Date range: 2026-04-27
- Cross-tool reviewer: `codex exec -m gpt-5.5 --sandbox read-only` (Round 0 hung — see §6 of plan); Round 1 in progress.

## Summary

Implements Phase 4 of [ADR 045](../../045-hybrid-harness-target-architecture.md): adds the completion-gate Stop adapter so the `completion gate` step of the Default Coding Flow is enforced at session end.

- **IC-11 resolution (Option A)**: Phase 2 exception-token markers are read-and-deleted by the Stop hook on both sides. `read_latest_token_marker` (both `verify_first.py` files) gains a 24h filter to skip Stop-failure leftovers. Marker schema unchanged from Phase 2 (no `session_id` field added). See §IC-11 Resolution below.
- **Pillar 7**: `completion_gate.py` (both sides) parses `governor-paths.md` at runtime (IC-10 — no inline glob re-declaration) and emits a reminder when `changed_files` intersects Tier A/B/C globs without a matching `governor-review-log/pr-{N}-*.md` entry whose `{N}` equals the current PR number. `[exploration]`/`[탐색]` token silences Pillar 7 too.
- **Claude side** — new `.claude/hooks/completion_gate.py` (~120 LOC). Called as subprocess by existing `stop-sync-reminder.sh` (HC-4.2 single Stop entry — `.claude/settings.json` unchanged). `main()` runs Pillar 7 check then `consume_phase2_markers()`.
- **Codex side** — new `.codex/hooks/completion_gate.py` (~140 LOC). Imported by existing `stop-sync-reminder.py` segments list (IC-2). Adds `governor_changing_segment()`, `consume_phase2_markers()`, `cleanup_stale_verify_logs()` (opportunistic 24h cleanup of OTHER sessions' verify-log files).
- **Phase 3 compatibility** — `verify_first.py` 24h filter is purely additive; Phase 3 test fixtures updated from hardcoded past-ts to dynamic ts.
- **Informational only** — never blocks commit or Stop (HC-4.1 / HC-3.3).
- Tests: `tests/unit/agents_shared/test_completion_gate.py` (31 cases). IC-2 GOVERNOR_REMINDER_* string-equality. `parse_trigger_globs` real file parse. `is_governor_changing` / `is_log_only_backfill` / `match_log_entry` classification. `pr_number_from_branch` fail-open smoke. 4 sample runs per `migration-strategy.md §Phase 4`. IC-11 lifecycle (consume deletes, idempotent, post-consume None). 24h stale marker ignored. `cleanup_stale_verify_logs` session isolation. Pillar 7 silence on exploration tokens / no-PR fallbacks.
- Docs: `harness-asset-matrix.md` Tier 3 +2 rows (Total 61→63, Overlay 11→13); `repo-facts.md` IC-11 resolution entry; `project-status.md` Phase 4 row.

## IC-11 Resolution (closed by Phase 4 / PR #128)

Phase 4 commits to **Option A — read-and-delete on Stop** with opportunistic 24h cleanup:

- Stop hook (both Claude and Codex sides) reads the latest marker (via `verify_first.read_latest_token_marker` or `completion_gate._read_latest_token`), applies `[exploration]`/`[탐색]` silence to its own segments, then calls `completion_gate.consume_phase2_markers()` which deletes ALL `exception-token-*.json` files in the state dir.
- `read_latest_token_marker` skips markers older than 24h (defensive against Stop-failure leftovers).
- Marker schema unchanged from Phase 2 (no `session_id` field added; PR #126 schema remains valid).
- Rationale: Stop is the sole consumer-deleter; PostToolUse readers (Phase 3 Claude `verify_first.py`) and Stop pre-segment readers (Phase 3 Codex `verify_first.should_remind`) all run before Stop's delete, so within one prompt all reads see the same file.
- Open question absorbed by Phase 5 (#124): should `.codex/state/verify-log-*.json` cleanup also be Stop-driven, or thread-aware via `CODEX_THREAD_ID` lifecycle? Phase 4 only does opportunistic 24h cleanup of *other* sessions' logs.

## Review Rounds

### Round 0 — Plan Review (plan stage)

- **Target**: `/Users/coursemos/.claude/plans/phase-4-123-snug-babbage.md` (§1~§10).
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only` (Codex CLI, read-only sandbox).
- **Status**: **Hung** — process ran 70+ minutes with ~0 CPU after exhausting model context. All 10 review angles are enumerated in plan §10 (Open Questions); they are carried into Round 1.
- **Fallback**: Claude self-stand-in (same as PR #126 lesson).

### Round 1 — Implementation Review

- **Target**: Commits `46c8fb2`, `e984386`, `5300303`, `b4e91b8` (4 impl commits). **pytest 93/93 PASSED** (34 token-parser + 28 verify-first + 31 completion-gate). All 4 sample-run unit tests (`test_sample_run_1~4`) verified.
- **Reviewer**: Claude self-administered stand-in (Round 0 Codex hung; Codex re-attempt pending credit restoration — same pattern as PR #126 Round 2). IC-8 substitution caveat applies.
- **Final Verdict**: `minor fixes recommended (no merge blockers)`. 1 R-point (R1.1) closes in the same commit as this review entry.

**Assessment by angle:**

1. **IC-11 Option A multi-Stop edge cases** — OK. Within one prompt: PostToolUse readers → Stop pre-segment verify_first.should_remind → completion_gate._read_latest_token → consume_phase2_markers. All reads precede the delete. Cross-session risk (Session A Stop deletes Session B's `[exploration]` marker) is the accepted Option A limitation; consequence is informational-only (HC-4.1).

2. **Pillar 7 false-positive/negative** — OK. All 4 sample-run unit tests verify the critical paths: no-entry → reminds, matching entry → silent, log-only-backfill → silent, wrong-PR-number entry → reminds. Self-application recursion clean: this PR's `governor-review-log/pr-128-*.md` in `changed_files` → `match_log_entry` returns "match" → silent.

3. **24h filter Phase 3 fixture** — OK. `test_corrupt_marker_skipped` (dynamic ts) and `test_codex_marker_read_parity` (dynamic ts) both pass; 93/93 green.

4. **IC-2 single-event** — OK. No new `.claude/settings.json` / `.codex/hooks.json` Stop entries. `test_governor_reminder_with_pr_string_equality` + `test_governor_reminder_no_pr_string_equality` confirm cross-side string parity.

5. **governor-paths.md parse robustness** — OK for current format. `parse_trigger_globs` correctly handles `^### Tier [ABC]` → `^##` tier boundaries; backtick glob extraction verified by `test_parse_trigger_globs_returns_globs` (real file read). Known fragility: inline code blocks with backticks inside tier sections would be mis-extracted as globs — documented as Phase 5 item.

6. **Phase 3/4 segment overlap** — OK. Both segments can fire simultaneously on Codex Stop; each carries distinct actionable information.

7. **Self-application recursion** — OK. See angle 2 above.

8. **`[trivial]`/`[hotfix]` cascade vs Pillar 7** — **needs follow-up → R1.1 below**.

> Original reviewer verdict (ko, verbatim): 보완 필요
> English normalised verdict: needs follow-up.

9. **Phase 5 readiness** — OK. Claude `.sh`+`.py` pair preserved; Codex pure-py. `_within_24h` x4 + `_read_latest_token` near-duplication explicitly deferred to Phase 5 (New Inherited Constraints).

10. **Acceptance test coverage** — OK. 31 cases cover: IC-2, parse_trigger_globs (real file + absent file), is_governor_changing (4 variants), is_log_only_backfill (2 variants), match_log_entry (5 variants), pr_number fail-open, 4 sample runs, IC-11 lifecycle (delete / idempotent / post-delete None / 24h filter), cleanup_stale_verify_logs (session isolation), Pillar 7 silence (`exploration` token, `[탐색]` token, no-PR-with-entry, no-changed-files).

**R-points:**

- **R1.1**: `[trivial]`/`[hotfix]` intentionally do **not** silence Pillar 7. `EXPLORATION_TOKENS = frozenset({"exploration", "탐색"})` — only the exploration-class tokens bypass the governor-changing check. Rationale: even a one-line trivial edit to `AGENTS.md` still warrants a governor-review-log entry; `[trivial]` means "small change, skip plan/verify steps" but does not mean "exempt from governance artefact requirements." This was left open in the plan and is now recorded as an explicit decision here. **No code change** — the current behaviour is correct; documentation-only R-point closing in this commit.

### Round 2 — Cross-Check (gate-on-gate)

- **Target**: Full branch diff vs main (5 commits). pytest 93/93 PASSED.
- **Reviewer**: Claude self-administered stand-in (same constraint as Round 1 — IC-8 substitution caveat applies).
- **Final Verdict**: `merge-ready`. Round 1 R1.1 closed in the same commit set (documentation-only). No new findings.

**R7.1 ~ R7.7 audit (PR #125 gate-on-gate framework):**

- **R7.1 (findings separated from evidence)**: Round 1 findings vs evidence separated above. ✓
- **R7.2 (behaviour-preserving framing)**: Phase 3 fixture updates (hardcoded past-ts → dynamic ts) are purely additive/defensive; no Phase 3 behaviour changed. ✓
- **R7.3 (safety preservation)**: No changes near PROMPT_RULES / HC-1 safety logic. completion_gate.py never touches safety checks. ✓
- **R7.4 (bucket-share consistency)**: `target-operating-model.md` §7 and `migration-strategy.md` §6 still cite "~86%/~14%" — now stale at 79%/21%. Both docs acknowledge "matrix is canonical"; the matrix Update Log records the full evolution. No edit needed (same rationale as PR #126 R7.4).
- **R7.5 (tier count arithmetic)**: Tier 3 = 18 (16 Phase-3 + 2 Phase-4). `Tier 0=9 + Tier 1=17 + Tier 2=14 + Tier 3=18 + Tier 4=6 = 64; Total 63` (excludes `.claude/settings.local.json`). Counting note in matrix is internally consistent. ✓
- **R7.6 (IC carry-forward into next phase)**: Open questions absorbed by Phase 5 documented in §New Inherited Constraints: (a) `verify-log-*.json` lifecycle; (b) `_within_24h` x4 consolidation. Phase 5 issue (#124) will read this entry on start. ✓
- **R7.7 (PR template Governor-Changing section filled)**: PR #128 body includes Governor-Changing checklist with all items checked. ✓

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | Codex Round 0 hung before output | Deferred-with-rationale | The failed read-only run produced no R-points; Round 1 and Round 2 covered the implementation surface. |
| Round 1 | R1.1: trivial and hotfix tokens must not silence Pillar 7 | Fixed | Behaviour confirmed as correct and documented in this entry. |
| Round 2 | R7.1: findings separated from evidence | Fixed | Round 1 findings and evidence were separated. |
| Round 2 | R7.2: behaviour-preserving framing | Fixed | Phase 3 fixture updates recorded as additive and defensive. |
| Round 2 | R7.3: safety preservation | Fixed | Completion gate kept safety checks untouched. |
| Round 2 | R7.4: bucket-share consistency after asset-count drift | Deferred-with-rationale | Matrix was treated as canonical; stale percentage mentions in other docs were left as historical references. |
| Round 2 | R7.5: tier count arithmetic | Fixed | Matrix counting note was internally consistent at merge time. |
| Round 2 | R7.6: IC carry-forward into Phase 5 | Fixed | Phase 5 inherited constraints documented follow-up ownership. |
| Round 2 | R7.7: PR template Governor-Changing section filled | Fixed | PR #128 body carried the filled checklist. |

### Self-Application Proof

PR #128 is governor-changing (Tier B: `.claude/hooks/`, `.codex/hooks/`). The governor's own self-review and completion-gate steps are recorded here.

#### `/review-architecture all`

```
Scope
- Target: all (changed surface of feat/123-completion-gate-stop-adapter — 5 commits vs main)
- Audited domains: none (no src/ change)

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/governor-paths.md
- docs/ai/shared/governor-review-log/pr-125-hybrid-harness-target-architecture.md (IC-1 ~ IC-10)
- docs/ai/shared/governor-review-log/pr-126-userpromptsubmit-token-parser.md (IC-11)
- docs/ai/shared/governor-review-log/pr-127-verify-first-adapters.md

Findings
- none

Drift Candidates
- target: target-operating-model.md §7 + migration-strategy.md §6 "~86%/~14%" references
  reason: now stale at 79%/21% after Phase 4 Overlay additions
  auto-fix: no (both docs acknowledge "matrix is canonical"; stale narrative snapshot is acceptable)
  sync-required: false
- target: governor-review-log/pr-128-completion-gate-stop-adapter.md
  reason: governor-changing PR must add entry
  auto-fix: yes (this commit set)
  sync-required: true (closed by commit 5)
- target: governor-review-log/README.md Index
  reason: new PR row needed
  auto-fix: yes (commit 5)
  sync-required: true (closed)

Next Actions
- User reviews PR on GitHub and merges.
- Phase 5 (#124) picks up via §New Inherited Constraints.

Completion State
- complete; drift candidates closed by commit 5 + Round 1/2 backfill commit.

Sync Required
- false (all candidates closed or explicitly deferred)
```

#### `/sync-guidelines`

```
Mode: review follow-up

Input Drift Candidates: 8 consumed
- governor-review-log/pr-128-completion-gate-stop-adapter.md (this entry)
- governor-review-log/README.md Index row
- governor-review-log/pr-126 IC-11 Resolution backfill
- harness-asset-matrix.md Tier 3 +2 rows (commit 4)
- repo-facts.md IC-11 Option A + verify-log cleanup (commit 4)
- project-status.md Phase 4 row (commit 4)
- PR template Governor-Changing PR section (filled in PR body at gh pr create)
- Round 1 R1.1 [trivial]/[hotfix] NOT silencing Pillar 7 (documentation-only, this entry)

project-dna: unchanged (no code-pattern shift)

AUTO-FIX (commits 4+5):
- harness-asset-matrix.md Tier 3 row count 18 + 2 new completion_gate.py rows; Bucket Distribution 61→63 (79%/21%); Counting note + Update Log refreshed
- repo-facts.md IC-11 Option A resolution text + verify-log cleanup mention
- project-status.md Phase 4 row + Last synced updated
- governor-review-log/pr-128-*.md created with Summary / IC-11 Resolution / Review Rounds 0~2 / Inherited Constraints / Self-Application Proof
- governor-review-log/README.md Index row added
- governor-review-log/pr-126 IC-11 Resolution section backfilled

REVIEW:
- R1.1 [trivial]/[hotfix] NOT silencing Pillar 7 — design decision confirmed and documented here (no code change needed)
- target-operating-model.md + migration-strategy.md "~86%/~14%" stale references — deferred (matrix is canonical; stale snapshots are acceptable)

Remaining: none

Next Actions:
- Merge PR #128 into main.
- Phase 5 (#124) opens next; inherits §New Inherited Constraints.
```

#### `/review-pr 128`

```
Scope
- PR: #128 — Hybrid Harness Phase 4: completion-gate Stop adapter (Closes #123)
- Base/Head: main / feat/123-completion-gate-stop-adapter
- Affected domains: process/governance layer only (no src/ change)
- Changed files: 14 (5 commits)

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/security-checklist.md
- docs/ai/shared/governor-paths.md
- docs/ai/shared/migration-strategy.md §Phase 4 acceptance
- docs/ai/shared/governor-review-log/pr-125-hybrid-harness-target-architecture.md
- docs/ai/shared/governor-review-log/pr-126-userpromptsubmit-token-parser.md
- docs/ai/shared/governor-review-log/pr-127-verify-first-adapters.md

Findings
- none

Drift Candidates
- none (all closed in commit set 4+5 + Round 1/2 backfill)

Next Actions
- User reviews PR on GitHub and merges.
- Phase 5 (#124) next.

Completion State
- Claude-side completion gate: PASSED.

Sync Required
- false
```

## Inherited Constraints

Carried from prior governor-changing PRs (no new IC introduced by Phase 4 — IC-11 is resolved, not new):

| IC | Source | Rule | Phase 4 application |
|---|---|---|---|
| IC-1 | PR #125 | Shared rules live in `AGENTS.md` + `docs/ai/shared/` | Phase 4 hook spec derived from `AGENTS.md` Default Flow + `governor-paths.md` |
| IC-2 | PR #125 | Single Stop event output (Codex) | `stop-sync-reminder.py` segments list; `GOVERNOR_REMINDER_*` string-equal Claude/Codex |
| IC-3 | PR #125 | Token regex canonical form in `AGENTS.md` | Phase 4 reads Phase 2 markers; no new token vocab |
| IC-4 | PR #125 | Exception tokens do not override Absolute Prohibitions | Phase 4 is informational only; `[exploration]` silences Pillar 7 but not blocking |
| IC-5 | PR #125 | Codex `apply_patch` is invisible to `^Bash$` matcher | Codex Pillar 7 uses Stop `changed_files()`; `completion_gate.py` is never a PostToolUse hook |
| IC-6 | PR #125 | Hook spec lives in `AGENTS.md`; skills in `.agents/skills/` | Phase 4 hooks registered in `CLAUDE.md` + `AGENTS.md` sections |
| IC-7 | PR #125 | `governor-paths.md` is the canonical governor-changing path list | Phase 4 reads this file at runtime (no inline re-declaration per IC-10) |
| IC-8 | PR #125 | Cross-tool review is multi-round Codex `gpt-5.5 --sandbox read-only` | Round 0 hung; Round 1 in progress (see §Review Rounds) |
| IC-9 | PR #125 | Governor-review-log entry required before merge (HC-3.5) | This file |
| IC-10 | PR #125 | PR template Governor-Changing section required | PR #128 body fills the section |
| IC-11 | PR #126 | Phase 2 marker lifecycle is un-decided; Phase 3 is read-only | **RESOLVED by Phase 4**: Option A (read-and-delete on Stop) + 24h defensive filter |

## New Inherited Constraints

None introduced by Phase 4. IC-11 is closed (resolved, not deferred).

Open questions carried into Phase 5 (#124):
- `.codex/state/verify-log-*.json` lifecycle — Phase 4 does opportunistic 24h cleanup of OTHER sessions' logs; Phase 5 may introduce thread-aware cleanup via `CODEX_THREAD_ID`.
- `_within_24h` helper is duplicated 4× (both `verify_first.py` files + both `completion_gate.py` files) — Phase 5 consolidates into `.agents/shared/governor/`.

## 1-week soak measurement

*(Backfill commit after 2026-05-04 — false-positive rate measurement for Pillar 7 and verify-first reminders.)*
