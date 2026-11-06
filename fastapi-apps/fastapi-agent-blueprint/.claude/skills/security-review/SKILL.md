---
name: security-review
argument-hint: "domain_name, file_path, or all"
description: |
  OWASP-based code security audit for a domain or file.
  Use when the user asks to "security review", "security audit", "OWASP check",
  or wants to audit code security for a domain or file.
---

# OWASP-Based Code Security Audit

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `security-review` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/security-review.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Resolve the audit scope and run the feature-detection / reference-freshness preflight (Phase 0)
2. Audit the target against the 13 security checklist categories (Phase 1)
3. Determine stale-reference drift, other `Drift Candidates`, and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the protocol output contract — `Findings` (open) + `Coverage` (OK/SKIP) + `Verdict: N/A (audit-only scope)` (Phase 3)
