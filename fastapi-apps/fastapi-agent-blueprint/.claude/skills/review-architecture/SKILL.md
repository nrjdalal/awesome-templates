---
name: review-architecture
argument-hint: domain_name or all
description: |
  Audit architecture compliance for a domain.
  Use when the user asks to "review architecture", "compliance audit",
  or wants to check if a domain follows project architecture rules.
---

# Architecture Compliance Audit

Target: $ARGUMENTS (domain name or "all")

## Default Flow Position
- Step: **`self-review`** (architecture commitments)
- Routes after: completion gate (`/sync-guidelines` if drift; otherwise `/review-pr`)
- Recursion guard: do not invoke `/review-architecture` recursively, do not invoke `/plan-feature` from inside

## Procedure Overview
1. Resolve the audit target and load the shared rule sources (Phase 0)
2. Audit the target against the 9 architecture checklist categories (Phase 1)
3. Determine `Drift Candidates` and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the shared review contract (Phase 3)

Read `docs/ai/shared/skills/review-architecture.md` for detailed steps and output format.
Also refer to `docs/ai/shared/architecture-review-checklist.md` for the full checklist.
For cross-tool review prompts, use the shared procedure's
`Cross-Tool Review Prompt Template` section; do not duplicate the template here.
