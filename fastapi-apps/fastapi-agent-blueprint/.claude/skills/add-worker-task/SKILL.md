---
name: add-worker-task
argument-hint: domain_name task_name
description: |
  This skill should be used when the user asks to
  "add worker task", "add async task", "add background job",
  "queue task", "Taskiq task",
  or wants to create a new asynchronous background task for a domain.
---

# Add Async Worker Task

Request: $ARGUMENTS (domain name and task description, e.g.: "order process_payment")

## Default Flow Position
- Step: `implement` (`approach options` upstream conditional — required for new event types or broker patterns)
- Routes after: `/test-domain {name} run` (verify) → `make worker` smoke run if applicable
- Recursion guard: do not invoke `/plan-feature` from inside this skill

## Procedure Overview
1. Analysis — identify domain, task purpose, check existing Service method
2. Implementation — Payload schema → Task function → Worker bootstrap → Service method
3. Verification — pre-commit, import check

Read `docs/ai/shared/skills/add-worker-task.md` for detailed steps and code templates.
Also refer to `docs/ai/shared/project-dna.md` §5 for DI patterns and §6 for conversion patterns.
