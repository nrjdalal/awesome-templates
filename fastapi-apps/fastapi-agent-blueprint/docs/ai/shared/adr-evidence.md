# ADR Evidence for Agent Work

Authority: [ADR 064](../../history/064-scoped-adr-evidence-in-agent-workflow.md).
Consult this reference when architecture, workflow, security boundaries or durable
trade-offs are relevant. It is not an instruction to read every historical ADR.

## Find the relevant decision

Start with the [history index](../../history/README.md), the affected canonical
rule, and topic/symbol searches in current ADRs. Follow only relevant references,
including the Decision, Consequences, amendments and supersession links. An index
entry, search excerpt or filename is a pointer; read the actual clause before
using it. Expand into archives or PR history only when provenance or a successor
requires it. Report missing history rather than inventing a reason.

Check status and scope together. Accepted does not mean every clause still
describes current code. Archived, Deprecated and Superseded records are historical
by default; if an active source explicitly carries a clause forward, cite that
current carrier too. A proposed decision is an option, not an existing obligation.
Resolve topic-level amendments instead of choosing whichever number supports the
desired answer. ADR 047's immutable G-slot and errata rules still apply.

## Record a decision basis

Use a short row or equivalent prose inside existing artifacts, only for relevant
decisions:

| Decision / claim | ADR, status and exact clause | Applicability / limits | Current evidence and disposition |
|---|---|---|---|
| What the work relies on | Linked decision/consequence or current successor | Why this domain, layer, path or mode is covered | Code symbol, test or observed command result; conform / conflict / unknown / new decision |

Evidence depth follows the claim. A code read can establish the configured branch
or contract; it cannot establish that a production branch ran or that a workflow
improved review time. Name unrun probes and unobserved effects. Recheck mutable
paths/configuration before consequential assertions (AGENTS Guard F).

If no ADR is relevant, state the bounded reason, such as "existing public schema
unchanged; local documentation typo, no durable choice." Do not create filler rows
or scan all history merely to prove absence. When relevant evidence is missing,
say unknown and identify the missing source; do not turn absence into permission.

## Carry it through the existing flow

- **Plan:** compare options against applicable clauses. Put the decision basis in
  Selected Approach / Architecture Impact, with supporting verification gates.
- **Ticket and execute:** carry the approved basis or an exact clause link from
  the parent packet. Recheck material source/config premises in the fresh context.
  Contradictory evidence becomes explicit drift or scope reconciliation; it is not
  permission to silently change the plan, waive ADR 054, or reopen every decision.
- **Review:** Sources Loaded lists the clauses actually read. A rule-source
  finding connects an applicable current clause to the concrete changed behavior
  or contract; the Coverage record explains conformity. Do not label a historical
  preference, bare citation or missing citation alone as a correctness defect.
- **Sync:** reconcile current decisions, implementation facts and dependent
  references. Record a durable new choice or explicit successor when necessary;
  keep ordinary changes in PR/CHANGELOG. Preserve historical snapshots and slots.
- **Why:** separate recorded rationale, current implementation and inference.
  Retrospective evidence cannot be presented as a contemporaneous conversation.

Preserve each clause's enforcement strength: an advisory decision does not become
a hard gate merely by being cited. Rationale and predicted benefits are not new
mandatory constraints.

Use existing review basis/closure vocabularies. This guide introduces no new
output section, mandatory footer field, approval authority or runtime detector.
The owner's scope and AGENTS precedence govern what may actually be changed.

## Resolve conflicts without self-licensing

When code and an applicable ADR disagree, verify both before deciding whether the
code regressed, documentation drifted, or an intentional decision needs recording.
Report the competing evidence and the smallest reconciliation consistent with the
authorized task. Escalate a genuinely new capability through ADR 050; preserve the
explicit plan/execute boundary. A new ADR must not retroactively manufacture
approval for a change or silently edit an immutable inherited constraint.

Record durable boundaries, public/security/data contracts, provider/DI choices,
changed guarantees and recurring team workflows. A rename, fixed link or measured
check result normally belongs in the PR rather than a new ADR. For retrospective
records, label the record type, link the actual implementation evidence, distinguish
known rationale from reconstruction, and state unobserved effects honestly.

## Worked applicability check

For "remove every embedding Selector because ADR 039 says no Selector":

1. [Archived ADR 035](../../history/archive/035-embedding-service-abstraction.md)
   describes per-provider client selection; its Accepted header alone is not
   current authority for restoring those clients.
2. [ADR 039 §No Selector pattern](../../history/039-pydantic-ai-embedder-transition.md#3-no-selector-pattern)
   removes the project-level choice between provider-specific adapter classes.
3. [ADR 042](../../history/042-optional-infrastructure-di-pattern.md) applies to
   enabled/disabled optional infrastructure, a different decision boundary.
4. Inspect `_build_embedding_client` and `CoreContainer.embedding_client` in
   [core_container.py](../../../src/_core/infrastructure/di/core_container.py):
   one PydanticAI adapter is built on the enabled branch, while a Selector retains
   the stub branch. These clauses coexist. Re-read current code before reusing
   this example; this text is not proof that a branch ran or a latency improved.

For a metadata-only update to consulted shared commands, historical ADR 047 D4 wording
cannot by itself establish the old cosmetic exemption. Read its current amendment,
[ADR 063](../../history/063-on-demand-harness-documentation.md), and the active
`SYNC_COSMETIC_FILES` in [sync_cosmetic.py](../../../.agents/shared/governor/sync_cosmetic.py).
The source location and changed content, not the old basename, determine coverage.

## Decision coverage for the #414/#427 work

This is a bounded map of this batch, not a new per-change archive or global catalog.

| Durable choice | Record |
|---|---|
| Codex completeness, bounded context, content-change dates and one-off histories | [ADR 059](../../history/059-harness-context-byte-budgets.md) |
| Ticket units, fresh execution, review risk/precision, integrated sync, on-demand investigation and prospective measurement | [ADR 060](../../history/060-ticket-session-boundaries-and-review-packets.md) |
| Runtime heuristic retirement, disclosed guarantees, real outcomes and cache continuity | [ADR 061](../../history/061-retire-runtime-verify-and-content-heuristics.md) |
| Generated membership, reviewed buckets and explicit retirement | [ADR 062](../../history/062-generated-harness-inventory.md) |
| Consulted/scoped sources, archive boundaries, compact DNA and notification authority | [ADR 063](../../history/063-on-demand-harness-documentation.md) |
| Task-scoped ADR evidence, truth/intent separation and decision lifecycle | [ADR 064](../../history/064-scoped-adr-evidence-in-agent-workflow.md) |
| Native discovery, routing ownership, shared procedure authority and thin-wrapper parity | [ADR 065](../../history/065-native-skill-discovery-and-procedure-authority.md) |
