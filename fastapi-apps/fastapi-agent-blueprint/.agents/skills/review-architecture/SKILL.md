---
name: review-architecture
description: Audit a domain or the full repository for architecture compliance using the shared architecture checklist and repository rules.
metadata:
  short-description: Architecture compliance audit
---

# Review Architecture

## Default Flow Position
- Step: **`self-review`** (architecture commitments)
- Routes after: completion gate (`/sync-guidelines` if drift; otherwise `/review-pr`)
- Recursion guard: do not invoke `/review-architecture` recursively, do not invoke `/plan-feature` from inside

## Procedure
1. Read `AGENTS.md` and `docs/ai/shared/skills/review-architecture.md` for the full procedure.
2. Read `docs/ai/shared/architecture-review-checklist.md` and `docs/ai/shared/project-dna.md` as the shared architecture rule sources.
3. Resolve the audit target and load the shared rule sources (Phase 0).
4. Audit the target against the 9 architecture checklist categories (Phase 1).
5. Determine `Drift Candidates` and whether `Sync Required` is `true` or `false` (Phase 2).
6. Report using the shared review contract: `Scope`, `Effect Answer`, `Sources Loaded`, `Findings`, `Drift Candidates`, `Next Actions`, `Completion State`, `Sync Required` (Phase 3). `Effect Answer` is mandatory — see `docs/ai/shared/skills/review-architecture.md` § Review Contract for the field definition and Guard H context.

For cross-tool review prompts, use the `Cross-Tool Review Prompt Template`
section in `docs/ai/shared/skills/review-architecture.md`; do not duplicate it here.
