---
name: plan-feature
argument-hint: feature description
description: |
  This skill should be used when the user asks to
  "plan feature", "design feature",
  or wants to plan and design a new feature before implementation.
---

# Feature Implementation Planning

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `plan-feature` routing.
Recursion guard: Do not invoke this skill recursively; implementation skills must not re-enter planning (ADR 050 scope expansion is separate).

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/plan-feature.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Requirements Interview (Phase 0).
2. Compare Approach Options (Phase 1).
3. Architecture Impact Analysis (Phase 2).
4. Security Checkpoint (Phase 3).
5. Task Breakdown (Phase 4).
6. Produce the Execution Packet: Goal, Scope, Success Criteria, Selected Approach, Architecture Impact, Task List, Verification Gates, Review Gates.
7. After approval use update_workflow_state to record planned; stop. Execution requires a separate execute-plan invocation (ADR 054).
