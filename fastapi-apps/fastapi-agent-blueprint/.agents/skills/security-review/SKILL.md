---
name: security-review
description: Review a domain, file, or the full repository for OWASP-oriented security issues using the shared security checklist.
metadata:
  short-description: OWASP security audit
---

# Security Review

## Default Flow Position
- Step: **`self-review`** (security-sensitive surfaces: auth, tokens, sensitive fields, file upload, credentials)
- Routes after: completion gate (`/sync-guidelines` if drift; otherwise `/review-pr`)
- Recursion guard: do not invoke `/security-review` recursively, do not invoke `/plan-feature` from inside

## Procedure
1. Read `AGENTS.md` and `docs/ai/shared/skills/security-review.md` for the full procedure.
2. Read `docs/ai/shared/security-checklist.md` and `docs/ai/shared/project-dna.md` as the shared security rule sources.
3. Resolve the audit scope and run the feature-detection / reference-freshness preflight (Phase 0).
4. Audit the target against the 12 security checklist categories using the shared applicability rules (Phase 1).
5. Determine stale-reference drift, other `Drift Candidates`, and whether `Sync Required` is `true` or `false` (Phase 2).
6. Report using the shared review contract: `Scope`, `Effect Answer`, `Sources Loaded`, `Findings`, `Drift Candidates`, `Next Actions`, `Completion State`, `Sync Required` (Phase 3). `Effect Answer` is mandatory — see `docs/ai/shared/skills/security-review.md` § Review Contract for the field definition and Guard H context.

For cross-tool review prompts, use the `Cross-Tool Review Prompt Template`
section in `docs/ai/shared/skills/security-review.md`; do not duplicate it here.
