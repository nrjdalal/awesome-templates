---
name: review-pr
description: Review a pull request or local diff against the repository's shared Review Protocol (correctness, regression, stability, contract, architecture, security, governance).
metadata:
  short-description: Review PR or local diff
---

# Review PR

## Default Flow Position
- Step: **`completion gate`** (final review at end of work)
- Routes after: `/sync-guidelines` if drift detected
- Recursion guard: do not invoke `/review-pr` recursively, do not invoke `/plan-feature` from inside

## Procedure
1. Read `AGENTS.md`, `docs/ai/shared/review-protocol.md`, and `docs/ai/shared/skills/review-pr.md` for the full procedure.
2. Read `docs/ai/shared/architecture-review-checklist.md` (ARCH), `docs/ai/shared/security-checklist.md` (SEC), and `docs/ai/shared/project-dna.md` as the shared rule sources the protocol references.
3. Resolve the review target, collect the diff + intent, and load the rule sources (Phase 0).
4. Review changed files against the protocol dimensions — `CORR / REG / STAB / CONTRACT / ARCH / SEC / GOV`; each finding carries a dimension ID + a basis (Phase 1).
5. Determine `Drift Candidates` and whether `Sync Required` is `true` or `false` (Phase 2).
6. Report using the protocol output contract: `Scope`, `Effect Answer`, `Sources Loaded`, `Findings` (open only), `Coverage` (OK/SKIP), `Drift Candidates`, `Verdict`, `Next Actions`, `Completion State`, `Sync Required` (Phase 3). `Effect Answer` is mandatory — see `docs/ai/shared/review-protocol.md` §3 for the contract and Guard H context.
7. Optionally post the final review per protocol §5 after user confirmation (Phase 4).

For cross-tool review prompts, use the `Cross-Tool Review Prompt Template`
section in `docs/ai/shared/skills/review-pr.md`; do not duplicate it here.
