---
name: sync-guidelines
description: Inspect drift between code, shared workflow references, and Claude or Codex harness assets after architecture or workflow changes.
metadata:
  short-description: Sync shared guidelines
---

# Sync Guidelines

## Default Flow Position
- Step: **`completion gate`** (or follow-up to `self-review` when drift detected)
- Routes after: end of work
- Recursion guard: do not invoke `/sync-guidelines` recursively, do not invoke `/plan-feature` from inside

## Procedure Overview
1. Determine the sync mode, gather incoming `Drift Candidates`, and load the governing sources (Phase 0)
2. Reconcile drift candidates with code, shared references, harness docs, and wrappers (Phase 1)
3. Refresh `project-dna` and dependent shared references as needed (Phase 2)
4. Verify Hybrid C parity for both Claude and Codex wrappers; run `project-status.md` table hygiene check (row count > 15 → flag for archival, cell-wrap scan, version-release archive to `docs/history/archive/project-status/`); then close with the sync contract (Phase 3)

Read `AGENTS.md` and `docs/ai/shared/skills/sync-guidelines.md` for detailed steps.
Also refer to `docs/ai/shared/drift-checklist.md` for inspection items.

Closing summary must include: `Mode`, `Input Drift Candidates`, `project-dna`, `AUTO-FIX`, `REVIEW`, `Remaining`, `Next Actions` - see "Sync Contract" in the shared procedure.
For cross-tool review prompts, use the shared procedure's
`Cross-Tool Review Prompt Template` section; do not duplicate the template here.
