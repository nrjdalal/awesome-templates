---
name: review-architecture
description: Audit a domain or the full repository for architecture compliance using the shared architecture checklist and repository rules.
metadata:
  short-description: Architecture compliance audit
---

# Review Architecture

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `review-architecture` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/review-architecture.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Resolve the audit target and load the shared rule sources (Phase 0)
2. Audit the target against the 10 architecture checklist categories (Phase 1)
3. Determine `Drift Candidates` and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the protocol output contract — `Findings` (open) + `Coverage` (OK/SKIP) + `Verdict: N/A (audit-only scope)` (Phase 3)
