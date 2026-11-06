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
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `sync-guidelines` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/sync-guidelines.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Determine the sync mode, gather incoming `Drift Candidates`, and load the governing sources (Phase 0)
2. Reconcile drift candidates with code, shared references, harness docs, and wrappers (Phase 1)
3. Refresh `project-dna` and dependent shared references as needed (Phase 2)
4. Verify Hybrid C parity for Claude and Codex wrappers plus Antigravity shared-source references, then close with the sync contract (Phase 3)

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
   - Table hygiene (Phase 3 check): require each data row <= 300 UTF-8 bytes including pipes, all cells, and links, with a one-sentence impact; narrative belongs in `CHANGELOG.md [Unreleased]` and the PR body, never a per-PR archive write; warn if row count > 15; check for cell-wrap issues; on version release, archive pre-release rows to `docs/history/archive/project-status/` (PR-B.1 pattern)
3. Update `.claude/rules/project-overview.md`
   (infrastructure options, environment config, app entrypoint changes)
4. Update `docs/ai/shared/commands.md` only when its command surface changes
   (new CLI commands, env vars, test commands, verification commands)

Optional-infra behaviour (toggles, env vars, dispatch semantics) is described once in `AGENTS.md` § Optional Infrastructure Toggles plus its `docs/operations/` runbook; `.claude/rules/*` carry a one-line pointer only.

All rules files and project-dna: use `> Last synced: YYYY-MM-DD via <reference>` (<= 200 UTF-8 bytes); update the date without narrative or `Prior:` chains. Preserve historical chains in the one-off sync-log archive; do not append to it per PR.

Context-budget gate: run `uv run python tools/check_context_budget.py` after sync.
The blocking hook enforces byte limits previously checked by eye. Sync dates equal
the last content change; do not touch a file whose content did not change.

## Tool Sources
Shared `AGENTS.md`, `project-dna.md`, the shared checklist and live code are authoritative. When checking Claude projection drift, inspect both `.claude/rules/architecture-conventions.md` and `.claude/rules/project-overview.md` even if their scoped paths did not load them. For unrelated domain work, consult only relevant projections when needed; do not assume scoped rules are already present.
