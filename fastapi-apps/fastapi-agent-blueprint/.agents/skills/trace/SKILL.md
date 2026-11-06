---
name: trace
description: Trace a concrete execution path with source citations in a read-only isolated context.
---

# Trace

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `trace` routing.

## Procedure

Read `docs/ai/shared/skills/trace.md` and answer only the requested investigation.
Use an available read-only child context, or `codex exec --sandbox read-only`
with the question and the shared procedure path (do not recursively invoke `$trace`).
Pass only necessary references and return the cited result. If isolation cannot run,
state that limitation and keep the investigation bounded and read-only.
