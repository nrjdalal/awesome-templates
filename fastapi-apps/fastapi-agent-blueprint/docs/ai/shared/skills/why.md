# Why — Read-Only Decision Provenance

## Default Flow Position
See [target-operating-model §1](../target-operating-model.md) — `why` routing.

## Procedure

Use on demand for the reason behind an existing architectural or workflow choice.
Run in an isolated/forked context with read-only tools. Report unavailable isolation
as a limitation; never imply a new context existed when it did not.

Use the [scoped Decision Basis contract](../adr-evidence.md): find only relevant
clauses through [the history index](../../../history/README.md), verify their
applicability and status/amendments/current carrier, then connect the recorded
choice to current code/test evidence or an explicit unknown. An Accepted header
is not implementation proof. Archived ADRs supply history unless an explicit
current rule carries the constraint; later dates alone do not establish precedence.
Read the problem, actual alternatives and consequences needed for the question;
follow issue/PR history only to resolve provenance or a conflict. Distinguish a
contemporaneous source from a retrospective author's reconstruction.

Return: the original problem, alternatives actually considered, recorded trade-off,
current constraints, and evidence links/`file:line` citations. Separate recorded
reason, present behavior, and inference; say when intent is unavailable or code has
drifted. Do not invent a rationale to defend the current design. Do not edit,
rewrite history, prescribe a redesign, or update workflow state. Identify unresolved
clause/code conflicts and conditions for revisiting; if a new decision is needed,
report the separate planning/revisit route without invoking it or treating this
read-only explanation as approval to implement.

Removal budget: replaces onboard Phase 1.2's four scripted history stories.
Onboarding retains its required structural/DTO/layer/DI topics and uses source-based
explanations adapted to the contributor rather than a fixed retrospective narrative.
