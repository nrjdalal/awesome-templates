# 060. Ticket Session Boundaries and Review Packets

- Status: Accepted
- Date: 2026-11-06
- Issue: #427; lightweighting dependency: #414 B7
- Amends: ADR [052](052-native-execution-ledger-and-execute-plan.md) D1/D3 and
  ADR [054](054-plan-execute-boundary-hard-gate.md) execution handoff only.

## Problem and evidence

Issue #427 compares the existing single-session workflow with ticket sessions.
Its [source comment](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/427#issuecomment-6569342493)
records observational repository data and external studies, including selection
bias and the absence of owner-active-review-time measurements. There is no
observed failure of the current execution topology and no local A/B evidence.
We need a reviewable handoff and a measurable baseline before buying orchestration.

## Alternatives

1. Keep one long session and local ledger as the handoff: cheapest process change,
   but local state cannot independently establish approval or PR/CI completion.
2. Add an external multi-agent orchestrator: can parallelize independent work,
   but creates dependency/state machinery before review capacity is measured.
3. Use native issues and a compact ticket brief, fresh serial execution, and a
   small review packet: adds handoff cost but makes intent and evidence durable.

## Decision

Choose option 3 as an operating default, not a proven quality or cost improvement.
[Ticket workflow](../ai/shared/ticket-workflow.md) owns the detailed contract:
Epic = one Execution Packet, Ticket = one PR/worktree/fresh execution session,
Task = a step within a ticket. Planning publishes ticket briefs and stops;
`execute-plan <issue>` explicitly starts a fresh execution session. Existing
explicit authorization is retained. No runtime session detector or new ledger
schema is introduced.

The issue/approved packet, PR, and CI carry durable intent and evidence. ADR 052's
ledger remains versioned, fail-open, and shared across tools within the worktree,
but is a local resume cache hydrated from the ticket, not authoritative approval
or cross-ticket status. ADR 054's explicit execute-plan/waiver boundary and
existing Claude block/Codex advisory implementations remain unchanged. The block
still requires a positive local `planned` ledger in the planning checkout. A fresh
ticket worktree has no gitignored ledger, so that pre-edit block cannot fire there
until such local state exists. The execution handoff relies on explicit
`execute-plan <issue>` invocation and ledger hydration, not a runtime fresh-session
or approval detector. This is a documented enforcement limit, not a new guarantee.

Default to serial tickets; parallelize only with disjoint file sets, satisfied
dependencies, and human review capacity. Derive a review-risk floor from paths
and diff size. Run one verified P0/P1 precision-filter cross-vendor review round
per implementation ticket, with documented fallback when unavailable. Explicit
full audits retain their existing coverage. Integrate sync into the feature PR;
release/post-merge audits may still be standalone.

## Consequences

- **ADR060-G1:** Durable ticket/PR/CI evidence outranks the local ledger; neither
  green CI nor issue closure alone certifies the acceptance criteria. Preserve
  ADR 052's schema compatibility and ADR 054's plan/execute boundary.
- **ADR060-G2:** Risk classification is a deterministic floor, separate from
  governor path tiers. Review may increase depth; it cannot use a low score to
  waive architecture, security, or governor obligations.
- **ADR060-G3:** Precision-filter review verifies concrete severe defects before
  reporting them. It does not replace deterministic gates, full requested audits,
  known-finding closure, or the owner's final diff review.
- **ADR060-G4:** Sync remains required when triggered; putting it in the feature PR
  removes a dedicated PR slot, not review or drift work. Footer history auditing
  runs at release; each feature checks its own footer.
- Fresh contexts can cost more when briefs omit evidence. Measure active review,
  corrections, fix-ups, and optional quota observations before claiming a benefit.
  On-demand trace/why replace named duplicated reference material; they add no
  always-loaded prose or automatic exploration.
