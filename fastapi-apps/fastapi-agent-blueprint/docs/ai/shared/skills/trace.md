# Trace — Read-Only Execution Path

## Default Flow Position
See [target-operating-model §1](../target-operating-model.md) — `trace` routing.

## Inline reference from fix-bug

When fix-bug reads this document inline, it uses only the execution-chain reference
and citation guidance below. No new fork is required. Fix-bug owns its active
investigation, Cause Impact Matrix, fix recommendations, edits, verification and
stage/ledger boundaries; the standalone isolation, read-only and no-fix restrictions
below do not replace those gates. Reading this reference is not invoking trace.

## Procedure

Use on demand to locate a concrete behavior's entry point, state/decision boundaries,
and observable result. Narrow to the requested symbol, endpoint, task, or symptom.
For a standalone trace invocation, run in an isolated/forked context with read-only
tools; if isolation is unavailable,
report that limitation before returning a bounded read-only result.

Start from observed entry-point registration, then follow actual calls and DI wiring.
Use the chain matching the actual registered entry point:

| Surface | Execution chain to verify |
|---|---|
| HTTP CRUD | Router → optional UseCase → Service → Repository |
| Worker / scheduler | broker message → `@broker.task` → Service → Repository; verify middleware order |
| Admin (NiceGUI) | `@ui.page` handler → Admin Page Config → `_get_service()` → Service |
| Optional infra / provider | `providers.Selector` → real/stub adapter branch → SDK where applicable |
| Harness / hook | tool event → per-tool shim → `.agents/shared/governor/` policy |
| Boot / config | Settings validator → container wiring → `bootstrap_app` |

Do not assume a router exists.
Inspect conversion/exclusion boundaries and config branches relevant to the question.
Static references show possible reachability, not proof a branch ran.

Return: scope and revision/config, ordered path with `file:line` citations, key
branch predicates, observation versus inference, and unknown edges. For a failure,
separate symptom site, propagation path, and earliest broken invariant. Stop at the
requested boundary; missing evidence is an explicit unknown, not an invented link.
Standalone trace does not edit, run mutating probes, prescribe a fix, or write the
work ledger.

Removal budget: relocates the sole execution-surface table in fix-bug Phase 2.
The bug workflow keeps its independent cause-impact and regression obligations;
using this reference inline there does not require spawning another investigation.
