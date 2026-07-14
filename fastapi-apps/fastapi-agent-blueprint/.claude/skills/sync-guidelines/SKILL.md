---
name: sync-guidelines
disable-model-invocation: true
description: |
  This skill should be used when the user asks to "sync guidelines",
  "document inspection", "check skill updates",
  "update project-dna", "sync patterns", "verify code-document consistency",
  or after architecture changes to verify Skills/AGENTS.md/CLAUDE.md match the actual code.
---

# Guideline Synchronization Inspection

## Default Flow Position
- Step: **`completion gate`** (or follow-up to `self-review` when drift detected)
- Routes after: end of work
- Recursion guard: do not invoke `/sync-guidelines` recursively, do not invoke `/plan-feature` from inside

## Procedure Overview
1. Determine the sync mode, gather incoming `Drift Candidates`, and load the governing sources (Phase 0)
2. Reconcile drift candidates with code, shared references, harness docs, and wrappers (Phase 1)
3. Refresh `project-dna` and dependent shared references as needed (Phase 2)
4. Verify Hybrid C parity for Claude and Codex wrappers plus Antigravity shared-source references, then close with the sync contract (Phase 3)

Read `docs/ai/shared/skills/sync-guidelines.md` for detailed steps.
Also refer to `docs/ai/shared/drift-checklist.md` for inspection items.

Closing summary must include: `Mode`, `Input Drift Candidates`, `project-dna`, `AUTO-FIX`, `REVIEW`, `Remaining`, `Next Actions` - see "Sync Contract" in the shared procedure.
For cross-tool review prompts, use the shared procedure's
`Cross-Tool Review Prompt Template` section; do not duplicate the template here.

## Claude-Specific Post-Steps

> This is a Claude-harness post-step.
> Codex may not have an equivalent post-step unless Codex-specific harness assets also require synchronization.

After completing the shared procedure:
1. Update `.claude/rules/architecture-conventions.md`
   (data flow, object roles, generic signatures changes)
2. Update `.claude/rules/project-status.md`
   (Recent Major Changes table, version context, violation status)
   - `git log --oneline --since="{last_synced_date}"` to identify major changes
   - project-dna.md §8 "Not implemented" items for Not Yet Implemented
   - Table hygiene (Phase 3 check): warn if row count > 15; check for cell-wrap issues; on version release, archive pre-release rows to `docs/history/archive/project-status/` (PR-B.1 pattern)
3. Update `.claude/rules/project-overview.md`
   (infrastructure options, environment config, app entrypoint changes)
4. Update `.claude/rules/commands.md`
   (new CLI commands, env vars, test commands, verification commands)

All rules files: update "Last synced" date line to current date.
