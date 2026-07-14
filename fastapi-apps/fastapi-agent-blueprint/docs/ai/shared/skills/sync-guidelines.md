# Guideline Synchronization Quality Gate

## Default Flow Position

This skill participates in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow) at the **`completion gate`** step (or as a follow-up to `self-review` when drift is detected).

It is invoked when any of:
- A `self-review` skill (`/review-architecture`, `/security-review`, `/review-pr`) reported `Drift Candidates` or `Sync Required: true`.
- The change touched shared rule sources (`AGENTS.md`, `docs/ai/shared/`, `.claude/rules/`, `.codex/rules/`, `.antigravity/rules/`, `.gemini/`, ADRs).
- An ADR was created or amended in the session.

Recursion guard: do **not** invoke `/sync-guidelines` recursively from within itself, and do not invoke `/plan-feature` from inside this skill. This skill is the closure step of the flow; it does not re-enter the flow.

Use this skill to close the documentation and workflow side of the quality gate
after architecture, security, or workflow changes.

## Operating Modes

`/sync-guidelines` supports two modes:

- standalone inspection mode - discover drift directly from the repo state
- review follow-up mode - consume incoming drift candidates from
  `/review-pr`, `/review-architecture`, or `/security-review`, then verify and
  close them

## Input Contract

If a previous review already produced `Drift Candidates`, consume them first.
Each candidate should preserve:

- `target`
- `reason`
- `auto-fix`
- `sync-required`

If no candidates are provided, derive them from the repo diff and code/reference
inspection.

## Gate Triggers

Treat sync as required when at least one of the following changed or drifted:

- `AGENTS.md`
- `docs/ai/shared/`
- `docs/ai/shared/project-dna.md`
- shared checklists
- shared skill procedures or tool wrappers
- harness docs (`CLAUDE.md`, `.claude/rules/`, `.codex/`, `.antigravity/`, `.gemini/`)
- base classes, shared architecture wiring, or other documented reference
  patterns

## Sync Contract

The result is not complete until it includes all of:

- `Mode` - standalone or review follow-up
- `Input Drift Candidates` - consumed list, or `none`
- `project-dna` - updated or unchanged
- `AUTO-FIX` - applied mechanical fixes, or `none`
- `REVIEW` - policy or judgment items that still require human review, or `none`
- `Remaining` - unresolved drift that still exists, or `none`
- `Next Actions` - follow-up expected from the caller

If any `REVIEW` item exists, do not close with "nothing to change" or similar
language.

## Phase 0: Intake and Reference Scan

1. Determine the operating mode.
2. Collect incoming `Drift Candidates` if they already exist.
3. Read the reference domain (`src/user/`) and shared/base modules to anchor the
   current implementation shape.
4. Load the governing sources:
   - `AGENTS.md` — including § Language Policy. When editing any path listed there (Tier 1), all new prose must be English regardless of the chat language. Refuse Korean prose insertions and hidden-rationale workarounds (HTML comments, encoded payloads, attribute values, metadata). Bilingual escape tokens and locale data files (`tools/check_language_policy.py::LOCALE_DATA_FILES`) are the two narrowly-scoped exceptions, scoped per-file by `tools/check_language_policy.py`.
   - `docs/ai/shared/project-dna.md`
   - `docs/ai/shared/drift-checklist.md`
   - the affected shared procedures, checklists, wrappers, and harness docs

## Phase 1: Reconcile Drift Candidates with Code and References

Process incoming drift first.

- verify whether each candidate is still real
- promote still-valid candidates into `AUTO-FIX` or `REVIEW`
- mark resolved candidates as closed instead of re-reporting them blindly

If no incoming candidates exist, run the full drift inspection from
`docs/ai/shared/drift-checklist.md`.

## Phase 2: Refresh `project-dna` and Shared References

Update or confirm `project-dna` based on actual code.

- regenerate when drift exists or the caller explicitly requests it
- re-check shared references that depend on `project-dna`
- keep mechanical updates separate from policy-review updates

When a shared reference depends on product or policy judgment, report it under
`REVIEW` even if the code facts are clear.

## Phase 3: Verify Hybrid C and Close the Gate

Before closing:

- verify shared procedure existence for migrated skills
- verify both Claude and Codex wrappers reference the same shared procedure
- verify both wrappers keep the same Phase/Step overview count as the shared
  procedure
- verify Antigravity assets reference shared skills and governor policy instead
  of copying shared procedure text
- verify shared procedures do not contain tool-specific instructions
- **`project-status.md` table hygiene**: count rows in the `Recent Major Changes` table; if row count exceeds 15, flag for archival; scan cells for multi-line content that would break markdown table rendering; when a new version ships, archive pre-release rows to `docs/history/archive/project-status/` following the PR-B.1 pattern

Emit the full sync contract and clearly state whether the quality gate is closed
or waiting on review follow-up.

