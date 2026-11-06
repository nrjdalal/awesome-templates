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

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `review-pr` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/review-pr.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Resolve the target and intent; load sources and prior Summary Finding Ledgers (Phase 0).
2. Review all required protocol dimensions with evidence (Phase 1).
3. Resolve Drift Candidates and Sync Required (Phase 2).
4. Report the full protocol contract, including Effect Answer and open findings (Phase 3).
5. Post externally only with authorization under protocol §5 (Phase 4).
