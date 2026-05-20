---
name: add-worker-task
description: Add a Taskiq worker task with an explicit payload contract, thin task adapter, and Service-owned business logic.
metadata:
  short-description: Add async worker task
---

# Add Worker Task

## Default Flow Position
- Step: `implement` (`approach options` upstream conditional — required for new event types or broker patterns)
- Routes after: verify (`/test-domain {name} run`, optional `make worker` smoke run)
- Recursion guard: do not invoke `/plan-feature` from inside this skill

## Procedure
1. Read `AGENTS.md` and `docs/ai/shared/skills/add-worker-task.md` for the full procedure.
2. Read `docs/ai/shared/project-dna.md` for DI and conversion patterns.
3. Confirm the target Service method exists; add it first if needed.
4. Create payload schema, task function, and bootstrap wiring.
5. Keep the task thin: validate payload, then call the Service.
6. Verify imports and run targeted checks on the new worker files.
