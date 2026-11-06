---
name: review-architecture
argument-hint: domain_name or all
description: |
  Audit architecture compliance for a domain.
  Use when the user asks to "review architecture", "compliance audit",
  or wants to check if a domain follows project architecture rules.
---

# Architecture Compliance Audit

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `review-architecture` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/review-architecture.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Resolve the audit target and load the shared rule sources (Phase 0)
2. Audit the target against the 10 architecture checklist categories (Phase 1)
3. Determine `Drift Candidates` and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the protocol output contract — `Findings` (open) + `Coverage` (OK/SKIP) + `Verdict: N/A (audit-only scope)` (Phase 3)

## Tool Sources
Shared `AGENTS.md`, `project-dna.md`, the shared checklist and live code are authoritative. When checking Claude projection drift, inspect both `.claude/rules/architecture-conventions.md` and `.claude/rules/project-overview.md` even if their scoped paths did not load them. For unrelated domain work, consult only relevant projections when needed; do not assume scoped rules are already present.
