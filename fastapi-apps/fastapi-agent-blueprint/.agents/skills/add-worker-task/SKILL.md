---
name: add-worker-task
description: Add a Taskiq worker task with an explicit payload contract, thin task adapter, and Service-owned business logic.
metadata:
  short-description: Add async worker task
---

# Add Worker Task

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-worker-task` routing.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/add-worker-task.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — identify domain, task purpose, check existing Service method
2. Implementation — Payload schema → Task function → Worker bootstrap → Service method
3. Verification — pre-commit, import check
