# PR #132 — Tier 1 Language Policy + Korean Prose Cleanup + 3-Layer Enforcement

> Issue: [#131](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/131)
> Pull Request: [#132](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/132)
> ADR: ADR 045 (constraints inherited)

## Summary

Lands AGENTS.md `## Language Policy` declaring English as the
intended writing language for Tier 1 paths (governance / harness /
contributor-facing files) while matching machine enforcement to the
observed failure mode: Korean (Hangul) prose leaks. Translates 83
Korean prose lines across 19 Tier 1 files to English. Adds 3-layer
enforcement (AI behaviour rule + pre-commit hook + CI execution via
the existing `architecture` job) so Korean chat language driving
Korean writes through `/sync-guidelines` is blocked before merge.

The bilingual escape-token vocabulary
(`[trivial]`/`[자명]`, `[hotfix]`/`[긴급]`,
`[exploration]`/`[탐색]`) remains the only Korean strings allowed
in Tier 1 paths, scoped per-file in
`tools/check_language_policy.py` so a token literal cannot launder
Korean prose elsewhere on the same line.

`governor-review-log/*` entries (pr-125 through pr-130) are
backfilled to English with explicit 3-category provenance
preservation: original user/owner statement, original reviewer
verdict, historical Korean excerpt. Each Korean line is recorded
verbatim as a `> Original ... (ko, verbatim):` blockquote
followed by an English normalised line, so audit-trail provenance
survives the translation.

This PR is **governor-changing** because it edits AGENTS.md
(Tier A), `docs/ai/shared/**` (Tier A), `docs/history/**` (Tier A),
`.claude/**` (Tier B), `.codex/**` (Tier B), `.agents/**` (Tier B),
and `governor-paths.md` (Tier A — Tier A list expanded to include
`CLAUDE.md`, and the `pre-commit-config.yaml` typo fixed).
Therefore this self-application entry is mandatory per
[`governor-paths.md`](../../../ai/shared/governor-paths.md).

## Review rounds

Five rounds of cross-tool review with Codex CLI before
implementation, plus a pre-implementation dry run.

### Round 1 — contrarian review of two-policy proposal

- **Target**: initial owner proposal of two policies — (A) English-only
  for harness artifacts, (B) Claude chat replies follow user's
  message language.
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only`.
- **Final Verdict**: `4-tier audience-tiered policy` proposed.
- **R-points** surfaced: A and B are not independent; "dominant
  language" is not a robust heuristic; chat language cannot be
  reliably enforced; `/sync-guidelines` itself was the leak vector;
  forcing English may degrade owner velocity; review-log handling
  needs explicit policy; mechanical checks must be path-bounded.
- **Outcome**: Codex proposed a 4-tier audience model — Canonical
  (English-only), Runtime chat (user-local), Informal (mixed
  allowed), Localized UX (override permitted).

### Round 2 — self-critique of the 4-tier proposal

- **Target**: Round 1's 4-tier proposal under solo-repo assumption.
- **Reviewer**: same Codex thread, asked to find concrete failure
  modes in its own output.
- **Final Verdict**: 4-tier overengineered for solo repo; reduce
  to MVP `1-layer CI grep on Tier 1, defer the rest`.
- **R-points** surfaced: solo-repo bar; tier-boundary friction;
  promotion-rule operational gaps; chat-language detection is
  heuristic-only; bulk-migration cost; 3-layer enforcement vs
  friction; the original failure mode points to Policy A leverage
  over Policy B; `<!-- ko:rationale -->` HTML-comment salvage
  option for owner velocity.

### Round 3 — context reset under team scale

- **Target**: Round 1+2 conclusions reconsidered under updated
  context: 5 teammates joining, external OSS contributors
  expected, all using Claude Code + Codex CLI in parallel,
  immediately post-merge.
- **Reviewer**: same Codex thread, given the corrected context.
- **Final Verdict**: Round 2 conclusions B / C / D / F / G
  overturned. Reinstate 4-tier with tightened Tier 3 (review-log
  no longer free-mixed), single-PR cleanup before onboarding,
  3-layer enforcement, English backfill of review-log entries.
- **R-points**: chat-language policy is UX, not enforcement;
  AI-multi-use × team-scale = 5x leak surface; foreign
  contributors invalidate the `<!-- ko:rationale -->` salvage;
  governor-review-log without backfill leaves an unreadable
  precedent for new contributors.

### Round 4 — implementation plan critical review

- **Target**: Plan agent's draft for the 4-commit single PR.
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only`.
- **Final Verdict**: `pygrep dropped, Python checker required`;
  test breakage scope expanded; provenance categories tripled;
  draft-PR workflow imposed; literal `<!-- ko:rationale -->`
  removed from policy text in favour of generic
  hidden-rationale prohibition; `governor-paths.md` L37 typo
  added to scope.
- **R-points** (all addressed in commits 1-4):
  - **R4.1**: pygrep cannot encode the per-file token allowlist
    + provenance prefixes + Markdown-only code-block exemption.
    Switch to a Python checker. **Applied** as
    `tools/check_language_policy.py`.
  - **R4.2**: test breakage scope is wider than the plan
    surfaced — `test_governor_phase4.py` L181 / L246-258 and
    `test_governor_phase3.py` L23 also assert Korean reminder
    bytes. **Applied** in commit 4 (all four test files
    updated).
  - **R4.3**: governor-review-log "user-attributed only"
    preservation is too narrow. Three categories needed:
    user/owner statement, reviewer verdict, historical excerpt.
    **Applied**.
  - **R4.4**: `pr-NNN-...md` filename PR-number requirement
    means commit 4 must follow draft PR creation.
    **Applied** as the documented commit-3-then-draft-PR-then-
    commit-4 workflow.
  - **R4.5**: `<!-- ko:rationale -->` is a non-existent literal;
    naming it confuses readers. **Applied** in commits 1-4 as a
    generic hidden-rationale prohibition; **tightened in commit 5**
    to the actual checker scope (line-visible Korean only; encoded
    payloads remain policy intent, not current enforcement).
  - **R4.6**: `AGENT_LOCALE` follow-up issue must be created
    in this PR's lifecycle, not deferred. **Applied** as
    a separate `gh issue create` invocation linked from
    the main PR body.
  - **R4.7**: review-log Tier 1 exclude in pre-commit is too
    coarse — every new entry would silently pass. **Applied**:
    review-log scanned with the same checker; only lines
    starting with one of three provenance prefixes are
    allowed to carry Korean.
  - **R4.8**: shell self-grep regex would drift from the
    Python checker. **Applied**: removed self-grep from
    documentation; the Python checker is the only
    sanity-check tool.
  - **R-extra**: `governor-paths.md` L37 typo
    (`pre-commit-config.yaml` should be `.pre-commit-config.yaml`)
    in scope of this PR. **Applied**.

### Round 5 — final sanity check + dry run

- **Target**: consolidated plan immediately before commit 1.
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only`.
- **Final Verdict**: 4 sharp findings; all integrated into
  the plan and the implementation.
- **R-points**:
  - **R5.1**: commit-4-after-draft-PR workflow must include
    a final PR-body update (link the new review-log entry)
    + `gh pr ready`. **Partially applied** before review fixes;
    PR #132 was converted back to draft for commit 5 / commit 6
    and must only be marked ready after the final re-review passes.
  - **R5.2**: per-file `TOKEN_LITERALS_BY_FILE`, multi-line
    provenance prefix repetition, and CWD/argv robustness
    must be explicit in the checker design. **Applied** in
    `tools/check_language_policy.py` (each constant + the
    `main()` argv vs full-scan branch).
  - **R5.3**: code-block exemption must be Markdown-only.
    `.py` / `.toml` / `.yaml` / `.sh` source/config files
    are scanned in full. **Applied**: `MARKDOWN_EXTENSIONS`
    gates the strip-fenced-blocks pass.
  - **R5.4**: pre-implementation dry run is necessary
    because the Plan Agent inventory may miss legacy
    Korean. **Applied**: dry run surfaced 4 additional
    Korean prose lines not in the original 17-file
    inventory (`scaffolding-layers.md` L293,
    `target-operating-model.md` L268 / L323,
    `archive/014-omc-vs-native-orchestration.md` L208).
    Commit 2 scope expanded from 17 to 19 files
    accordingly.

### Round 6 — post-fix cross-tool review

- **Target**: PR #132 diff after commit 6 (`38c06da`), focused on
  Tier 1 Language Policy correctness, checker/pre-commit alignment,
  governor-review-log accuracy, and regressions introduced by commits
  5 and 6.
- **Reviewer**: `codex exec -m gpt-5.5 --sandbox read-only`.
- **Final Verdict**: `Not merge-ready`; 3 findings surfaced.
- **R-points**:
  - **R6.1** (HIGH): AGENTS.md said backtick-quoted Korean is
    blocked, but the checker stripped all Markdown inline code before
    scanning. **Applied**: inline backticks are now scanned; only
    fenced Markdown blocks remain exempt. Added regression tests for
    inline-backtick Korean and HTML-comment Korean.
  - **R6.2** (LOW): drift tests overclaimed full path alignment while
    checking hand-picked anchor paths. **Applied**: AGENTS.md policy
    bullets now compare as a normalised set against `TIER1_GLOBS`, and
    pre-commit regex coverage is generated from every `TIER1_GLOBS`
    entry. **Tightened after re-review**: `.codex/rules/**/*` now
    covers the live `.rules` prefix-rule file, with a regression test
    proving non-Markdown Codex rule files are Tier 1-scanned.
  - **R6.3** (MEDIUM): the behaviour-invariance table overstated
    review-log Korean as only provenance-tagged; the README prompt
    template still contains fenced Korean sample labels. **Applied,
    then tightened after re-review**: metric now distinguishes
    provenance-bearing entries, token-only references, and the fenced
    README prompt sample.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 1 | Initial two-policy proposal failure modes | Fixed | Converted into the audience-tiered policy analysis. |
| Round 2 | 4-tier overengineering under solo-repo assumption | Rejected | Later team-scale context invalidated the solo-repo simplification. |
| Round 3 | Team-scale leak surface and review-log readability gaps | Fixed | Restored stronger Tier 1 policy, cleanup, and review-log backfill requirements. |
| Round 4 | R4.1: pygrep cannot encode required exceptions | Fixed | Python checker implemented. |
| Round 4 | R4.2: test breakage scope wider than planned | Fixed | Affected hook tests updated. |
| Round 4 | R4.3: review-log preservation categories too narrow | Fixed | Three provenance prefixes adopted. |
| Round 4 | R4.4: draft-PR ordering needed for PR-numbered log | Fixed | Commit workflow documented and followed. |
| Round 4 | R4.5: misleading literal hidden-rationale marker | Fixed | Policy now describes hidden rationale generically. |
| Round 4 | R4.6: AGENT_LOCALE follow-up must be created | Fixed | Follow-up issue was created during the PR lifecycle. |
| Round 4 | R4.7: review-log Tier 1 exclude too coarse | Fixed | Review-log files are scanned with provenance-prefix exceptions only. |
| Round 4 | R4.8: shell self-grep would drift | Fixed | Python checker became the single sanity-check tool. |
| Round 4 | R-extra: governor-paths filename typo | Fixed | `.pre-commit-config.yaml` path corrected. |
| Round 5 | R5.1: draft PR workflow needs final body update and ready step | Fixed | PR lifecycle was adjusted before final readiness. |
| Round 5 | R5.2: checker design constants and argv robustness | Fixed | Constants and full-scan versus argv scan paths implemented. |
| Round 5 | R5.3: code-block exemption must be Markdown-only | Fixed | Fenced-block stripping is gated by Markdown extensions. |
| Round 5 | R5.4: pre-implementation dry run needed | Fixed | Dry run expanded cleanup scope from the original inventory. |
| Round 6 | R6.1: inline-backtick Korean was being stripped | Fixed | Inline code is scanned and regressions were added. |
| Round 6 | R6.2: drift tests overclaimed path alignment | Fixed | Tests compare normalized Tier 1 path sets and pre-commit coverage. |
| Round 6 | R6.3: behaviour-invariance table overstated review-log Korean scope | Fixed | Metric split provenance, token-only references, and fenced prompt samples. |

## Inherited constraints

This PR introduces three new ICs that future governor-changing
PRs must respect.

- **IC-1 ~ IC-16** — preserved verbatim from pr-130. Hybrid
  Harness v1 contract still binding.
- **IC-17 (NEW)** — *Tier 1 paths block Korean (Hangul) prose at
  commit time; English is the intended writing language for
  everything else.* The bilingual escape-token vocabulary is the
  only exception and is scoped per-file in
  `tools/check_language_policy.py::TOKEN_LITERALS_BY_FILE`.
  Enforced by the pre-commit hook `tier1-language-policy` plus
  `tests/unit/agents_shared/test_language_policy.py`. AGENTS.md
  § Language Policy is the canonical text. **Scope today is
  Korean only**; other CJK languages and encoded payloads
  (base64, HTML entities) are explicitly out of the checker's
  enforcement surface — see AGENTS.md § Language Policy for the
  full scoping note.
- **IC-18 (NEW)** — *governor-review-log entries preserve
  original Korean lines as provenance only when they begin with
  one of three exact blockquote prefixes:
  `> Original user/owner statement (ko, verbatim):`,
  `> Original reviewer verdict (ko, verbatim):`,
  `> Historical Korean excerpt (ko, verbatim):`.* The next
  non-blank line after each provenance line must be Hangul-free
  (the English normalised meaning); the checker enforces this
  via a next-line scan added in commit 5 of this PR. Multi-line
  preserved Korean must repeat the prefix on every line.
- **IC-19 (NEW, scoped to line-visible forms)** — *No hidden
  Korean rationale in Tier 1 paths in line-visible forms — HTML
  comments, backtick-quoted attribute values, or any Korean text
  the line-grep checker can read.* The checker
  intentionally does **not** decode base64 / HTML entities /
  other encodings today; smuggling Korean through those layers
  still violates the policy intent and will be removed if found,
  but it is best-effort enforcement, not a hard guarantee. If
  encoded-payload leaks become a real failure mode, expand the
  detector first and update this constraint to match.

## Self-application proof

Evidence checkpoint after commit 5 (`e8b9ec9`) and before commit 6
(this documentation correction):

- **PR state** — GitHub connector read for PR #132 returned
  `state=open`, `draft=true`, `head_sha=e8b9ec9`, `commits=5`.
  `fetch_pr_comments`, `list_pull_request_reviews`, and
  `list_pull_request_review_threads` all returned empty collections,
  so there were no GitHub inline threads or submitted reviews to
  resolve at this checkpoint.
- **Review feedback actually addressed in commit 5** — the owner
  handoff checklist supplied the actionable review items:
  R132-IMPL.1, R132-IMPL.2, R132-IMPL.3, R132-IMPL.5, plus the
  HIGH/MEDIUM/LOW follow-ups. Commit 5 applied those fixes:
  policy wording now matches Korean/Hangul enforcement scope;
  `.pre-commit-config.yaml` file matching is drift-tested against
  canonical anchor paths; provenance lines require a following
  Hangul-free English summary; Markdown fences tolerate up to
  three leading spaces; stale `(block-级)` / `(block-level)` labels
  are now `(blocking)`; IC-19 no longer claims encoded-payload
  enforcement; `test_governor_phase3.py` is less wording-coupled;
  and `scaffolding-layers.md` was removed from the live token
  allowlist.
- **Commit-hook evidence** — the first commit attempt failed because
  the hook entry used `python`, which is absent in the local commit
  environment. Commit 5 changed the hook entry and the matching
  documentation references to `python3`; the second `git commit`
  attempt then ran the hook stack successfully.
- **Verification commands**:
  - `uv run pytest tests/unit/agents_shared/test_language_policy.py tests/unit/agents_shared/test_governor_phase3.py` → 28 passed.
  - `uv run pytest tests/unit/agents_shared/ -v` → 223 passed.
  - `python3 tools/check_language_policy.py` → 0 violations across
    158 scanned files.
  - `uv run pre-commit run tier1-language-policy --all-files` → passed.
  - `uv run pre-commit run --all-files` → passed.
  - `git diff --check` → clean.
- **Sync evidence** — commit 5 touched shared rule sources and kept
  command references aligned across `AGENTS.md`,
  `docs/ai/shared/drift-checklist.md`,
  `.pre-commit-config.yaml`, and `tools/check_language_policy.py`.
  It did not change runtime app layering; architecture guards still
  ran through pre-commit (`no-domain-infra-import`,
  `no-entity-pattern`).
- **Remaining gate** — R132-IMPL.4 is this correction. After commit
  6 is pushed, the branch still needs a fresh PR re-review plus the
  required cross-tool review before PR #132 is marked ready again.

## Behaviour-invariance proof

| Metric | Pre-PR | Post-PR | Note |
|---|---|---|---|
| Tier 1 Korean violations (run by `tools/check_language_policy.py`) | 83 across 19 files | 0 across 159 scanned | Cleanup goal met. |
| `tests/unit/agents_shared/` full suite | not used as the original PR metric | 226 passed | Includes 20 language-policy regression cases after Round 6 follow-up fixes. |
| Existing reminder fixtures | 3 byte-equality assertions targeting Korean reminders | 3 byte-equality assertions targeting English reminders | `CANONICAL_KOREAN_LINES` renamed `CANONICAL_REMINDER_LINES`; intent unchanged (inline-redeclaration ban). |
| `governor-review-log/*` files with Korean prose | 6 (pr-125 ~ pr-130, README) | 4 provenance-bearing entries + token-only references in pr-127/pr-132 + 1 fenced README prompt sample | Original Korean preserved verbatim under three blockquote prefixes; README keeps a fenced review-template sample, which the Markdown fence exemption intentionally ignores. |
| Pre-commit configured hook count | 16 | 17 | +1 `tier1-language-policy` (15 commit-stage hooks, 1 manual mypy hook, 1 commit-msg hook). |
| CI workflow file count | unchanged | unchanged | Existing `architecture` job picks up the new hook automatically. |
| Bilingual escape-token regex | `^\s*\[(trivial\|hotfix\|exploration\|자명\|긴급\|탐색)\](?:\s\|$)` | identical | Token vocabulary unchanged; per-file allowlist preserves them in their canonical files. |

## Open follow-ups

- **`AGENT_LOCALE=ko` env-var override**: terminal hook prompts
  (`stop-sync-reminder.sh`, `completion_gate.py` reminders,
  `verify.py` reminder) are now English-only. Korean
  teammates lose ergonomic readability of these terminal
  lines. A separate GitHub issue tracks the
  terminal-localisation layer; the policy source language
  remains English-canonical regardless of locale.
