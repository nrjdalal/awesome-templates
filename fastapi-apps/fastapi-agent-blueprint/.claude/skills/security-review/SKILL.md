---
name: security-review
argument-hint: "domain_name, file_path, or all"
description: |
  OWASP-based code security audit for a domain or file.
  Use when the user asks to "security review", "security audit", "OWASP check",
  or wants to audit code security for a domain or file.
---

# OWASP-Based Code Security Audit

Target: $ARGUMENTS (domain name, file path, or "all")

## Default Flow Position
- Step: **`self-review`** (security-sensitive surfaces: auth, tokens, sensitive fields, file upload, credentials)
- Routes after: completion gate (`/sync-guidelines` if drift; otherwise `/review-pr`)
- Recursion guard: do not invoke `/security-review` recursively, do not invoke `/plan-feature` from inside

## Procedure Overview
1. Resolve the audit scope and run the feature-detection / reference-freshness preflight (Phase 0)
2. Audit the target against the 12 security checklist categories (Phase 1)
3. Determine stale-reference drift, other `Drift Candidates`, and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the shared review contract (Phase 3)

Read `docs/ai/shared/skills/security-review.md` for detailed steps and output format.
Also refer to `docs/ai/shared/security-checklist.md` for the full checklist.
For cross-tool review prompts, use the shared procedure's
`Cross-Tool Review Prompt Template` section; do not duplicate the template here.