## Quality Gate Scenarios

Use these scenarios as regression examples for the workflow.

1. Architecture-changing PR
   - `/review-pr` should produce code findings and/or drift candidates
   - `/sync-guidelines` should refresh references before the gate closes
2. Security feature activation not reflected in `project-dna`
   - `/security-review` should not end in `SKIP`
   - it should raise a stale-reference drift candidate and require sync
3. Shared procedure changed but wrapper did not
   - `/sync-guidelines` should detect Hybrid C drift for Claude and Codex
     wrappers, and shared-source drift for Antigravity assets
4. Docs-only change that alters checklist meaning
   - `/sync-guidelines` should classify it under `REVIEW`, not a silent auto-fix

## Completion Example

```text
Mode: review follow-up
Input Drift Candidates: 2 consumed
project-dna: updated (feature status refreshed)
AUTO-FIX: 2 items applied (planning-checklists, skill wrappers)
REVIEW: 1 item (security checklist wording changed and needs human approval)
Remaining: none
Next Actions: rerun the originating review or acknowledge the open review item
```

## Cross-Tool Review Prompt Template

Use this template when another tool or reviewer cross-checks a
`/sync-guidelines` result, a shared-docs scan, or a drift-closure decision. The
purpose is a consistent input and output frame; reviewers may surface new drift
when current repository evidence supports it.

```text
Cross-tool review for /sync-guidelines (read-only). Do not modify files. Do not
run git commands.

Context
- Repo: fastapi-agent-blueprint
- Review target: <shared-docs scan, PR diff, or drift candidate set>
- Issue link: <#NNN or none>
- Round: <0 plan / 1 implementation / 2 gate-on-gate / N>
- original user question: <verbatim or concise restatement>
- success metric: <what the user said would count as success>
- Inherited constraints: <list of ADR{NNN}-G{N} consequence IDs from prior governance ADRs (post-ADR-047); for historical context, see governor-review-log/ archive>

What you are reviewing
- Mode: <standalone inspection / review follow-up>
- Input Drift Candidates: <none or summarized candidates>
- Changed shared surfaces: <AGENTS.md, docs/ai/shared, wrappers, harness docs>
- Claimed closure: <AUTO-FIX / REVIEW / Remaining / Next Actions summary>

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/drift-checklist.md
- docs/ai/shared/governor-paths.md
- docs/ai/shared/harness-asset-matrix.md
- docs/ai/shared/repo-facts.md
- Affected shared procedures, wrappers, checklists, and harness docs

Review Angles
1. Candidate reconciliation: were incoming drift candidates consumed, closed,
   or promoted instead of silently re-reported or dropped?
2. Shared-source consistency: do AGENTS.md, shared docs, wrappers, and harness
   docs agree without re-declaring governor-path globs?
3. Hybrid C parity: do shared procedures and both wrapper families point to the
   same canonical source without duplicating bodies?
4. Volatile facts: are file existence, path lists, index rows, and changed
   surfaces verified from current repository state?
5. Closure discipline: are AUTO-FIX, REVIEW, Remaining, and Next Actions
   separated without calling unresolved policy judgment "done"?

Output format
- Mode
- Sources Loaded
- Drift Candidates: target, reason, auto-fix, sync-required
- AUTO-FIX
- REVIEW
- Remaining
- R-points: every cross-review point must include one closure category:
  Fixed, Deferred-with-rationale, or Rejected. Do not use non-canonical labels.
- Final Verdict: closed / closed after minor fixes / still needs review /
  block merge
- Sync Required: true or false
```

## Self-Structured Review Checklist

Use when a cross-tool reviewer is unavailable (single-tool environment). Record
`reviewer: self-structured` in the Governor Footer. Work through each item
below and surface any findings as R-points with the same closure categories
(`Fixed` / `Deferred-with-rationale` / `Rejected`).

**F — Volatile workspace facts**
- [ ] All file paths and section references cited in this sync review have been
  re-verified from current file reads (not from memory or prior-session state).

**G — Closure discipline**
- [ ] Every drift candidate identified is closed with `Fixed`,
  `Deferred-with-rationale`, or `Rejected`. Non-canonical labels not used.

**H — Effect vs process**
- [ ] Drift questions ("is this file out of sync?") are answered by actually
  diffing the canonical and the copy, not by describing the sync process.

**I — Self-licensing check**
- [ ] Before declaring "Sync Required: false", the full consumer table in
  `governor-paths.md` was checked, not just the files I already intended to
  touch.

**Canonical-to-pointer verification**
- [ ] Every file that should link to the canonical source actually links to it
  (no re-declaration of path lists or rules that belong in the canonical).

**Language Policy**
- [ ] Any Tier 1 file modified contains only English prose (bilingual escape
  tokens and `LOCALE_DATA_FILES` are the two narrow exceptions).
