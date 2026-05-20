# PR #148 — G Closure Linter

GitHub PR: https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/148

## Summary

Issue #145 adds a mechanical checker for AGENTS.md guard G. The checker scans
`docs/ai/shared/governor-review-log/pr-*.md`, requires exactly one canonical
`## R-points Closure Table`, accepts only the three canonical closure labels,
and is registered as a local pre-commit hook.

The PR intentionally bundles three tightly-coupled pieces: the linter, the
canonical table-shape documentation, and legacy review-log backfill. This is the
IC-RG-5-compatible bundling case: the checker cannot hard-fail safely until the
historical entries pass, and the table contract must land with the checker that
enforces it.

V1 non-scope is explicit: no summary-count validation, no `Source` or R-point ID
format validation, and no semantic judgment of whether a chosen closure category
is correct. Issue #146 remains time-gated and is not implemented here.

## Review Rounds

### Round 0 — Plan Review

- **Reviewer**: Claude Opus 4.7, read-only.
- **Target**: #145 implementation plan before coding.
- **Final Verdict**: implement after tightening parser and enforcement details.
- **Outcome**: final plan incorporated stricter parser policy, fenced-code
  avoidance, explicit v1 non-scope, and hard-fail after legacy backfill.

### Round 1 — Implementation Review

- **Reviewer**: Claude Opus 4.7 via `claude -p --model claude-opus-4-7`,
  read-only, no file modification, no git commands.
- **Target**: implementation after local verification passed.
- **Final Verdict**: `minor fixes recommended`.
- **Findings**:
  - F1: missing PR-numbered self-application entry for this PR.
  - F2: `harness-asset-matrix.md` Update Log missing #145 row.
  - F3: IC-RG-5 bundling justification not surfaced.
  - F4: heading detection accepts 4-space indented pseudo-headings.
  - F5: backslash escape handling is intentionally narrower than full
    CommonMark semantics.
  - F6: pre-commit trigger globs are correctly scoped.
  - F7: coarse historical backfill rollups are acceptable v1 compromise.
  - F8: `pr-143` summary-count validation remains out of v1 scope.
  - F9: test coverage is thorough.

### Round 2 — Gate-on-Gate Review

- **Reviewer**: Claude Opus 4.7 via `claude -p --model claude-opus-4-7`,
  read-only, no file modification, no git commands.
- **Target**: PR #148 self-application entry, Round 1 closure, and sync
  surfaces after the PR-numbered log entry was added.
- **Final Verdict**: `minor fixes recommended`.
- **Findings**:
  - F1: Round 1 R4 closure rationale wording contradicted the permissive
    `line.strip() == HEADING` implementation.
  - F2: Verification block recorded only pre-entry counts.
  - F3: `tools/` remains outside `governor-paths.md`; this follows the
    `tools/check_language_policy.py` precedent and is not changed in #145.
  - F4: Round 2 outcome needed to be appended after this review completed.
  - F5: #147 README round-numbering drift was correctly not re-opened.
  - F6: #145 did not broaden into #146 retrospective scope.
  - F7: PR #148 entry uses the canonical closure-table shape.
  - F8: sync targets are complete.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | Parser and enforcement plan needed stricter shape | Fixed | Final plan required one canonical heading, canonical header, four-column rows, fenced-code avoidance, escaped-pipe parsing, exact closure labels, and hard-fail after backfill. |
| Round 0 | V1 non-scope needed to be explicit | Fixed | README and checker docstring state summary counts, Source format, R-point ID format, and semantic correctness are out of scope. |
| Round 1 | R1: missing PR-numbered self-application entry | Fixed | This file records PR #148 and README index links it. |
| Round 1 | R2: missing matrix Update Log row | Fixed | `harness-asset-matrix.md` now records the #145 64-to-65 transition. |
| Round 1 | R3: IC-RG-5 bundling justification not recorded | Fixed | Summary explains why linter, canonical table docs, and backfill must land together. |
| Round 1 | R4: CommonMark-strict heading indentation | Rejected | V1 accepts indented headings because detection strips outer whitespace; no current or legacy entry exercises this theoretical gap. |
| Round 1 | R5: CommonMark backslash semantics | Rejected | Closure-label validation is unaffected because valid closure labels contain no backslashes. |
| Round 1 | R6: pre-commit trigger globs | Rejected | Hook runs full-scan when the linter, README, or any review-log PR entry changes. |
| Round 1 | R7: coarse rollups in legacy backfill | Deferred-with-rationale | V1 accepts compact historical rollups; a future retrospective can granularise them if #146 finds that useful. |
| Round 1 | R8: `pr-143` closure summary-count validation | Deferred-with-rationale | Summary-count validation is explicitly out of v1 scope. |
| Round 2 | F1: R4 closure rationale wording contradicted implementation | Fixed | Round 1 R4 note now states that V1 accepts indented headings and rejects the issue as a v1 non-problem. |
| Round 2 | F2: Verification block recorded only pre-entry counts | Fixed | Verification now records the post-entry 12-entry and 168-file counts. |
| Round 2 | F3: `tools/` outside governor-paths | Deferred-with-rationale | This follows the `tools/check_language_policy.py` precedent; promoting `tools/**` into governor-paths is a separate ADR-grade decision. |
| Round 2 | F4: Round 2 outcome forward-reference | Fixed | This Round 2 section and closure rows record the completed gate-on-gate review. |
| Round 2 | F5: #147 README round-numbering drift | Rejected | #147 explicitly deferred that drift; #148 does not reopen it. |
| Round 2 | F6: #146 retrospective scope | Rejected | #145 remains limited to the v1 linter, documentation, and backfill. |
| Round 2 | F7: PR #148 entry self-application | Rejected | The entry uses one canonical closure table and passes the linter. |
| Round 2 | F8: sync-target completeness | Rejected | Pre-commit, README, matrix, and repo-facts are all updated. |

## Inherited Constraints

- IC-1 through IC-RG-8 from prior governor-changing PRs remain in force.
- New closure-table entries must use exactly `Fixed`,
  `Deferred-with-rationale`, or `Rejected` as the closure category.
- Decisions to retain existing behaviour must still be classified as
  `Deferred-with-rationale` or `Rejected`; "preserve" and "leave as-is" are not
  closure categories.

## Self-Application Proof

- **Governor-changing scope**: yes. This PR touches `.pre-commit-config.yaml`,
  `docs/ai/shared/**`, and adds `tools/check_g_closure.py`.
- **Cross-tool review**: Round 0 plan review, Round 1 implementation review,
  and Round 2 gate-on-gate review completed with Claude Opus 4.7.
- **Sync proof**: `governor-review-log/README.md` defines the enforced table
  shape; `.pre-commit-config.yaml` registers the hook; `harness-asset-matrix.md`
  and `repo-facts.md` list the new enforcement asset.
- **Architecture proof**: no application-layer code changed. The change is
  isolated to governance tooling, tests, and review-log documentation.
- **Verification**:
  - `uv run pytest tests/unit/agents_shared/test_g_closure.py -v` — 23 passed.
  - `python3 tools/check_g_closure.py` — 0 violations across 12 entries.
  - `python3 tools/check_language_policy.py` — 0 violations across 168 scanned
    files.
  - `uv run pre-commit run --all-files` — passed.
