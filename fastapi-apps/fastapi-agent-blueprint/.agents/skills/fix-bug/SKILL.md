---
name: fix-bug
description: Investigate, reproduce, fix, and verify a bug while staying inside existing repository patterns and architecture rules.
metadata:
  short-description: Structured bug-fix workflow
---

# Fix Bug

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `fix-bug` routing.
Recursion guard: Do not recurse or invoke plan-feature for the bug’s own framing/plan; ADR 050 scope expansion still routes to plan-feature.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/fix-bug.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Reproduce: prove the reported failure before writing a red test; otherwise exit not-a-bug or cannot-reproduce without implementation.
2. Trace: distinguish symptom, propagation and root cause; close the Cause Impact Matrix.
3. Fix at the earliest boundary owning the invariant; explain why tests missed it.
4. Verify the reproduction, focused regression coverage, pyright and pre-commit.
5. Emit Bug Fix Report with Outcome, evidence, Drift Candidates and Sync Required, including on early exits.
6. Commit is opt-in after the user authorizes it.
