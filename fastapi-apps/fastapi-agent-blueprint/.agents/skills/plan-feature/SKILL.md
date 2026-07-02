---
name: plan-feature
description: Guide a feature from requirements interview through architecture analysis, security check, and task decomposition.
metadata:
  short-description: Feature implementation planning
---

# Plan Feature

## Default Flow Position
- Steps: **`framing`** (Phase 0) + **`approach options`** (Phase 1) + **`plan`** (Phases 2~4)
- Routes after: hand off to the appropriate `implement` skill
- Recursion guard: do not invoke `/plan-feature` recursively. Implement skills must not call `/plan-feature` (planning happens before implement)

## Procedure Overview
1. Requirements Interview — 3-5 questions from 5 categories (Phase 0)
2. Approach Options — propose 2-3 candidates with trade-offs, recommend one (Phase 1)
3. Architecture Impact Analysis — layer, domain, DTO, cross-domain (Phase 2)
4. Security Checkpoint — 6-item assessment matrix (Phase 3)
5. Task Breakdown — skill mapping, supervision levels, execution order (Phase 4)
6. Execution Packet — include Goal, Scope, Success Criteria, Selected Approach,
   Architecture Impact, Task List, Verification Gates, and Review Gates.
7. Work-ledger update — after task breakdown is confirmed, record goal/scope/plan and workflow state via
   `from work_ledger import update_goal_scope_plan, update_workflow_state; update_goal_scope_plan(goal=..., scope=..., plan=..., updated_by="skill:plan-feature"); update_workflow_state(stage="planned", plan_ref=..., tasks=..., updated_by="skill:plan-feature")`

1. Read `AGENTS.md` and `docs/ai/shared/skills/plan-feature.md` for the full procedure.
2. Read `docs/ai/shared/planning-checklists.md` for question bank and templates.
3. Interview the user on requirements (data model, business rules, integrations).
4. Propose 2-3 approach options with trade-offs and recommend one.
5. Analyze architecture impact, run security checkpoint, break into tasks.
6. Present the implementation plan in the standard output format, including the Execution Packet.
7. After approval, hand complex, architecture-changing, governor-changing, or multi-task work to `$execute-plan`.
