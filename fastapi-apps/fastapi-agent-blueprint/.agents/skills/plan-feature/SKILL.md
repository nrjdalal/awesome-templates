---
name: plan-feature
description: Guide a feature from requirements interview through architecture analysis, security check, and task decomposition.
metadata:
  short-description: Feature implementation planning
---

# Plan Feature

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `plan-feature` routing.
Recursion guard: Do not invoke this skill recursively; implementation skills must not re-enter planning (ADR 050 scope expansion is separate).

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/plan-feature.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Requirements Interview (Phase 0).
2. Compare Approach Options (Phase 1).
3. Architecture Impact Analysis (Phase 2).
4. Security Checkpoint (Phase 3).
5. Task Breakdown (Phase 4).
6. Produce the Execution Packet: Goal, Scope, Success Criteria, Selected Approach, Architecture Impact, Task List, Verification Gates, Review Gates.
7. After approval use update_workflow_state to record planned; stop. Execution requires a separate execute-plan invocation (ADR 054).
