# 064. Scoped ADR Evidence in Agent Workflow

- Status: Accepted
- Date: 2026-11-06 (decision and recording date)
- Record type: contemporaneous — follow-up design requested during the original PR #434 review, for delivery through separate issue PRs; not an account of earlier deliberation
- Decision evidence: owner request in the [PR #434](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/434) review
- Related issue: none (delivered as a separate follow-up PR)
- Amends / supersedes: none; adds verified current ADR clauses to the Review Protocol rule-source list ([ADR 053](053-shared-review-protocol.md) carrier)
- Related: [ADR 060](060-ticket-session-boundaries-and-review-packets.md), [ADR 063](063-on-demand-harness-documentation.md)

## Problem and evidence

The owner asked to record worthwhile decisions and use ADRs as working evidence.
ADRs already explain many rules, but the planning packet does not connect a chosen
clause to its applicability and current implementation. A fresh execution session
can inherit a decision number without its scope. Review Protocol's rule-source
list also names checklists and AGENTS but gives no explicit path for a verified
current ADR clause. A citation can therefore become decoration or false authority.

A real counterexample is archived ADR 035, whose header still says Accepted.
ADR 039 replaces provider-class selection, while ADR 042 keeps enabled/disabled
selection. The word Selector or an Accepted header alone cannot settle either
scope. Current code and the later decisions must be inspected together.

## Alternatives

1. Load every ADR in every session and add an ADR-read checkbox. Rejected: fixed
   context cost grows, and reading or naming a document proves no applicability.
2. Add a runtime blocker or a citation-count linter. Rejected: filenames/counts
   cannot establish semantic applicability, truth, supersession or owner approval.
3. Use scoped decision evidence in existing workflow artifacts. Selected: one
   consulted guide defines the contract, and existing consumers carry its result.

## Decision

The [ADR evidence guide](../ai/shared/adr-evidence.md) owns scoped discovery,
status/supersession checks, clause applicability, current source/test/probe evidence,
and explicit conflict or uncertainty handling. Planning captures that basis inside
Selected Approach / Architecture Impact; ticket handoff carries it; execution
rechecks material premises; review uses the relevant clause and implementation
evidence; sync reconciles durable decisions and their dependent references.

No new packet field, Governor Footer field, runtime gate, skill, or always-loaded
ADR catalog is introduced. Work without a relevant durable decision states its
bounded reason; it does not invent an ADR. The shared procedure remains the owner
of each step. The guide changes evidence discipline, not the plan/execute boundary.

An ADR records intent and constraints. It is not proof of runtime behavior, a
permission grant, or a licence to override AGENTS precedence, sandbox policy or
the owner's explicit scope. Archived/superseded decisions are historical by
default; an active canonical source must explicitly carry forward any clause
still used. Contradictions are reported, not silently rationalized or rewritten.

## Consequences

- **ADR064-G1:** Decision evidence names the relevant status/clause, why its scope
  applies, and the current evidence supporting the claim. A bare ADR number or
  Accepted label cannot establish compliance or observed behavior.
- **ADR064-G2:** Carry the basis through existing plan/ticket/review/sync fields;
  recheck volatile premises in fresh execution. Keep lookup scoped and consulted.
- **ADR064-G3:** New durable choices record alternatives, trade-offs, provenance,
  consequences and revisit conditions honestly. Retrospective records identify
  that provenance and never invent contemporaneous debate or measured benefits.
- **ADR064-G4:** Preserve immutable governance slots and historical records. A
  changed durable constraint gets an explicit successor and dependent-reference
  synchronization; uncertainty or code drift cannot self-authorize redesign.

The cost is a small amount of task-specific evidence work. It avoids duplicating
full ADR bodies or treating every edit as an architecture decision. Static link
and consistency tests can catch broken routing; they cannot prove an agent has
reasoned correctly about a clause. Realistic forward checks and review remain
necessary. This is procedural guidance, not new mechanical enforcement.

## Verification and revisit

Verify discovery and handoff using the provider-selection counterexample and a
current governance-exemption question. Check that selected clauses are linked,
code evidence is inspected, historical intent is distinguished, and unresolved
claims remain explicit. Run existing link/language/context/inventory and workflow
checks after synchronization.

Revisit when repeated misses show the scoped lookup is insufficient, when the
guide adds measurable review burden, or when a deterministic check can prevent a
specific observed error without pretending to judge semantic applicability.
Record that evidence before adding another tool, catalog or hard gate.
