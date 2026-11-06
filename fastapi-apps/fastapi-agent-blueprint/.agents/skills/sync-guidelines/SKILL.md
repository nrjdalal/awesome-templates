---
name: sync-guidelines
description: Inspect drift between code, shared workflow references, and Claude, Codex, or Antigravity harness assets after architecture or workflow changes.
metadata:
  short-description: Sync shared guidelines
---

# Sync Guidelines

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `sync-guidelines` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/sync-guidelines.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Determine the sync mode, gather incoming `Drift Candidates`, and load the governing sources (Phase 0)
2. Reconcile drift candidates with code, shared references, harness docs, and wrappers (Phase 1)
3. Refresh `project-dna` and dependent shared references as needed (Phase 2)
4. Verify Hybrid C parity for Claude and Codex wrappers plus Antigravity shared-source references, then close with the sync contract (Phase 3)
