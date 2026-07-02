---
name: execute-plan
description: Execute an approved multi-task plan through native project workflow gates.
metadata:
  short-description: Native plan execution workflow
---

# Execute Plan

## Default Flow Position
- Steps: **`implement`** + **`verify`** + **`self-review`** + **`completion gate`**
- Consumes: approved **Execution Packet** from `$plan-feature`
- Scope: complex, architecture-changing, governor-changing, or multi-task work

## Procedure Overview
1. Read `AGENTS.md` and `docs/ai/shared/skills/execute-plan.md`.
2. Confirm the Execution Packet contains Goal, Scope, Success Criteria,
   Selected Approach, Architecture Impact, Task List, Verification Gates, and
   Review Gates.
3. Record workflow state with `update_workflow_state(...)`.
4. Execute each task in dependency order, invoking the mapped implementation
   skill when available.
5. Run each task's Verification Gates before marking it complete.
6. Run Review Gates. Governor-changing work defaults to cross-tool review by
   the other harness (Codex-implemented work → Claude review), with
   `self-structured` or `human:<handle>` fallback when the reviewing tool is
   unavailable.
7. Update the ledger to `stage="complete"` only after verification and review
   are satisfied.

Read `docs/ai/shared/skills/execute-plan.md` for the full procedure.
