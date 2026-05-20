# PR #134 — AGENT_LOCALE: Localized Hook Reminders + Locale Data Exception

> Issue: [#133](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/133)
> Pull Request: [#134](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/134)
> ADR: ADR 045 (constraints inherited)
> Inherited from: [pr-130](pr-130-shared-governor-module.md) (IC-13~16) +
> [pr-132](pr-132-language-policy.md) (IC-17 Tier 1 ban)

## Summary

Adds AGENT_LOCALE-aware translation of all hook-emitted terminal /
systemMessage strings while preserving the canonical English source
in every hook file (Issue AC). When the agent process (`claude` /
`codex` CLI) is started with `AGENT_LOCALE=ko` in environment, hooks
emit Korean. With the variable unset / `en` / unknown, output is
byte-identical to pre-#133 English.

The new locale data file
[`.agents/shared/governor/locale.py`](../../../../.agents/shared/governor/locale.py)
holds an 18-key table — 3 reminder constants re-exported from
`verify.py` / `completion_gate.py` (drift impossible by reference)
and 15 sync-advisory keys whose English values mirror the inline
fallback strings each hook file already carried. The Bash hook
resolves keys via `python -m governor.locale KEY`; Python hooks call
`get_locale_string("KEY") or KEY` (always-fallback per IC-19).

The previous Tier 1 Language Policy "bilingual escape tokens are the
only exception" wording is replaced everywhere by **"two
narrowly-scoped exceptions: bilingual escape tokens AND locale data
files (LOCALE_DATA_FILES)"** — synchronized across `AGENTS.md` (5
sites), `CLAUDE.md`, `.claude/rules/project-status.md`,
`docs/ai/shared/skills/{sync-guidelines, security-review}.md`,
`docs/ai/shared/drift-checklist.md`,
`tools/check_language_policy.py` (docstring + stderr footer), and
`.pre-commit-config.yaml`. The phrasing drift test
(`test_locale_exception_documented_consistently`) is pinned to a
10-file allowlist with bidirectional regex (Codex Round 6 caught
that one-direction matching missed half the real phrases, plus the
word-boundary trap on `exception` vs `exceptions`).

This PR is **governor-changing** because it edits AGENTS.md +
CLAUDE.md (Tier A), `docs/ai/shared/**` (Tier A),
`.claude/hooks/**` + `.claude/rules/**` (Tier B), `.codex/hooks/**`
(Tier B), `.agents/**` (Tier B), `tools/check_language_policy.py`
(Tier A), `.pre-commit-config.yaml` (Tier A). Therefore this
self-application entry is mandatory per
[`governor-paths.md`](../../../ai/shared/governor-paths.md).

## Review rounds

**Eight rounds** of cross-tool review with Codex CLI (`codex exec
--skip-git-repo-check`) before the first commit landed. Trajectory
of findings:

| Round | Verdict | Findings | BLOCKING |
|---|---|---|---|
| R1 | RED | 10 | 3 |
| R2 | RED | 8 (F11–F18) | 4 |
| R3 | RED | 8 | 2 |
| R4 | RED | 7 | 1 |
| R5 | RED | 5 | 1 |
| R6 | RED | 5 | 1 |
| R7 | RED | 2 | 1 |
| **R8** | **GREEN** | 0 | 0 |

### Round 1 — adversarial review of the initial test.md plan

- **Target**: the user-supplied plan in `test.md` (substitution-layer
  design, `LOCALE_DATA_FILES`, 5 keys, single try block).
- **Reviewer**: `codex exec -m gpt-5.5`.
- **Final Verdict**: RED.
- **R-points** (all addressed across v2–v8):
  - **F1 BLOCKING**: env model error — `AGENT_LOCALE=ko make dev`
    does not propagate to hook subprocesses. Re-defined as
    *agent-process env* (`AGENT_LOCALE=ko codex` / `~/.zshrc`).
  - **F2 BLOCKING**: `.claude/hooks/stop-sync-reminder.sh` Korean
    inline violates the AC — moved to `python -m governor.locale`
    invoke pattern (D4).
  - **F3 HIGH**: `LOCALE_DATA_FILES` file-wide skip is too broad;
    narrowed to a single file (`locale.py`) plus an AST guard.
  - **F4 HIGH**: AGENTS.md "only exception" contradicts a new
    locale carve-out — policy body itself rewritten in 5 sites.
  - **F5 BLOCKING**: existing `test_completion_gate.py:346-353`
    asserts `governor_changing_segment()` returns the English
    constant byte-identically, breaking under `AGENT_LOCALE=ko`
    leak — solved by the autouse `isolate_agent_locale` conftest
    fixture (D10).
  - **F6 HIGH**: locale resolver inside the existing shared-import
    `try` block silences `_SHARED_OK` if locale.py fails — separate
    `try` block + per-key fallback dict (D6).
  - **F7 HIGH**: stop-sync translation scope was incomplete (only
    headers); expanded to all user-facing prose (D7, 15 SYNC_*
    keys).
  - **F8 MEDIUM**: `_LOCALE_EN` literal duplication risks drift —
    re-export `verify.REMINDER_TEXT` /
    `completion_gate.GOVERNOR_REMINDER_*` by reference (D8).
  - **F9 MEDIUM**: subprocess emission untested — added 6
    in-process emission tests + 2 shell subprocess in temp-repo
    tests (D11).
  - **F10 LOW**: smoke verification was unreliable on clean tree;
    replaced by controlled subprocess in temp git repo with
    untracked file (no commit identity needed).

### Round 2 — F11–F18 surfaced after v2

- **Target**: plan v2 (Codex log: ADDRESSED 5/10, PARTIAL 5/10).
- **Final Verdict**: RED.
- **R-points** (8 new):
  - **F11 BLOCKING**: direct path execution
    `python3 .agents/shared/governor/locale.py KEY` fails because
    `from .verify import REMINDER_TEXT` requires package context —
    switched to `python -m governor.locale` (D5).
  - **F12 BLOCKING**: Bash helper used cwd-relative path —
    introduced `HOOK_DIR` / `REPO_ROOT` / `SHARED_DIR` plus
    `PYTHONPATH=$SHARED_DIR` (D4).
  - **F13 BLOCKING**: `${var,,}` is bash 4+; macOS dev shell is
    bash 3.2.57. Replaced with
    `tr '[:upper:]' '[:lower:]'` (D4); `bash -n` test added.
  - **F14 BLOCKING**: AC ("canonical English source unchanged")
    contradicted v2's plan to *move* stop-sync inline strings into
    `_LOCALE_EN`. AC re-interpreted as
    *value-invariance + file-invariance + position-flexibility*;
    every English literal stays in its hook file as the `_loc()`
    fallback argument; drift caught by D8 substring tests.
  - **F15 HIGH**: AGENTS.md § Two specific prohibitions Item 2
    (`No new Korean prose lines`) was missed in the v2 sync target
    list; added to D9 with explicit carve-out wording.
  - **F16 HIGH**: Bash fallback strings containing
    `$sync-guidelines` would expand under `set -u` and abort the
    hook — fix mandates single-quoted fallbacks (D4); IC-19 shell
    callsite test enforces.
  - **F17 HIGH**: Codex `_shared.REPO_ROOT` is computed at module
    import, so `tmp_path + git init` cannot redirect it. Replaced
    subprocess test pattern with `monkeypatch.setattr` on the
    module-bound `changed_files` (D11).
  - **F18 MEDIUM**: key inventory was reported as 16 but actually
    18 (3 + 15). `_EXPECTED_KEYS` pinned and asserted by
    `test_locale_keys_match_expected_inventory`.

### Round 3 — eight new R3 findings after v3

- **Target**: plan v3 (5 ADDRESSED + 3 PARTIAL from R2).
- **Final Verdict**: RED.
- **R-points** (8 new):
  - **R3-F1 BLOCKING**: completion-gate `WITH_PR` path
    `_resolve_locale_string("KEY").format(pr=p)` would emit `""`
    when locale import fails (`""`.format(pr=p) == `""`). Fix:
    `template = _resolve_locale_string("KEY") or KEY;
    template.format(pr=current_pr)`. The IC-19 always-fallback
    callsite test (D13) was added to prevent this regression.
  - **R3-F2 BLOCKING**: AGENTS.md alone was not enough — 6 more
    files mention the exception phrasing
    (`sync-guidelines.md`, `drift-checklist.md`, `review-pr.md`,
    `review-architecture.md`, checker docstring, pre-commit
    comment). All 12 sync targets enumerated in D9.
  - **R3-F3 HIGH**: D8 drift-guard "read line 32 of the shell
    hook" wording contradicted D4's plan to move that echo into
    a variable reference; line-agnostic substring + ast-based
    drift extraction adopted instead.
  - **R3-F4 HIGH**: Codex stop-sync had no callable entry point
    for in-process testing — extracted `build_segments(changed)`
    + `main()` while preserving all 5 responsibilities
    (sync advisory / verify-first / completion-gate / marker
    consumption / stale verify-log cleanup).
  - **R3-F5 HIGH**: monkeypatch target in v3 test snippet was
    `_shared.changed_files`, but Codex completion_gate does
    `from _shared import changed_files` — the bound name lives on
    `completion_gate.changed_files`, matching the existing
    `test_completion_gate.py:198` pattern.
  - **R3-F6 MEDIUM**: shell `source` in subprocess test broke
    `$0` ($BASH_SOURCE issue) and could exit the parent shell on
    `[ -z "$CHANGED" ] && exit 0`. Switched to a temp git repo +
    script execution with `_setup_temp_repo`.
  - **R3-F7 MEDIUM**: file-wide skip allowed Korean in comments /
    docstrings inside locale.py — added the AST + tokenize guard
    that requires Hangul to be inside `_LOCALE_KO` *dict values*
    only.
  - **R3-F8 LOW**: per-hook emission map was missing; added the
    explicit table to D7 + per-hook key tests
    (`test_*_emission_keys`).

### Round 4 — seven R4 findings after v4

- **Target**: plan v4 (3 ADDRESSED + 5 PARTIAL).
- **Final Verdict**: RED.
- **R-points** (7 new):
  - **R4-F1 BLOCKING**: v4's `build_segments` snippet preserved
    only sync-advisory + completion-gate; verify-first segment
    append + the two side-effect calls (`consume_phase2_markers`,
    `cleanup_stale_verify_logs`) were missing. v5 made
    `build_segments` cover responsibilities 1–3 and `main`
    drive 4–5 explicitly.
  - **R4-F2 HIGH**: D9 sync-target list missed `CLAUDE.md:19`
    and `.claude/rules/project-status.md:48`. Added; phrasing
    test scope explicitly excludes `governor-review-log/**` and
    `docs/history/**` to avoid historical false positives.
  - **R4-F3 HIGH**: per-hook map mis-assigned the Codex side —
    actual REMINDER_TEXT *emit* lives in
    `.codex/hooks/stop-sync-reminder.py:88`, not
    `.codex/hooks/verify_first.py`. Latter is provider-only
    (`should_remind`, `REMINDER_TEXT`); v5 added a
    `localized_reminder_text()` helper that the Stop hook calls.
  - **R4-F4 MEDIUM**: IC-19 was aspirational without a concrete
    test; v5 D13 specified the AST + parent-map callsite scan
    plus shell single-quote regex check.
  - **R4-F5 MEDIUM**: AST guard allowed Hangul inside the entire
    `_LOCALE_KO` line range, including comments inside the dict.
    Strengthened to `ast.Dict` + per-value node-id tracking +
    tokenize comment scan.
  - **R4-F6 MEDIUM**: ko emission test omitted
    `_read_latest_token` patch, so an exploration token in the
    real session would silence the reminder. Added the patch.
  - **R4-F7 LOW**: `git commit` in shell test would fail without
    `user.name` / `user.email`. Switched to untracked-file
    pattern (no commit needed; shell hook reads
    `git ls-files --others --exclude-standard`).

### Round 5 — five R5 findings after v5

- **Target**: plan v5 (5 ADDRESSED + 3 PARTIAL).
- **Final Verdict**: RED.
- **R-points** (5 new):
  - **R5-F1 BLOCKING**: v5 `main()` proposed
    `_ = load_payload()`, but the original Codex Stop hook does
    not read stdin. Adding a `json.load(sys.stdin)` would crash
    on empty stdin. Removed completely.
  - **R5-F2 HIGH**: phrasing drift test regex was unidirectional
    (`only/sole exception ... bilingual`), missing the more common
    repo wording (`Bilingual ... only/sole exception`).
    Bidirectional regex + Form-3 catch for
    `the only Korean strings allowed`.
  - **R5-F3 HIGH**: `AGENTS.md:133` Default Coding Flow
    Exception-Tokens callout was missed; added to D9.
  - **R5-F4 MEDIUM**: `security-review.md` carve-out wording was
    Korean in the plan body — fixed to English.
  - **R5-F5 MEDIUM**: IC-19 AST guard needed an explicit
    parent-map idiom (`_build_parent_map`) and `_loc` keyword
    rejection (positional-only convention).

### Round 6 — five R6 findings after v6

- **Target**: plan v6 (3 ADDRESSED + 2 PARTIAL).
- **Final Verdict**: RED.
- **R-points** (5 new):
  - **R6-F1 BLOCKING**: regex `\s+exception` matched both
    `exception` and `exceptions` (no word boundary). After the
    new stderr footer was applied
    (`...are the two narrowly-scoped exceptions.`), it would
    self-fail. Fix: `exception\b`.
  - **R6-F2 HIGH**: regex missed the `the only Korean strings
    allowed` form — added Form 3.
  - **R6-F3 HIGH**: security-review insertion anchor was vague
    ("around line 82"); replaced with
    "immediately after the bullet paragraph that mentions
    'hidden non-English rationale'".
  - **R6-F4 MEDIUM**: positional-only `_loc` convention not
    documented; v7 added the docstring + IC-19 enforces it.
  - **R6-F5 MEDIUM**: test_31 ordering coverage was vague — v7
    pinned 6 explicit input scenarios.

### Round 7 — exact replacement wording missing

- **Target**: plan v7.
- **Final Verdict**: RED.
- **R-points**:
  - **R7-BLOCKING**: 9 stale phrases existed; v7 said "UPDATE"
    abstractly. v8 inlined exact replacement wording for every
    target file so the implementer copies them verbatim.
  - **R7-non-blocking**: `security-review.md` insertion location
    sharpened.

### Round 8 — GREEN

- **Target**: plan v8.
- **Reviewer**: same Codex thread.
- **Result**: Codex regex-simulated all 11 v8 replacement wordings
  against Form 1 / 2 / 3 — **zero matches** for every replacement,
  including the trickiest cases:
  - `tools/check_language_policy.py:421-424` new stderr footer
    (`...are the two narrowly-scoped exceptions.`) — passes Form 1
    because of `\b` after `exception`.
  - `AGENTS.md:85` AI-when-editing rule rewrite (mentions
    `bilingual` and `exception` in the same paragraph) — passes
    because the order in the new wording is
    `bilingual ... exception ... only` rather than
    `bilingual ... only ... exception`, breaking both Form 1 and
    Form 2.
- **Final Verdict**: **GREEN — implementable as specified**.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 1 | R1-F1 through R1-F10: initial locale plan defects | Fixed | Later plan rounds absorbed all blocking, high, and medium defects. |
| Round 2 | R2-F11 through R2-F18: follow-up locale design defects | Fixed | Later plan rounds resolved all carried defects before implementation. |
| Round 3 | R3-F1 through R3-F8: completion-gate, sync-target, callable-entry, and checker gaps | Fixed | Plan v4 and later revisions addressed the full R3 set. |
| Round 4 | R4-F1 through R4-F7: segment-builder, sync, emission-map, AST guard, and test gaps | Fixed | Plan v5 and later revisions addressed the full R4 set. |
| Round 5 | R5-F1 through R5-F5: main fallback, phrasing drift, default-flow wording, and guard specificity gaps | Fixed | Plan v6 and later revisions addressed the full R5 set. |
| Round 6 | R6-F1 through R6-F5: regex false-positive and implementation-specificity gaps | Fixed | Plan v7 addressed the R6 set. |
| Round 7 | R7-BLOCKING: exact replacement wording missing | Fixed | Plan v8 inlined exact replacement wording. |
| Round 7 | R7-non-blocking: security-review insertion location | Fixed | Insertion location was sharpened. |
| Round 8 | GREEN regex simulation | Fixed | Round 8 reported zero remaining findings. |

## Inherited constraints

This PR carries forward IC-13 through IC-17 from PR #130 / #132 and
introduces three new constraints that future governor-changing PRs
must respect.

- **IC-13** (PR #130): hooks must not redeclare `_within_24h` /
  marker reader / `EXPLORATION_TOKENS` / reminder text inline. Held
  here.
- **IC-14** (PR #130): hook shims must import canonical reminder
  strings from the shared module, never inline copies. Held here —
  every emit pattern is `<resolver call> or <imported canonical
  constant>`.
- **IC-15** (PR #130): `MarkerLifecycle` is a closed `Literal`.
  Untouched.
- **IC-16** (PR #130): GateStatus is a closed enum. Untouched.
- **IC-17** (PR #132): Tier 1 Korean-prose ban remains. The
  `LOCALE_DATA_FILES` carve-out is the second narrowly-scoped
  exception introduced by this PR; it is *file-scoped* and
  AST-bounded inside `locale.py`.
- **IC-18 (NEW)** — `governor.locale` may import from
  `governor.verify` and `governor.completion_gate`, but neither of
  those modules may import from `.locale`. Cycle prevention is
  enforced by
  `tests/unit/agents_shared/test_locale.py::test_no_locale_import_in_canonical_modules`.
  Future contributors adding helpers that need locale rendering at
  the canonical-constant module level must instead route the call
  through the hook's emit site.
- **IC-19 (NEW)** — every hook callsite of the locale resolver
  must combine the result with the canonical English fallback
  *before* any further operation (`format`, `echo`, etc.).
  Acceptable forms:
  - Python: `_resolve_locale_string("KEY") or KEY`
  - Python: `_loc("KEY", "fallback text")` (positional only;
    keyword form rejected)
  - Bash: `_resolve_locale KEY 'fallback text'` (single-quoted to
    avoid `set -u` expansion)
  Direct `.format(...)` on the resolver result is forbidden because
  `""`.format(...) silently emits the empty string. Enforced by
  `test_python_resolver_callsites_have_or_fallback` and
  `test_shell_resolver_callsites_have_single_quoted_fallback`.
- **IC-20 (NEW)** — adding a new entry to `LOCALE_DATA_FILES`
  requires the **5-step sync**:
  1. `tools/check_language_policy.py::LOCALE_DATA_FILES` — register the path.
  2. `AGENTS.md § Language Policy → Exemptions` — add the bullet that
     names the file and its scope.
  3. `tests/unit/agents_shared/test_locale.py::_EXPECTED_KEYS` — extend
     the inventory if new keys are introduced.
  4. Drift-guard test — every key emitted from a hook must have an
     explicit substring or AST equality check against `_LOCALE_EN`.
  5. New governor-review-log entry — this directory.

## Self-application proof

This PR is governor-changing and was implemented through the
governor-review flow defined by PR #130. The proof points:

1. **Plan-mode iteration before any commit** — 8 Codex rounds
   logged above; plan file at
   `~/.claude/plans/test-md-133-fuzzy-blum.md` (private).
2. **`/sync-guidelines` Phase 0 alignment** — every change to
   `AGENTS.md` § Language Policy / `CLAUDE.md` / harness files /
   skills was paired with the policy-sync update in commit 2
   (`docs(policy): expand language policy to allow LOCALE_DATA_FILES
   exception`). The phrasing-drift test
   (`test_locale_exception_documented_consistently`) self-proves
   that the synchronization is complete.
3. **Per-hook drift guards** — the SYNC_* English source canonically
   lives where the hooks emit it (per-file invariance, AC). The
   substring + ast drift tests prove that each hook's English
   fallback equals `_LOCALE_EN[KEY]`. Drift between the two becomes
   a build failure.
4. **Inherited-constraint citations** — every IC-13 through IC-17
   freeze is held; new IC-18 / IC-19 / IC-20 are documented above
   with their enforcing tests.
5. **`tests/unit/agents_shared/test_locale.py`** runs 72 cases
   across 13 layers; combined suite is 298 tests (226 existing +
   72 new), all green at v8.
6. **Pre-commit clean** — `tier1-language-policy` (the gate this PR
   itself extended) passes for every modified file, including
   `.agents/shared/governor/locale.py` (file-wide skip via
   `LOCALE_DATA_FILES`).

### Findings

None remaining at v8. All R1–R7 BLOCKING / HIGH / MEDIUM issues
addressed; R8 GREEN.

### Drift Candidates

None. The phrasing-drift test enumerates the 10 in-scope files and
asserts zero stale phrases.

### Next Actions

All pre-merge items superseded by merge (commit 8648d59). Retrospective
cross-review completed as part of full governor audit (2026-04-28
evaluation session with Codex CLI gpt-5.5); see Completion State.

### Completion State

complete — PR #134 merged (commit 8648d59). Retrospective Codex
cross-review conducted as part of governor evaluation audit (2026-04-28)
covering IC-18 / IC-19 / IC-20 enforcement, 72-case locale test coverage,
and LOCALE_DATA_FILES carve-out consistency. No residual blocking findings
for PR #134 scope. IC-18/IC-19 numbering collision with PR #132 is noted
as a low-risk non-blocking item (A-3) deferred to the next governance PR.

### Sync Required

false — `/sync-guidelines`-equivalent updates already shipped in
commit 2 of this PR.
