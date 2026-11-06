# 065. Native Skill Discovery and Procedure Authority

- Status: Accepted
- Date: 2026-11-06 (recording date; the batch was implemented and reviewed in PR #434, 2026-11-05 to 2026-11-06 UTC)
- Record type: retrospective — record of the owner-authorized, implemented batch, delivered through separate issue PRs
- Decision evidence: the superseded [PR #434](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/434) review
- Related issue: #414 (A5/A6/B6), #419, #420; #427 (investigation-skill boundaries)
- Amends / supersedes: refines [ADR 047](047-governor-review-provenance-consolidation.md) G4
- Related: [ADR 045](045-hybrid-harness-target-architecture.md),
  [ADR 060](060-ticket-session-boundaries-and-review-packets.md),
  [ADR 063](063-on-demand-harness-documentation.md)

## Context and Provenance

Skill names, routing blocks and procedure summaries were maintained in multiple
places even though tools already discover native skills. The owner-authorized batch
reduced those copies while keeping tool metadata and complete procedures. This
record makes the enduring contract explicit after implementation; it does not
claim a new runtime capability or a measured improvement in model quality.

[ADR 033](archive/033-hybrid-c-skill-split-convention.md) records the historical
choice of shared procedures plus thin tool wrappers. Its comparison of full
duplication, one tool-neutral native file and Hybrid C is historical evidence.
Its original skill counts and line-size estimates are not current limits.
Current authorities are the shared rules, procedures and metadata linked below;
archiving that antecedent does not make snapshots current policy.

The alternatives below explain the implemented choice. They combine the recorded
antecedent and the batch's observed duplication; they are not a claim that every
comparison was formally rehearsed before the original edits.

## Alternatives and Trade-offs

1. **Full procedure and routing copies in every tool:** self-contained invocation,
   but each procedure/guard change has several independently editable bodies and
   a fixed discovery list that can diverge from native metadata.
2. **Only a shared procedure, without native wrappers:** minimizes copies but
   loses tool-specific invocation metadata, user-only exceptions and legitimate
   tool post-steps. A wrapper that only names a procedure without requiring it to
   be read also cannot guarantee the full contract is in context.
3. **Native discovery plus thin, authoritative adapters, selected:** native indexes
   discover skills; compact wrappers retain metadata, an overview and explicit
   source loading. A single routing table and detailed shared procedure carry
   common policy. The cost is a bounded lookup and continued cross-tool parity
   verification, rather than independently usable duplicate procedure bodies.

## Decision

### Discovery and Invocation

Use native skill discovery rather than hand-maintaining a second complete skill
catalog in the root harness. Discovery is not permission for implicit invocation.
Claude's user-invoked-only `sync-guidelines`, `migrate-domain`, `trace` and `why`
remain explicitly discoverable through [CLAUDE.md](../../CLAUDE.md) and onboarding
because their native metadata excludes them from automatic discovery.

Codex's new `trace` / `why` policy files explicitly disable implicit invocation.
The existing Codex invocation policy for `sync-guidelines` / `migrate-domain` is
unchanged; do not manufacture symmetric metadata to make tools appear identical.
The [semantic metadata tests](../../tests/unit/agents_shared/test_native_workflow.py)
verify that distinction. Future invocation-policy changes require a deliberate
consumer/permission review, not just a prose-list refresh.

### Routing and Procedure Ownership

The [operating-model skill table](../ai/shared/target-operating-model.md#1-default-coding-flow-7-step)
is the current common home for step placement, approach-option conditions,
post-skill routes and recursion guards. Each shared skill and both native wrappers
retain a compact Default Flow Position pointer; compacting that block does not
waive phase, routing, exception, scope-expansion or plan/execute obligations.

The detailed procedure remains in `docs/ai/shared/skills/{name}.md`. A standard
wrapper must require reading and following that complete procedure before acting,
not merely say that further reading is optional. The original Claude/Codex wrapper
pairs keep the same procedure overview; native frontmatter, invocation flags,
argument handling and justified tool-only source/post-steps remain in their
respective wrappers. Tool-specific notes need not fit an arbitrary line count.

Scoped projections are consulted when the task needs them; they are not assumed
to have loaded in every session. Tool-neutral procedures use canonical shared
sources and live code, without requiring a private tool projection for unrelated
work. A tool wrapper supplies the relevant projection checks when auditing that
projection. [ADR 063](063-on-demand-harness-documentation.md) owns that reference
allocation and its archive boundary.

### Investigation Boundaries

Standalone `trace` / `why` remain on-demand, cited, read-only investigations.
Claude's fork/Explore metadata and Codex's explicit invocation policy preserve
their native isolation boundaries; do not claim the two runtimes use identical
mechanisms. The shared [trace](../ai/shared/skills/trace.md) reference also supports
inline use by fix-bug: that use does not require another fork or transfer fix-bug's
investigation, Cause Impact Matrix, recommendations, edits, verification or ledger
authority to a standalone read-only skill. ADR 060 owns the ticket/session and
measurement policy; this record does not add an execution orchestrator.

### Exact Relationship to ADR047-G4

ADR047-G4 continues to require coordinated updates and consistent information
across the shared procedure and both native wrappers. This refinement makes its
consistency test explicit: complete semantic coverage through mandatory source
loading, matched overview/routing and retained metadata, rather than identical
body length or a copied full procedure in all three files. The antecedent Hybrid C
already separated thin wrappers from detailed shared content.

This is not a waiver of three-surface synchronization. The historical G4 body
remains unchanged; the operative refinement is ADR065-G1 below. Any future change
that removes a required surface or relaxes a phase/guard needs its own explicit
superseding decision. Do not silently edit the old slot or treat an archived
line-count example as the replacement contract.

## Consequences

- **ADR065-G1 — Semantic parity through authority:** preserve the three skill
  surfaces and synchronize their contracts. Native wrappers must read/follow the
  complete shared procedure; compact pointers and matched overviews may replace
  copied bodies, never required phases, routes or guards. This refines G4 without
  changing its historical text or dropping a synchronization participant.
- **ADR065-G2 — Native invocation is part of the contract:** preserve user-only
  exceptions and actual tool-specific metadata/policy files. Native discovery,
  invocation permission and runtime isolation are different responsibilities.
- **ADR065-G3 — Scoped context and inline ownership:** consult relevant projections
  explicitly when needed; do not assume conditional context is present. A shared
  investigation reference used inline does not override the owning workflow or
  require an additional standalone invocation.

The reduction removes duplicate prose, not the obligation to load the detail.
A reader may need another file lookup; missing/unread authority is a failed
invocation contract. Exact savings are observations of the PR's tested tree,
not stable limits or evidence of fewer defects, lower quota use or faster review.
No new per-call runtime check or generated wrapper format is introduced.

## Verification and Reconsideration

Keep the [wrapper authority/outline tests](../../tests/unit/agents_shared/test_standard_skill_wrappers.py),
[native invocation tests](../../tests/unit/agents_shared/test_native_workflow.py),
[context-loading tests](../../tests/unit/agents_shared/test_skill_context_loading.py)
and [inventory check](../../tools/generate_harness_inventory.py) with the existing
language, link and budget gates. Exercise a representative skill against real
source/test evidence when its adapter behavior changes; parsing metadata or
matching an outline does not prove a model actually read the required procedure.

Revisit this split if a supported tool stops discovering the native format,
changes explicit-only/isolation semantics, cannot load the shared source, or
repeated source-backed failures show the overview omits a necessary invocation
contract. Measure the failure and adjust the smallest responsible adapter or
procedure together. Do not restore full duplication merely because a lookup is
inconvenient. Any coherent rollback preserves the native metadata and restores
routing/procedure consumers together; it must not turn mandatory reading into
optional advice or silently relax review, safety or session boundaries.
