# PR #127 — Hybrid Harness Phase 3: verify-first adapters (Claude PostToolUse + Codex Stop)

- GitHub PR: <https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/127>
- Closes: #122
- Branch: `feat/122-verify-first-adapters` → `main`
- Date range: 2026-04-27
- Cross-tool reviewer: `codex exec -m gpt-5.5 --sandbox read-only` (Round 0); Round 1 / Round 2 in progress.

## Summary

Implements Phase 3 of [ADR 045](../../045-hybrid-harness-target-architecture.md): adds informational verify-first reminders to both harnesses so the `verify` step of the Default Coding Flow is not silently skipped.

- **Claude side** — new `PostToolUse Edit|Write` sibling hook pair (`.claude/hooks/verify-first.sh` + `.claude/hooks/verify_first.py`). On every `.py` edit, reads the latest Phase 2 marker from `.claude/state/exception-token-*.json`; emits bilingual stderr reminder unless the token is `[exploration]`/`[탐색]`. Never blocks (HC-3.3). Fail-open on all error paths (HC-3.6).
- **Codex side** — Stop hook segment merge pattern (IC-2). New library module `.codex/hooks/verify_first.py` imported by the existing `stop-sync-reminder.py` (no new hooks.json entry). `.codex/hooks/post-tool-format.py` extended with a verify-log writer that records `pytest` / `make test` / `make demo[-rag]` / `alembic upgrade` invocations as JSONL to `.codex/state/verify-log-{session_id}.json`. `stop-sync-reminder.py` refactored to a segments list (IC-2 single output) and appends a verify-first segment when changed `.py` files exist and the current-session verify-log is absent or stale.
- Phase 2 `[exploration]`/`[탐색]` markers silence both adapters. Read-only on Phase 2 markers (IC-11; lifecycle is Phase 4 #123's responsibility). Informational only — never blocks commit or Stop (HC-3.3).
- Tests: `tests/unit/agents_shared/test_verify_first.py` (28 cases). String-equality of `REMINDER_TEXT` across tools (IC-2 cornerstone). Silence on `[exploration]`/`[탐색]` markers (both Claude and Codex). Non-silence on `[trivial]`/`[hotfix]`. Non-Python edits silent. Codex `should_remind()` marker silence direct tests (R1.3). Codex verify-log freshness (recent → silent; stale → remind). Cross-session silence prevention (R0.2 + R1.1 CODEX_THREAD_ID). Fail-open smokes. Marker read idempotency (IC-11). 7-case parametrised verify-log writer pattern suite. `tool_input: null` fail-open regression (R2.3).
- Docs: `harness-asset-matrix.md` Tier 3 +3 rows (Total 58→61, Bucket Distribution updated); `repo-facts.md` registers `.codex/state/verify-log-{session_id}.json` surface.

R0 reinforcement applied before any implementation file was touched: import fail-open (R0.1), current-session-only verify-log to defeat cross-session silence (R0.2), subsecond `ts_epoch_ns` freshness comparison (R0.3), top-level fail-open in `post-tool-format.py` (R0.4), Codex marker silence parity tests + test name correction (R0.5).

## Review Rounds

### Round 0 — Plan Review (plan stage)

- **Target**: `/Users/coursemos/.claude/plans/122-playful-snail.md` (Phase 3 plan, §1~§15 + §16 R0 Reinforcement Log).
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only` (Codex CLI, read-only sandbox).
- **Final Verdict**: `still needs reinforcement` → all 5 R-points (R0.1~R0.5) reflected into plan §16 "R0 Reinforcement Log" before implementation files were created.
- **R-points** (full text in plan §16; abbreviated here):
  - **R0.1** (merge-blocking): `import verify_first` at module level in `stop-sync-reminder.py` — if import fails, entire Stop hook crashes, violating HC-3.6. → **Applied**: import moved inside `with contextlib.suppress(Exception):` block; existing sync-reminder behaviour preserved on ImportError.
  - **R0.2** (merge-blocking): `latest_verify_log_ts()` originally globbed all `verify-log-*.json` files → a prior Codex session's `pytest` run could silence the current session (cross-session contamination). → **Applied**: reads only `verify-log-{session_id()}.json` (current session); `session_id()` uses `CODEX_SESSION_ID or f"{ppid}-{pid}-{start_ns_hex}"` to defeat PPID collision across rapid Codex re-invocations. Renamed to `current_session_latest_verify_ns()`.
  - **R0.3** (merge-blocking): ISO 8601 string comparison truncated to 1-second precision → false-negative when `pytest` and `.py` edit land in the same wall-clock second. → **Applied**: JSONL stores `ts_epoch_ns: int` (`time.time_ns()`); mtime comparison uses `Path.stat().st_mtime_ns`; `should_remind()` compares `verify_ns < py_mtime_ns` (epoch-ns integers).
  - **R0.4** (merge-blocking): `post-tool-format.py` had no top-level fail-open — `json.load(sys.stdin)` could crash on invalid stdin now that the hook has Phase 3 verify-log writer responsibility. → **Applied**: entire body wrapped in `def main()` with `try/except (json.JSONDecodeError, ValueError)` around stdin parse; both format and record branches use `with contextlib.suppress(Exception):`.
  - **R0.5** (advisory): test name `test_codex_silent_when_verify_log_older_than_py_mtime` backwards (assert is `True` = reminds); Codex marker silence parity tests missing; `git status --porcelain` wording vs `_shared.changed_files()` wording. → **Applied**: test renamed `test_codex_reminds_when_verify_log_older_than_py_mtime`; `test_codex_silent_on_exploration_marker` + `test_codex_silent_on_korean_탐색_marker` added; wording uses function name.

### Round 1 — Implementation Review

- **Target**: 6-commit working tree (commits d143491, 9d88064, 000893f, 2283dad, 689f1e5, 0f02e8a). Pytest 25/25 PASSED. PR #127 open.
- **Reviewer**: Claude Code (cross-session review via empirical env var probe + code inspection).
- **Final Verdict**: `minor fixes recommended` → 3 R-points surfaced (R1.1~R1.3); all applied in commit `0f02e8a`.
- **R-points** (all resolved):
  - **R1.1** (blocking): `session_id()` originally preferred `CODEX_SESSION_ID`, but empirical `python3 -c` probe inside the Codex sandbox confirmed `CODEX_SESSION_ID` is **not injected** by Codex CLI. The actual env var is `CODEX_THREAD_ID` (stable across all hook processes in a session). → **Applied**: `session_id()` priority chain updated to `CODEX_THREAD_ID → CODEX_SESSION_ID → ppid-pid-startns`. Tests updated to `monkeypatch.setenv("CODEX_THREAD_ID", ...)` + `monkeypatch.delenv("CODEX_SESSION_ID", raising=False)`.
  - **R1.2** (blocking): `post-tool-format.py` originally used `payload.get("tool_input", {})` which returns `None` when the key is present but explicitly `null` in the JSON payload, causing `AttributeError: 'NoneType' object has no attribute 'get'`. → **Applied**: changed to `(payload.get("tool_input") or {}).get("command", "")` + added outer broad `except Exception: return 0` (R0.4 strengthened).
  - **R1.3** (advisory): Direct unit test that Codex `should_remind()` respects `[exploration]`/`[탐색]` marker silence was missing (only Claude side tested). → **Applied**: `test_codex_silent_on_exploration_marker_should_remind` + `test_codex_silent_on_korean_탐색_marker_should_remind` added; test count 25 → 27.

### Round 2 — Cross-Check (gate-on-gate)

- **Target**: 9-commit working tree (commits d143491 ~ 8bbf5a5). R1.1~R1.3 applied. Self-Application Proof committed.
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only` (Codex CLI, read-only sandbox).
- **Final Verdict**: `minor fixes recommended` → 3 R-points surfaced (R2.1~R2.3); all applied in next backfill commit.
- **R-points** (all resolved):
  - **R2.1** (doc drift): `harness-asset-matrix.md:633` described `session_id()` as `CODEX_SESSION_ID or fallback` — stale after R1.1 changed priority to `CODEX_THREAD_ID → CODEX_SESSION_ID → ppid-pid-startns`. → **Applied**: description updated to match actual priority chain.
  - **R2.2** (log accuracy): `pr-127-verify-first-adapters.md:16` Summary said `25 cases` — stale after R1.3 brought count to 27. → **Applied**: updated to `27 cases` (R2.3 then added one more → `28 cases`).
  - **R2.3** (optional test): `post-tool-format.py` `tool_input: null` path tested only by code inspection; no subprocess regression test. → **Applied**: `test_codex_post_tool_format_null_tool_input_fail_open` added; 28 tests total, all pass.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | R0.1: Stop hook import fail-open risk | Fixed | Import moved inside a suppressed block. |
| Round 0 | R0.2: verify-log cross-session contamination | Fixed | Codex reads only the current session log. |
| Round 0 | R0.3: one-second timestamp precision false-negative | Fixed | Verify log stores and compares epoch nanoseconds. |
| Round 0 | R0.4: post-tool-format top-level fail-open missing | Fixed | Main path wrapped with fail-open parsing and suppressed record branches. |
| Round 0 | R0.5: test naming and marker-silence parity gaps | Fixed | Test names corrected and Codex exploration-marker silence tests added. |
| Round 1 | R1.1: CODEX_THREAD_ID priority | Fixed | Session-id priority now uses CODEX_THREAD_ID before fallback aliases. |
| Round 1 | R1.2: `tool_input: null` AttributeError | Fixed | Command extraction handles explicit null and adds fail-open regression coverage. |
| Round 1 | R1.3: missing direct Codex exploration-marker tests | Fixed | Direct `should_remind` marker-silence tests added. |
| Round 2 | R2.1: stale session-id priority in matrix | Fixed | Matrix wording updated to current priority chain. |
| Round 2 | R2.2: stale test count in log summary | Fixed | Summary updated as test count changed. |
| Round 2 | R2.3: missing subprocess regression for null tool input | Fixed | Subprocess fail-open regression test added. |

## Inherited Constraints

Carried from prior governor-changing PRs (no new IC introduced by Phase 3 — by design):

| IC | Source | Rule | Phase 3 application |
|---|---|---|---|
| IC-1 | PR #125 | Shared rules live in `AGENTS.md` + `docs/ai/shared/` | Phase 3 hook spec derived from `AGENTS.md` Default Flow |
| IC-2 | PR #125 | Single Stop event output (Codex) | `stop-sync-reminder.py` segments list → single `{"systemMessage": ...}` |
| IC-3 | PR #125 | Token regex canonical form in `AGENTS.md` | Phase 3 reads Phase 2 markers; no new token vocab |
| IC-4 | PR #125 | Exception tokens do not override Absolute Prohibitions | Phase 3 is informational only; no override path |
| IC-5 | PR #125 | Codex `apply_patch` is invisible to `^Bash$` matcher | Codex reminder uses Stop changed-files (`_shared.changed_files()`); verify-log writer on PostToolUse Bash only records, never emits |
| IC-6 | PR #125 | Hook spec lives in `AGENTS.md`; skills in `.agents/skills/` | Phase 3 hooks registered in `CLAUDE.md` + `AGENTS.md` sections |
| IC-7 | PR #125 | `governor-paths.md` is the canonical governor-changing path list | No new paths added in Phase 3 |
| IC-8 | PR #125 | Cross-tool review is multi-round Codex `gpt-5.5 --sandbox read-only` | Round 0 completed; Rounds 1/2 in progress |
| IC-9 | PR #125 | Governor-review-log entry required before merge (HC-3.5) | This file — log-only-backfill commit 5 |
| IC-10 | PR #125 | PR template Governor-Changing section required | PR #127 body fills the section |
| IC-11 | PR #126 | Phase 2 marker lifecycle is un-decided; Phase 3 is read-only | `read_latest_token_marker()` reads only; no delete/mutate anywhere in Phase 3 |
| HC-1 | PR #126 | Codex safety-block-first; parser runs only after safety pass | Phase 3 hooks all fail-open (HC-3.6); safety hook path unchanged |

## Self-Application Proof

Executed in same PR #127 review session (2026-04-27).

### `/review-architecture all`

```
Scope: All 3 active domains (user, classification, docs) + _core
Sources Loaded: AGENTS.md, project-dna.md, architecture-review-checklist.md,
  security-checklist.md
Findings:
  [OK] §1 Layer Dependency — clean in all domains
  [OK] §2 Auth — JWT not yet implemented (project-wide known gap per project-dna)
  [OK] §3 Conversion — DTO ↔ Model patterns correct throughout
  [OK] §4 Repository — no Model objects leak outside Repositories
  [OK] §5 Test Coverage — all 3 domains have unit + integration + e2e baselines
    [MEDIUM] pre-existing: user admin unit tests missing (src/user/interface/admin/)
    [MEDIUM] pre-existing: classification admin unit tests missing (src/classification/interface/admin/)
  [OK] §6 Infrastructure DI — Selector/lazy-factory pattern correct; AWS + admin extras guarded
  [OK] §7 Error Translation — error_mapper ACL established; domain exceptions propagate correctly
  [OK] §8 Hook surface — governance-only PR; src/ untouched; hook changes reviewed separately
  [OK] §9 Migration — no new migrations in this PR
Drift Candidates:
  - docs/ai/shared/migration-strategy.md §7: #NNN → actual issue numbers
    auto-fix: yes  sync-required: optional (advisory only)
Next Actions: Run /sync-guidelines to fix migration-strategy.md §7 (auto-fixable).
Completion State: complete (no open findings; 2 pre-existing MEDIUM admin test gaps pre-date this PR)
Sync Required: false
```

### `/sync-guidelines`

```
Mode: drift-candidate follow-up (from /review-architecture all drift candidate)
Input Drift Candidates:
  - docs/ai/shared/migration-strategy.md §7: #NNN placeholder → actual issue numbers
  - .claude/rules/project-status.md: Phase 2 + Phase 3 entries missing; Last synced stale
project-dna: no changes required
AUTO-FIX:
  - migration-strategy.md §7: #NNN → #121/PR#126, #122/PR#127, #123, #124 (applied)
  - project-status.md: Phase 2 (#121/PR#126) + Phase 3 (#122/PR#127) rows added;
    Last synced updated to 2026-04-27 (applied)
REVIEW: none
Remaining: none
Next Actions: commit sync changes as log-only-backfill commit
  → committed as 1109839 "docs(governor): sync migration-strategy §7 issue numbers + project-status Phase 3 entry"
```

### `/review-pr 127`

```
Scope: PR #127 Phase 3 verify-first adapters — 11 changed files, governance-only
Sources Loaded: AGENTS.md, project-dna.md, architecture-review-checklist.md,
  security-checklist.md, drift-checklist.md §1D, PR #125 + PR #126 governor-review-log entries
Findings:
  [OK][BLOCKING-class] HC-3.6 fail-open: all 5 surfaces (verify-first.sh, verify_first.py Claude,
    post-tool-format.py R0.4, stop-sync-reminder.py R0.1, verify_first.py Codex library)
  [OK][BLOCKING-class] IC-5: Codex reminder from Stop only; post-tool-format records only
  [OK][BLOCKING-class] IC-11: read_latest_token_marker() read-only in both helpers
  [OK][BLOCKING-class] HC-3.3: informational only, exit 0 / return 0 unconditional
  [OK][BLOCKING-class] IC-2: segments list → single systemMessage print
  [OK][HIGH] R1.1 CODEX_THREAD_ID priority; R1.2 null tool_input; R1.3 Codex marker silence tests
  [OK][MEDIUM] REMINDER_TEXT string equality + test assertion; R0.2 cross-session; R0.3 ts_epoch_ns
  [OK][MEDIUM] 28 test cases; subprocess fail-open smokes; IC-11 marker idempotency; R1.2 null regression
  [OK][LOW] drift-checklist §1D: pr-127 filename match; README index row; matrix + repo-facts
  [NOTE] governor-review-log §Round1 + §Self-Application Proof pending → filled by this backfill commit
Drift Candidates:
  - migration-strategy.md §7 #NNN: FIXED by /sync-guidelines run (committed 1109839)
  - project-status.md Phase 2+3 entries: FIXED by /sync-guidelines run (committed 1109839)
Next Actions:
  1. Commit this Self-Application Proof update (backfill commit)
  2. Run Round 2 Codex cross-tool review
  3. Merge after Round 2 verdict
Completion State: complete with no open findings; drift candidates resolved and committed
Sync Required: true (docs/ai/shared/ in diff; resolved by /sync-guidelines run 1109839)
```

## New Inherited Constraints

None introduced by Phase 3 (by design — Phase 3 is informational only, no new lifecycle decisions).

Open questions carried into Phase 4 (#123):
- IC-11 marker lifecycle (read-and-delete vs. age-based filter vs. session-id correlation) — same open question as PR #126.
- `.codex/state/verify-log-{session_id}.json` lifecycle — shares IC-11 open question; Phase 4 decides both at once.

## 1-week soak measurement

*(Backfill commit after 2026-05-04 — false-positive rate measurement: reminder fires / total reminder events where silence would have been correct)*
