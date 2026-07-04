---
name: review-pr
argument-hint: "PR number, URL, or omit to detect current branch"
description: |
  Review a pull request against the shared Review Protocol (correctness,
  regression, stability, contract, architecture, security).
  Use when the user asks to "review PR", "check PR", "PR review",
  or wants an evidence-grounded review of a pull request before merge.
---

# Pull Request Quality Gate Review

Target: $ARGUMENTS (PR number, GitHub URL, or empty for current branch)

## Default Flow Position
- Step: **`completion gate`** (final review at end of work)
- Routes after: `/sync-guidelines` if drift detected
- Recursion guard: do not invoke `/review-pr` recursively, do not invoke `/plan-feature` from inside

## Procedure Overview
1. Resolve PR; collect diff + **intent** (PR body / issue / acceptance criteria) and load the
   Review Protocol + its checklists (Phase 0)
2. Review changed files against the protocol dimensions — `CORR / REG / STAB / CONTRACT /
   ARCH / SEC / GOV` (Phase 1)
3. Determine `Drift Candidates` and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the protocol output contract — `Findings` (open) + `Coverage` (OK/SKIP) +
   `Verdict` (Phase 3)
5. Post to GitHub per protocol §5 only after user confirmation (Phase 4)

Read `docs/ai/shared/skills/review-pr.md` for detailed steps, and
[`docs/ai/shared/review-protocol.md`](../../../docs/ai/shared/review-protocol.md) for the shared
dimensions, finding basis, output contract, and posting rules.
For cross-tool review prompts, use the shared procedure's `Cross-Tool Review Prompt Template`
section; do not duplicate the template here.

## Claude-Specific: Finding Basis
Every finding obeys the protocol's [Finding Basis rule](../../../docs/ai/shared/review-protocol.md#2-finding-basis-anti-hallucination-rule):
`ARCH` / `SEC` / `GOV` findings must cite a shared rule source (you may navigate via
`.claude/rules/architecture-conventions.md`, but the citation is the shared checklist / `AGENTS.md`);
`CORR` / `REG` / `STAB` / `CONTRACT` findings must cite `diff` / `contract` / `test` / `runtime`
evidence. A concern with no basis is a `Question`, not a finding.
