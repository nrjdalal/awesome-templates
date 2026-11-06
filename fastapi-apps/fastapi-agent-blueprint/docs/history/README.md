# Architecture Decision History

This directory records the reasoning behind the structural and technology
choices that shape how code is written in this project.

> **Not every decision is required reading.** The entries below are the
> load-bearing set — the active decisions a contributor needs to internalize to
> work anywhere in the codebase (they are exactly the non-archived ADRs).
> Superseded, operational, and tooling decisions have been preserved under
> [`archive/`](archive/) so the historical record is intact without burying the
> core set.

## Start here — core reading order

Read top-to-bottom; each builds on the ones above it.

### 1. Structural foundations

| # | Title | Why it matters |
|---|-------|----------------|
| [006](006-ddd-layered-architecture.md) | Per-Domain Layered Architecture | The shape of every `src/<domain>/` folder. |
| [011](011-3tier-hybrid-architecture.md) | 3-Tier Hybrid (BaseService) | When to write a UseCase vs. a plain Service; `BaseService` 3-TypeVar contract. |
| [007](007-di-container-and-app-separation.md) | DI Container Layering and App Separation | How CoreContainer, DomainContainer, and DynamicContainer fit together. |
| [019](019-domain-auto-discovery.md) | Domain Auto-Discovery | Why adding a new domain needs no container edits. |
| [022](022-underscore-prefix-convention.md) | Underscore Prefix Convention | Why `_core`, `_apps` lead with an underscore; what it signals. |
| [043](043-responsibility-driven-refactor.md) | Responsibility-Driven Refactor | Where provider SDKs, exception mapping, and typed service contracts belong — layer responsibilities readable from the code structure. |

### 2. Object-model rules

| # | Title | Why it matters |
|---|-------|----------------|
| [003](003-response-request-pattern.md) | Response/Request Pattern | The rule that lets Request travel straight to Service when fields match. |
| [004](004-dto-entity-responsibility.md) | DTO / Entity Responsibility | **No Entity, no Mapper** — single carrier type per domain. |

### 3. Cross-cutting concerns

| # | Title | Why it matters |
|---|-------|----------------|
| [009](009-async-external-clients.md) | Async External Client Standardization | Contract every AWS / HTTP / external client follows. |
| [017](017-exception-handling-strategy.md) | Exception Handling Strategy | Native handler over middleware; 4-typed handler topology. |
| [049](049-admin-identity-realm-separation.md) | Admin Identity Realm Separation | Admin vs. customer identity as separate bounded contexts + JWT realms; "share the auth mechanism, separate the trust boundary." |

### 4. Current AI & persistence abstractions

| # | Title | Why it matters |
|---|-------|----------------|
| [037](037-pydanticai-agent-integration.md) | PydanticAI Agent Integration | How LLM-powered services are wired today. |
| [039](039-pydantic-ai-embedder-transition.md) | PydanticAI Embedder Transition | Current embedding adapter (supersedes the per-provider Selector in 035). |
| [040](040-rag-as-reusable-pattern.md) | RAG as a Reusable `_core` Pattern | Why RAG lives in `_core/`, not in its own domain. |
| [041](041-vector-backends-consolidation.md) | Multi-backend Infrastructure Layout | Current `src/_core/infrastructure/` umbrella + subfolder convention. |
| [042](042-optional-infrastructure-di-pattern.md) | Optional Infrastructure (Selector + Lazy Factory) | How every non-DB infra (storage, DynamoDB, vectors, embedding, LLM) is made optional without breaking app boot. |
| [051](051-runtime-llm-guardrails.md) | Runtime LLM Guardrails | The runtime prompt-injection + output-integrity layer every LLM adapter wires; precise-block / fuzzy-log + `GUARDRAILS_ENABLED` kill-switch. |

### 5. Process & harness governance

