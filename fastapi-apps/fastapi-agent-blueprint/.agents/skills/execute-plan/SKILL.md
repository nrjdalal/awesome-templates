---
name: execute-plan
description: Execute an approved multi-task plan through native project workflow gates.
metadata:
  short-description: Native plan execution workflow
---

# Execute Plan

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `execute-plan` routing.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/execute-plan.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Read the approved Execution Packet and shared procedure.
2. Validate all required packet fields.
3. Record executing with update_workflow_state.
4. Execute dependent tasks through their mapped skills.
5. Pass each Verification Gate before task completion.
6. Run Review Gates and record actual review/fallback evidence.
7. Record complete only after verification and review pass.
