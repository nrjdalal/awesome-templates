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

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-worker-task` routing.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/add-worker-task.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — identify domain, task purpose, check existing Service method
2. Implementation — Payload schema → Task function → Worker bootstrap → Service method
3. Verification — pre-commit, import check