| # | Title | Why it matters |
|---|-------|----------------|
| [045](045-hybrid-harness-target-architecture.md) | Hybrid Harness Target Architecture | The 7-step Default Coding Flow + escape-token vocabulary + Claude/Codex adapter strategy that route AI-assisted work into framing → plan → verify → review by default. |
| [046](046-otel-core-langfuse-recipe-prompt-domain-defer.md) | Observability Strategy (OTEL + Langfuse opt-in) | `[otel]` extra, `OTEL_ENABLED` bootstrap, Langfuse opt-in recipe, and deferred prompt domain — the observability layer a contributor needs to understand before adding instrumented services. |
| [047](047-governor-review-provenance-consolidation.md) | Governor Review Provenance Consolidation | Folds per-PR `governor-review-log/` into PR-description `## Governor Footer` blocks (CI-linted by `tools/check_governor_footer.py`). The canonical record for all governor-changing PR audit trails. |
| [048](048-independent-review-generalization.md) | Independent Review Generalization | Generalizes Pillar 2 to accept three modes (`cross-tool` / `self-structured` / `human`). Constrains `[skip-governor-footer]` bypass to non-governor-changing PRs. Read before customizing governance files. |
| [050](050-midtask-scope-expansion-gate.md) | Mid-Task Scope-Expansion Gate | A capability gap discovered mid-task is new plan-class work; stage-based advisory reminder + Direction & Non-goals in `project-dna`. |
| [052](052-native-execution-ledger-and-execute-plan.md) | Native Execution Ledger & Execute-Plan | The gitignored work-ledger state machine + `/execute-plan`; `/plan-feature` writes the plan, `/execute-plan` advances the Default-Flow stages. |
| [053](053-shared-review-protocol.md) | Shared Review Protocol | One shared contract (dimensions / finding-basis / output / verdict / posting) for the three review skills; `review-pr` as the PR entry point. |
| [054](054-plan-execute-boundary-hard-gate.md) | Plan→Execute Boundary Hard Gate | `/plan-feature` ends at the approved Execution Packet; implementing from the `planned` stage without `/execute-plan` or a waiver token is hard-blocked on Claude, advisory on Codex. |
| [055](055-summary-finding-ledger.md) | Summary Finding Ledger | Out-of-diff review findings post as a task-list ledger with complete carry-forward per round; any `OPEN` ledger key blocks Approve and the completion gate (closes the #292 merge-gate bypass). |
| [056](056-zero-downtime-migration-safety.md) | Zero-Downtime Migration Safety | No-downtime migration playbook (expand-contract + per-engine safe/unsafe DDL) + an advisory checker that scans Alembic revisions for unsafe DDL; advisory-first, plan-time data-model contracts explicitly out of scope. |
| [057](057-audit-actor-correlation-only.md) | Admin Audit Actor — Correlation-Only, No Foreign Key | `admin_audit_log.admin_user_id` drops its foreign key: the value is an `admin_identity.id` and migration 0009's id-preserving copy left the two id spaces overlapping, so a constraint against either table can be satisfied by the wrong row. Integrity moves to the read path; the swallowed audit-write failure that hid it becomes loud. |
| [058](058-base-repository-engine-guarantees.md) | What `BaseRepository` Guarantees Regardless of `DATABASE_ENGINE` | Five defects in the base class six domains and nine examples inherit. Bulk insert now refreshes like the singular path (it 500'd on any dialect without RETURNING, for rows already committed); offset pagination carries a deterministic order; search and sort fail closed with curated 4xx instead of returning the whole table or an opaque 500; the dead `related_entities` branch is gone. Verified by forcing the dialect flag rather than a MySQL CI leg — limitation stated. |
| [059](059-harness-context-byte-budgets.md) | Harness Context Byte Budgets | Blocking byte caps prevent automatic context from regrowing; sync dates record content changes. |
| [060](060-ticket-session-boundaries-and-review-packets.md) | Ticket Session Boundaries and Review Packets | Native ticket briefs, fresh serial execution, risk floors, precision-filter review and measured follow-up. |
| [061](061-retire-runtime-verify-and-content-heuristics.md) | Retire Runtime Verify and Content Heuristics | Removes redundant runtime checks while preserving active safety, outcomes and continuity. |
| [062](062-generated-harness-inventory.md) | Generated Harness Inventory | Tracked scope discovery, reviewed bucket judgments and generated-output gate. |
| [063](063-on-demand-harness-documentation.md) | Consult Detailed References on Demand | Consulted commands, scoped projections and compact policy references with historical snapshots. |
| [064](064-scoped-adr-evidence-in-agent-workflow.md) | Scoped ADR Evidence in Agent Workflow | Connect applicable decision clauses and status to choices, current evidence, conflicts and revisit routes. |
| [065](065-native-skill-discovery-and-procedure-authority.md) | Native Skill Discovery and Procedure Authority | Keep tool-native discovery and invocation metadata separate from shared procedure authority. |

## Archive

Decisions that have been superseded, reversed, or are purely operational
(tooling migrations, OSS prep, harness choices) live under
[`archive/`](archive/). They remain indexed and linked — nothing is deleted —
but they are not required reading for contributing to the codebase as it
stands today.

See [`archive/README.md`](archive/README.md) for the full archived list and
the rationale behind each archival bucket.

## Writing a new ADR

Numbering continues sequentially (next free number is 066). Only add a new
ADR when the decision is **load-bearing** — i.e. it constrains how future
code will be written, not merely which tool was picked. Purely
operational choices can be captured in `CHANGELOG.md` or a PR description.

### Principles

An ADR is **not** a document that justifies a decision already made.
It is a record of the **decision-making process** — the problem, the
options, and why one was chosen.

**Anti-patterns (rationalization):**
- Starting from the conclusion and gathering evidence to support it
- "We chose X. Here's why X is good..." (conclusion → evidence)
- Omitting alternatives that were seriously considered
- Writing rationale that only lists benefits without trade-offs

**Correct approach (decision record):**
- "We faced problem Y. We considered A, B, C. Given our context, we chose
  X because..." (problem → process → conclusion)
- Being honest about the decision type: was this designed upfront, or
  corrected after experience?
- Acknowledging trade-offs and what was sacrificed

Use the [scoped Decision Basis contract](../ai/shared/adr-evidence.md) when a task
makes or tests an architectural choice. Start from the affected concern and this
index; read only applicable clauses and their amendments/current carriers. A
scoped explanation that no ADR decision is affected is sufficient when true.
An Accepted status records a decision, not proof that code implements it or tests
pass. An archive supplies history unless a current rule explicitly carries its
constraint; do not promote historical rationale into current authority.

Retrospective records are valid when labelled honestly. Distinguish the decision
date from the recording date, cite contemporaneous evidence where available, and
identify later reconstruction or missing evidence. Do not invent past alternatives
or pretend the present author witnessed the original decision.

### Language

ADRs must be written in English.

### File naming

```
{number}-{topic}.md
e.g.: 042-your-decision-topic.md
```

### Document structure

```markdown
# {number}. {title}

- Status: Proposed / Accepted / Deprecated / Superseded by {number and clause scope}
- Date: YYYY-MM-DD (label whether decision or recording date)
- Record type: contemporaneous / retrospective
- Decision evidence: {approved issue, PR, discussion, or unavailable}
- Related issue: #{number}
- Amends / supersedes: {linked ADR clauses/current carriers, or none}

## Summary
<!-- 1-2 sentences: "To solve {problem}, we chose {approach}" -->

## Background
<!-- Trigger: what made this decision necessary NOW -->
<!-- Decision type: upfront design / experience-based correction / external factor -->
<!-- For retrospective records, separate sourced history from later analysis. -->

## Problem

## Alternatives Considered
### A. {alternative}
### B. {alternative}
<!-- Identify which alternatives were considered then; label later analysis. -->

## Decision

## Rationale
<!-- Lead with architectural "why", not implementation details -->

### Self-check
- [ ] Does this decision address the root cause, not just the symptom?
- [ ] Is this the right approach for the current project scale?
- [ ] Will a reader understand "why" 6 months from now without extra context?
- [ ] Am I recording the decision process, or justifying a conclusion?

## Consequences
<!-- Applicable scope, trade-offs, evidence/limits, and conditions for revisiting.
Link current code/tests separately; do not treat Accepted as implementation proof. -->
```

### Status values

- **Proposed** — A candidate decision; not an accepted constraint or permission to implement.
- **Accepted** — The recorded decision applies within its stated scope, subject to
  explicit amendments/supersession and the current rule carrier. Verify implementation separately.
- **Deprecated** — Retained history, no longer the current decision.
- **Superseded by XXX** — Replaced in the linked scope; identify whether replacement
  is complete or clause-specific instead of silently discarding unaffected decisions.

Clarifications, reviewed corrections, status links and explicit dated amendments
may be added to an Accepted ADR without rewriting its original rationale. A change
to an underlying architectural constraint needs an explicit new/revisiting decision
and links from the affected record/carriers, not silent editing to match today's
code. Follow [ADR 047 D3](047-governor-review-provenance-consolidation.md#d3--durable-inherited-constraints-move-to-adr-consequences):
existing `ADR047-G*` bodies are write-once; changed constraints get successor slots
and alias supersession links. The closed governor-review archive permits only
append-only English `Errata YYYY-MM-DD:` notes under its last section (ADR 047 D6);
this template does not authorize rewriting frozen entries.
