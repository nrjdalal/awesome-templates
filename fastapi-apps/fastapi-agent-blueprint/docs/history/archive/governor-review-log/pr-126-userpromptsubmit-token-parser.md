# PR #126 — Hybrid Harness Phase 2: UserPromptSubmit exception-token parser

- GitHub PR: <https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/126>
- Closes: #121
- Branch: `feat/121-userpromptsubmit-token-parser` → `main`
- Date range: 2026-04-26
- Cross-tool reviewer: `codex exec -m gpt-5.5 --sandbox read-only` (Round 0 + Round 1); **Round 2 performed by Claude as self-administered stand-in (Codex API credit exhausted mid-flight)**.

## Summary

Implements Phase 2 of [ADR 045](../../045-hybrid-harness-target-architecture.md): the exception-token vocabulary defined in PR #125 becomes machine-readable on both tool surfaces.

- New Claude `UserPromptSubmit` hook surface — `.claude/hooks/user-prompt-submit.sh` + `.claude/hooks/user_prompt_submit.py` + `.claude/settings.json` entry. Mirrors the existing `pre-tool-security.sh` + `pre_tool_security.py` sh-wrapper / py-helper pair.
- Codex `.codex/hooks/user-prompt-submit.py` extended (behaviour-preserving) — pre-existing safety check runs first; on `decision: block`, hook returns immediately without parsing or writing a marker. Empty / invalid stdin now fail-open (parity with Claude side; pre-Phase-2 path crashed). The fail-open transition is the only behaviour change beyond the parser block; safety logic itself is preserved verbatim.
- Recognised tokens (NFKC, leading-bracketed, case-insensitive) per IC-3 canonical regex `^\s*\[(trivial|hotfix|exploration|자명|긴급|탐색)\](?:\s|$)`. Decision payload `{matched, token, rationale_required}` shared across tools; marker file adds `ts` (ISO 8601) and uses `uuid.uuid4().hex[:12]` filename suffix to make collisions effectively impossible.
- Tests: `tests/unit/agents_shared/test_token_parser.py` (34 cases). Parity assertions across Claude/Codex parser via `importlib.util.spec_from_file_location` (Codex hook filename has hyphens). Marker schema validation. HC-1 safety-preservation smokes via subprocess. Fail-open subprocess smokes for both sides.
- Docs: `harness-asset-matrix.md` Tier 3 (count 11→13, intro sentence rewrite, Codex hook role updated, two new Claude rows, Bucket Distribution Summary 56→58 with bucket-share ~86% / ~14% retained at one decimal); `repo-facts.md` adds `.claude/state/` + `.codex/state/` row.
- Multi-commit on the branch (per PR #125 convention): `feat(claude)` + `feat(codex)` + `test` + `docs(matrix+repo-facts)` + `docs(governor-review-log)` (this entry, follow-up commit). Final file count is read from `git diff --stat main..HEAD` at merge time.

## Review Rounds

### Round 0 — Plan Review (plan stage)

- **Target**: `/Users/doo/.claude/plans/117-playful-dongarra.md` (Phase 2 plan, inherited filename from #117 plan).
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only`.
- **Final Verdict**: `still needs reinforcement` → all 11 R-points reflected back into the plan before any implementation file was touched.
- **R-points** (full text inlined in plan §"Round 0 — captured (Codex)" so a fresh session can recover the rationale; not re-duplicated here):
  - R0.1 (merge-blocking): Codex existing safety block preservation missing → HC-1 added; Codex side spec rewritten; verification checks safety preservation explicitly.
  - R0.2: hyphen filename forces `importlib.util.spec_from_file_location`; CLI smoke for end-to-end safety-preservation.
  - R0.3: SDK hook stdin schema must be confirmed before implementation.
  - R0.4: regex fixture corrections — `[trivial]hello` no-match, CRLF behaviour, leading-newline acceptance, decomposed jamo as out-of-spec.
  - R0.5: PR-number ↔ log-filename ordering (HC-3) — scratch first, rename after `gh pr create`.
  - R0.6 (merge-blocking): self-application proof skill mismatch — `/review-architecture` + `/sync-guidelines` are the proof; `/review-pr` is gate-on-gate.
  - R0.7: verification expanded (marker schema, state dir auto-create, empty stdin, invalid JSON).
  - R0.8: "additive only" → "behaviour-preserving extension" (Codex side semantics).
  - R0.9: cold-start reads expanded to 15 items.
  - R0.10: new-session start prompt added at plan top.
  - R0.11: stale plan filename `117-playful-dongarra.md` clarified.

### Round 1 — Implementation Review

- **Target**: 4-commit working tree before push (`.claude/hooks/user_prompt_submit.py`, `.claude/hooks/user-prompt-submit.sh`, `.codex/hooks/user-prompt-submit.py` extension, `tests/unit/agents_shared/test_token_parser.py`, `.claude/settings.json`, `.gitignore`). Pytest 30/30 PASSED at submission time.
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only`.
- **Final Verdict**: `minor fixes recommended` (no merge blockers). 5 review angles flagged as needing follow-up; 4 actionable + 1 deferred to Phase 4.

> Original reviewer verdict (ko, verbatim): 보완 필요
> English normalised verdict: needs follow-up.
- **R-points** (all addressed or explicitly deferred):
  - **R1.1** (Top 1) `harness-asset-matrix.md` Tier 3 not yet reflecting the new Claude hooks and the Codex role change. → **Applied**: Tier 3 11→13, Codex hook role updated, Bucket Distribution Summary 56→58, Counting note + Update Log refreshed (commit 4 `docs(governor): register Phase 2 hooks in matrix + repo-facts`).
  - **R1.2** (Top 2) marker filename uses `int(time.time() * 1000) % 1_000_000` — millisecond modulo collisions possible if two hook invocations land in the same UTC-second. → **Applied**: both sides switched to `uuid.uuid4().hex[:12]` suffix (48-bit random).
  - **R1.3** (Top 3) marker lifecycle ill-defined — Phase 4 must commit to read-and-delete vs. age-based filter vs. session-id correlation. → **Deferred to Phase 4** as **IC-11** (see Inherited Constraints below). Issue #123 body updated with the carry-forward link.
  - **R1.4** (Top 4) test coverage gaps: Claude empty-stdin / invalid-JSON subprocess smokes missing; Codex marker JSON parse not validated; HC-1 marker absence relies on manual smoke. → **Applied**: 4 new tests (`test_claude_hook_empty_stdin_fail_open`, `test_claude_hook_invalid_json_fail_open`, `test_codex_hook_empty_stdin_fail_open`, `test_codex_hook_invalid_json_fail_open`) plus `test_codex_marker_written_on_match` upgraded to JSON-parse validation. Total fixtures 30 → 34.
  - **R1.5** (Top 5) Codex side stdin asymmetry — Claude fail-opens, Codex crashes. Issue #117 Non-Goal "false-positive blocking" suggests symmetry. → **Applied**: Codex `main()` now reads raw stdin, returns 0 on empty / `JSONDecodeError` / non-dict payload before the safety check runs. (See "Self-Coherence Note" below for the migration-safety reasoning.)

### Round 2 — Cross-Check on Round 1 (gate-on-gate, Claude self-administered stand-in)

- **Target**: post-R1-fix working tree (4 commits + R1 deltas applied). Pytest 34/34 PASSED.
- **Reviewer**: **Claude** (`gpt-5.5 --sandbox read-only` Codex run was attempted; the user reported mid-flight that Codex credit had been exhausted and asked Claude to self-administer a fresh check; the running Codex job and its monitor were stopped; Claude performed Round 2 as a self-administered cross-check using **PR #125 Round 7 R7.1 ~ R7.7 patterns** as the audit framework, since those patterns are the most recent record of *what self-review tends to miss*).

> Original user/owner statement (ko, verbatim): "codex가 크레딧이 모두 소모돼서 클로드가 자체적으로 다시한번 확인해봐야할거 같아"
> English normalised meaning: "Codex credit is exhausted, so Claude needs to do another self-administered check."
- **Final Verdict**: `minor fixes recommended (no merge blockers)`. 2 open R-points; both close in the same commit set as this entry.
- **Substitution caveat**: Self-administered Round 2 cannot replicate the cross-tool review's structural value (an independent reviewer with a different reasoning trace catching what Claude's reasoning trace systematically misses). The user's `feedback_codex_cross_review.md` memory captures this lesson explicitly. The substitution is recorded here so a future reader can re-run Round 2 with Codex once credit returns and compare findings; if the comparison surfaces additional R-points, those land as a follow-up commit on this same log entry per the log-only-backfill exclusion in [`governor-paths.md`](../../../ai/shared/governor-paths.md).
- **R-points**:
  - **R2.1** (R7.6 pattern) IC-11 carry-forward into Phase 4 issue body had not landed at Round-2 time. → **Applied** in the same commit set as this entry: `gh issue edit 123` injects an "Inherited Review Constraints" note linking this entry and citing IC-11.
  - **R2.2** (R7.2 / R7.3 pattern) "Behaviour-preserving extension" framing tension — R1.5 introduced fail-open for empty / invalid stdin, which is technically a behaviour change from the pre-Phase-2 crash. → **Applied** here (this Self-Coherence Note): the safety-block contract itself is preserved verbatim; only the corner-case crash path is replaced by `return 0`. Empty / invalid stdin cannot carry a destructive prompt because the prompt field is unreachable until JSON parsing succeeds, so fail-open does not weaken IC-1.

#### Round-2 Evidence (separated from Findings per R7.1)

These OK observations support the verdict; they are not findings.

- §1~§9 architecture checklist all N/A: no `src/` change.
- Bucket-share consistency: denominator 56→58, Keep 48→50, Overlay 8 unchanged. ~86% / ~14% rounding holds (50/58 = 86.21%, 8/58 = 13.79%). ADR 045 §D4 / `target-operating-model.md` §7 / `migration-strategy.md` §6 mention `~86% / ~14%` — no edit needed (R7.4 regression avoided).
- Tier 3 hook count arithmetic: 5 Claude shell + 2 Claude py + 6 Codex py = 13. Counting note `Tier 0=9 + Tier 1=17 + Tier 2=14 + Tier 3=13 + Tier 4=6 = 59; Total 58 excludes .claude/settings.local.json` — internally consistent.
- Stale-count residue check: `grep -n "\b56\b" docs/ai/shared/harness-asset-matrix.md` returns only the Update Log line documenting the 56→58 transition (intended as historical evolution record); no stale count elsewhere.
- HC-1 still in force after R1.5 fail-open: empty / invalid stdin path returns 0 before PROMPT_RULES, but those paths cannot carry a destructive prompt, so safety surface is unchanged.
- chmod +x on `.claude/hooks/user-prompt-submit.sh` preserved across `git add` (mode `100755` confirmed via `git ls-files --stage`).
- Pytest 34/34 PASSED. Manual smoke (Korean token, CRLF, dangerous-prompt-with-token-prefix block + no marker) all green.
- pre-commit hooks (ruff format / ruff check / detect-secrets / mypy / domain-import / entity-pattern) green on every commit.
- governor-paths.md Tier B `.claude/**` + `.codex/**` already covers the new files; no edit needed there (R5.1 / R5.2 regression avoided).

### Round 3 — (skipped)

Round 2 final verdict was `minor fixes recommended (no merge blockers)` and both R2 R-points close in the same commit set as this entry. No conditional Round 3 needed per the plan §"Cross-Tool Review Cadence" rule. If a future Codex re-run of Round 2 (after credit returns) surfaces additional R-points, that becomes Round 3 and lands in this same log entry as a backfill commit per the log-only-backfill exclusion.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | R0.1: Codex safety block preservation missing | Fixed | HC-1 added and verification checks safety preservation. |
| Round 0 | R0.2: hyphen filename import and CLI smoke risk | Fixed | Import strategy and smoke coverage reflected into the plan. |
| Round 0 | R0.3: hook stdin schema uncertainty | Fixed | SDK schema confirmation required before implementation. |
| Round 0 | R0.4: regex fixture corrections | Fixed | Fixtures covered no-match, CRLF, leading newline, and decomposed-jamo scope. |
| Round 0 | R0.5: PR number and log filename ordering | Fixed | Scratch-first then rename-after-PR workflow adopted. |
| Round 0 | R0.6: self-application proof skill mismatch | Fixed | `/review-architecture` and `/sync-guidelines` became required proof. |
| Round 0 | R0.7: verification gaps | Fixed | Marker schema, state directory, empty stdin, and invalid JSON checks added. |
| Round 0 | R0.8: additive-only wording overclaim | Fixed | Reframed as behaviour-preserving extension. |
| Round 0 | R0.9: cold-start reads too narrow | Fixed | Cold-start reads expanded. |
| Round 0 | R0.10: missing new-session start prompt | Fixed | Plan gained the start prompt. |
| Round 0 | R0.11: stale plan filename | Fixed | Filename clarified. |
| Round 1 | R1.1: harness-asset-matrix Tier 3 drift | Fixed | Matrix and repo-facts updated for Phase 2 hooks. |
| Round 1 | R1.2: marker filename collision risk | Fixed | Both tools switched to UUID suffixes. |
| Round 1 | R1.3: marker lifecycle unspecified | Deferred-with-rationale | Deferred explicitly to Phase 4 as IC-11 and linked into issue #123. |
| Round 1 | R1.4: subprocess and marker parse test gaps | Fixed | Four fail-open tests and JSON-parse validation added. |
| Round 1 | R1.5: Codex stdin fail-open asymmetry | Fixed | Codex hook now returns 0 on empty, invalid, or non-dict stdin. |
| Round 2 | R2.1: IC-11 carry-forward missing from Phase 4 issue | Fixed | Issue #123 body gained the inherited-constraint note. |
| Round 2 | R2.2: behaviour-preserving framing tension | Fixed | Self-Coherence Note explains the safety-preserving crash-path change. |

## Inherited Constraints (carried forward to Phase 3~5 and any future governor-changing PR)

This entry inherits IC-1 ~ IC-10 from [`pr-125-hybrid-harness-target-architecture.md`](pr-125-hybrid-harness-target-architecture.md) verbatim and adds one new constraint:

- **IC-11** (Phase 2 R1.3 deferral) **Marker lifecycle is unspecified at Phase 2.** The Phase 2 hooks write `.claude/state/exception-token-{ts}-{uuid}.json` / `.codex/state/...` markers when an exception token is recognised, but the markers accumulate across sessions with no consumed / age / session-id field. Phase 4 (#123) **must commit to a lifecycle policy** before promoting the completion gate from informational to harder reminder. Candidate policies (not exhaustive): (a) read-and-delete by the completion-gate hook on each Stop; (b) age-based filter (e.g. only consider markers within the last N minutes); (c) session-id correlation (require `session_id` field added to the marker schema and matched against the current session). Whichever Phase 4 picks, the marker schema may grow new fields — Phase 5 (#124) will then consolidate the writer in `.agents/shared/governor/`. Until Phase 4 lands, users may delete `.claude/state/*.json` and `.codex/state/*.json` manually (both are gitignored).

### IC-11 Resolution (closed by Phase 4 / PR #128)

Phase 4 commits to **Option A — read-and-delete on Stop** with opportunistic 24h cleanup:
- Stop hook (both Claude and Codex sides) reads the latest marker, applies `[exploration]`/`[탐색]` silence to its own segments, then deletes ALL `exception-token-*.json` files in the state dir.
- `read_latest_token_marker` skips markers older than 24h (defensive against Stop-failure leftovers).
- Marker schema unchanged from Phase 2 (no `session_id` field added; PR #126 schema remains valid).
- Rationale: Stop is the sole consumer-deleter; PostToolUse readers (Phase 3 Claude) and Stop pre-segment readers (Phase 3 Codex) all run before Stop's delete, so within one prompt all reads see the same file.
- Open question absorbed by Phase 5 (#124): should `.codex/state/verify-log-*.json` cleanup also be Stop-driven, or thread-aware via `CODEX_THREAD_ID` lifecycle? Phase 4 only does opportunistic 24h cleanup of *other* sessions' logs.

## Self-Application Proof

PR #126 is governor-changing. The governor's own self-review and completion-gate steps are recorded here.

### `/review-architecture all` (manual scan, structural only — no `src/` changes in this PR)

```
Scope
- Target: all (changed surface of feat/121-userpromptsubmit-token-parser, final file count read from `git diff --stat main..HEAD` at merge time)
- Audited domains: none (no src/ change)
- Important exclusions: src/ tree (untouched in this PR)

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/governor-paths.md
- docs/ai/shared/governor-review-log/pr-125-hybrid-harness-target-architecture.md (IC-1 ~ IC-10)

Findings
- none

Drift Candidates
- target: docs/ai/shared/governor-review-log/pr-{NNN}-userpromptsubmit-token-parser.md
  reason: Per IC-8 + IC-10 + HC-3, governor-changing PR must add a new entry whose filename's {NNN} equals the PR number.
  auto-fix: yes (this commit)
  sync-required: true
- target: docs/ai/shared/governor-review-log/README.md Index
  reason: New PR row needed.
  auto-fix: yes (this commit)
  sync-required: true
- target: docs/ai/shared/repo-facts.md
  reason: `.claude/state/` + `.codex/state/` are new gitignored governance state surfaces.
  auto-fix: yes (commit 4 already applied)
  sync-required: true (closed by commit 4)
- target: PR template Governor-Changing PR section
  reason: must be filled in PR body (Round-7 R7.7).
  auto-fix: yes (already applied during gh pr create)
  sync-required: true (closed)

Next Actions
- Apply this commit (governor-review-log entry + Index row).
- Edit issue #123 body with IC-11 carry-forward link.
- Wait for review / merge.

Completion State
- complete on architecture surface (no src/ findings); drift candidates closed by this commit + post-PR-create steps.

Sync Required
- true (closed by this commit)
```

### `/sync-guidelines` (manual scan against drift-checklist 1A~1D)

```
Mode: review follow-up

Input Drift Candidates: 6 consumed
- governor-review-log/pr-126-userpromptsubmit-token-parser.md (this entry)
- governor-review-log/README.md Index row
- repo-facts.md `.claude/state/` + `.codex/state/` row
- harness-asset-matrix.md Tier 3 update (already applied in commit 4)
- PR template Governor-Changing PR section (already filled in PR body)
- IC-11 (Phase 4 marker lifecycle) carry-forward (R1 Top R3, deferred to Phase 4)

project-dna: unchanged (no code-pattern shift; project-dna §0~§14 still accurate)

AUTO-FIX:
- harness-asset-matrix.md Tier 3 row count 11→13 + 2 new Claude rows + Codex hook role updated; intro sentence + Counting note + Bucket Distribution Summary refreshed; Update Log records the 56→58 transition.
- repo-facts.md adds row for `.claude/state/` + `.codex/state/`.
- governor-review-log/pr-126-userpromptsubmit-token-parser.md created (this entry) with: Summary, Review Rounds 0~2 (each with explicit Final Verdict), Inherited Constraints (IC-1~IC-10 link + new IC-11), Self-Application Proof.
- governor-review-log/README.md Index row added.
- PR body Governor-Changing PR section filled (during gh pr create).

REVIEW:
- IC-11 (proposed and adopted) — Phase 4 marker lifecycle. Carried into issue #123 body via gh issue edit. Policy choice (read-and-delete vs age-based vs session-id) deferred to Phase 4 design.

Remaining: none

Next Actions:
- Re-run /review-pr (or its manual equivalent) on the PR head once GitHub picks up the additional commit. Treat the governor as having satisfied its own quality gate for this PR.
- Phase 3 (#122) and Phase 4 (#123) issues already exist; both inherit IC-1 ~ IC-11 from this entry.
```

### `/review-pr` (Claude-side completion gate)

```
Scope
- PR: #126 — Hybrid Harness Phase 2: UserPromptSubmit exception-token parser (Closes #121)
- Base/Head: main / feat/121-userpromptsubmit-token-parser
- Affected domains: process/governance layer only (no src/ change)
- Changed files: 9 (counts read from `git diff --stat` at merge time)

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/security-checklist.md
- docs/ai/shared/governor-paths.md
- docs/ai/shared/governor-review-log/pr-125-hybrid-harness-target-architecture.md
- docs/ai/shared/migration-strategy.md §1 Phase 2 acceptance

Findings
- none

Drift Candidates
- none (all closed in this commit set; matrix + repo-facts updated in commit 4; this entry + Index row + issue #123 edit close the rest)

Next Actions
- User reviews the PR on GitHub UI and merges.
- Phase 3 (#122) picks up via Inherited Review Constraints IC-1 ~ IC-11.

Completion State
- Claude-side completion gate: PASSED.

Sync Required
- false
```

## Recommendations Carried Forward

For Phase 3~5 implementations, link this entry's `Inherited Constraints` block from each PR description. In particular:

- Phase 3 (#122) verify-first adapter must read the exception-token marker as the natural escape signal (e.g. `[exploration]` skips the verification reminder entirely).
- Phase 4 (#123) completion gate must commit to the marker lifecycle policy described in IC-11 before promoting from informational to harder reminder.
- Phase 5 (#124) shared governor module must absorb the parser, the marker writer, and the lifecycle policy chosen by Phase 4.
- Future governor-changing PRs that change the regex / vocabulary / payload schema must re-run cross-tool review (Round 0 + at least Round 1) and add their own entry; the log-only-backfill exclusion does **not** apply to schema changes.
