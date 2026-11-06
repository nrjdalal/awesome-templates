---
name: why
description: Explain a recorded architectural decision and its trade-offs from cited ADR and code evidence.
---

# Why

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `why` routing.

## Procedure

Read `docs/ai/shared/skills/why.md` and answer only the requested investigation.
Use an available read-only child context, or `codex exec --sandbox read-only`
with the question and the shared procedure path (do not recursively invoke `$why`).
Pass only necessary references and return the cited result. If isolation cannot run,
state that limitation and keep the investigation bounded and read-only.
