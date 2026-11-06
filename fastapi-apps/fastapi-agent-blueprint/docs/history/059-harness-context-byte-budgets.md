# 059. Harness Context Byte Budgets

- Status: Accepted
- Date: 2026-11-06
- Related issues: #413, #414, #415, #416, #417

## Summary

Bound automatic session context with a blocking, index-selected byte checker.
Dates record content changes; they do not create periodic documentation work.

## Background

The #414 audit found that line-count and table-row-count limits allowed growth
inside individual lines. Long sync headers had become retrospective archives,
and AGENTS.md exceeded Codex's default project-document allowance (#413).
Shrinking those files once cannot prevent the same growth from recurring.

## Alternatives Considered

### A. Keep freshness dates and a manual line-count target

Rejected: neither measures the bytes injected into a session. Updating dates
for unchanged files also creates conflicts and gives histories another home.

### B. Delete governance hooks and shared architecture rules

Rejected: the audit did not establish equivalent replacements for those
responsibilities. Context savings do not justify removing product guarantees.

### C. Check bytes, keep policy, archive historical narrative once

Selected: sizes are deterministic facts. A full-index scan catches growth even
when the triggering change did not edit the file that consumes the budget.

## Decision

`tools/check_context_budget.py` is a blocking pre-commit check. It reads the
working-tree contents of index-selected files; untracked local files cannot
change the scan. It checks:

- The total bytes of CLAUDE.md and rules without nonempty `paths` frontmatter.
- Each rules file's full size, including scoped rules and fenced examples.
- Short sync headers (Last synced or Last updated) and whole Markdown rows,
  including pipes and links, inside the Recent Major Changes table.
- An absolute AGENTS.md budget below the default Codex document allowance.

Checker budget limits live in the checker and its hook-registration comment only.
The independent native project-document allowance is configured in
[.codex/config.toml](../../.codex/config.toml); it is not another checker budget.
Fenced examples are excluded from line checks but still consume file/total
bytes. General shared-document prose and tables are outside line-cap scope;
their migration requires a later, measured ratchet rather than retroactive
failures across unrelated documents.

A rules file's sync date equals its most recent substantive content change.
Do not touch an unchanged file merely because its date is old. A sync header is
one short provenance line; detailed explanation belongs in CHANGELOG and the
PR body. Existing narrative is archived once with its source provenance.
Routine sync does not append to the historical archive, preserving ADR 047 D4.

The initial total and file ceilings leave headroom above the compacted tree.
At each quarterly review, measure the same tracked set, lower ceilings when
observed usage permits, and record before/after measurements in the PR.
Raising a ceiling is governor-changing: justify the need and include independent
review and a Governor Footer. Do not raise it to avoid moving a retrospective.

## Consequences

### Durable Governance Constraints

- **ADR059-G1**: Context-budget increases require governor-changing review.
  Preserve the index-selected scan, content-change dates, actionable
  `file:line` failures, and separate fenced-line vs full-file counting.

- **ADR059-G2 — Independent loading defenses:** the lean AGENTS budget and native
  project-document allowance are distinct controls. Changing either requires
  checking actual tail ingestion independently of the configured margin; do not
  treat a setting value or historical CLI observation as proof of loaded context.

### Verification and fork policy

Run the checker, its unit tests, the language/link checks, and all pre-commit
hooks after synchronization. The closing sync output must itself fit the
limits; record that self-application measurement in the PR description.

Forks may use `SKIP=context-budget` for a deliberate local bypass. A bypass is
not a passing verification result and does not replace the review requirement
for changing this repository's policy. Existing safety, stage, locale and
review-provenance semantics are unchanged.

## Supplementary Decision Record — Native Loading and Lean Source

This supplement records the implemented #413/#414 choice retrospectively, after
[PR #434](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/434) assembled
the reviewed batch before the owner requested separate issue PRs. That superseded
PR preserves the original review evidence; it is not the delivery target or merge
authorization. Issue #413 explicitly required both defenses and described
the weakness of either partial fix. This is not a claim that every comparison
below was a separate formal design session.

### Choice and partial alternatives

- **Configuration only:** raising the native loading allowance can restore the
  truncated tail immediately. It leaves document growth unchecked and makes
  visibility depend entirely on that configuration being applied and honored.
- **Trimming only:** keeping AGENTS below the default-sized loading budget restores
  portability and reduces fixed context, but leaves no independent loading margin
  when user/ancestor project instructions or future loading behavior differ.
- **Both, selected:** retain the smaller, blocking AGENTS budget and a separate
  repository native allowance with headroom. The allowance is defense in depth,
  never permission to regrow the constitution or raise a checker ceiling.

The cost is coordinating two different controls and an actual ingestion probe;
a byte count alone cannot prove that a CLI loaded the file. Runtime settings
remain tool-specific, while source compactness is a shared obligation.

### Evidence, validation and reconsideration

The silent truncation reported in [#413](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/413)
is an observation of its stated CLI/environment. The superseded PR #434 records
a successful explicitly default-sized tail probe in its tested environment as
historical verification evidence. Neither observation
establishes a timeless default or proves all CLI versions honor project settings.
The [live healthcheck](../ai/shared/commands.md#codex-healthcheck) deliberately
checks the final AGENTS section with an explicit default-sized override; the
[tail regression](../../tests/unit/tools/test_project_doc_tail.py) also pins that
marker as the final section. The configured allowance therefore cannot hide a
failure of the lean-source probe.

Re-check current vendor documentation and actual ingestion when the CLI loader,
trust/config precedence, ancestor instructions or project-document setting
changes. If the tail disappears despite passing byte checks, investigate the
loader/config contract before raising a ceiling. Revisit the need for the
configuration margin only with evidence that the lean-source rule and actual
loading remain reliable; a coherent change updates config, probes, documentation
and affected checks together. The quarterly ratchet above governs checker
ceilings, not an assumed vendor default.
