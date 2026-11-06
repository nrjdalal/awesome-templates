---
name: security-review
description: Review a domain, file, or the full repository for OWASP-oriented security issues using the shared security checklist.
metadata:
  short-description: OWASP security audit
---

# Security Review

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `security-review` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/security-review.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Resolve the audit scope and run the feature-detection / reference-freshness preflight (Phase 0)
2. Audit the target against the 13 security checklist categories (Phase 1)
3. Determine stale-reference drift, other `Drift Candidates`, and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the protocol output contract — `Findings` (open) + `Coverage` (OK/SKIP) + `Verdict: N/A (audit-only scope)` (Phase 3)
