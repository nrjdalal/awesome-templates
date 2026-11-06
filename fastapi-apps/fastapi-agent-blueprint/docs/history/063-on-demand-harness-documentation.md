# 063. Consult Detailed References on Demand

- Status: Accepted
- Date: 2026-11-06
- Issue: [#414](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/414) (A4, B1, B4, B5)
- Related issue: [#418](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/418) (notification reference ownership)
- Related: [ADR 045](045-hybrid-harness-target-architecture.md), [ADR 047](047-governor-review-provenance-consolidation.md), [ADR 051](051-runtime-llm-guardrails.md)

## Context

Fixed context grew through copied command examples, migration history and source-derived catalogs. Reducing lines alone did not constrain bytes. The shared policy remains useful, while a complete import table or old phase checklist is more accurately obtained from its owning source when needed.

Moving a rule file also changes a governance boundary: ADR 047 D4 exempted timestamp-only updates to the auto-loaded command projection. That exemption must not follow a consulted shared reference merely because its basename is unchanged.

## Decision

1. Move the shell command reference to [shared commands](../ai/shared/commands.md). All tools consult it as needed. Path-scoped architecture and project overview rules remain Claude projections; shared policy stays in AGENTS and project-dna.
2. Remove both the obsolete `.claude/rules/commands.md` path and its relocated shared destination from the sync-cosmetic carve-out. Only the remaining project-status / project-overview cosmetic cases qualify. This narrows ADR 047 D4; no historical ADR047-G slot is rewritten.
3. Archive historical migration / repository-facts prose and TOM Appendices A/C. Keep live navigation stubs and update current consumers to their actual authority. Appendix B's sample workflows remain live; the fix-bug skill relies on Trace 2.
4. Keep project-dna as a policy and source-navigation reference, at most 48 KiB. Replace derivable blocks with links to their source; retain original section numbers/headings, the non-derivable §5 provider-lifetime policy, and §14 guardrail policy. Preserve removed examples once as a historical snapshot with relative links repaired.
5. Current sources take precedence over historical snapshots. Snapshots preserve evidence, not new policy, and are not required reading on every sync. Routine provenance belongs in git, CHANGELOG and the PR body.

## Consequences

- **ADR063-G1 — Source ownership:** consulted commands live in shared documentation; path-scoped projections do not become new canonical homes. A relocation never silently extends the cosmetic exemption.
- **ADR063-G2 — Stable policy anchors:** project-dna § numbers and headings, §5 provider policy and §14 guardrail invariants survive block-level compression. New source-derived catalogs should be pointers; real markdown anchors replace new free-text section references where practical.
- **ADR063-G3 — Archive boundaries:** historical migration notes and implementation examples do not govern current adapters. Appendix B remains a live contract. Archives retain per-source provenance, repaired links and original text; no routine archive writer is introduced.

- **ADR063-G4 — Notification authority allocation:** shared toggle/dispatch policy,
  operator guidance and developer wiring invariants keep the distinct homes
  defined in the supplementary allocation below. Tool projections remain pointers; retirement or movement of an invariant
  requires source/test verification and an explicit replacement home.

The first migration also fixes confirmed drift: aggregate read contracts omitted `count_datas_by_day`; the LLM DI narrative instructed domain Services to construct SDK Agents despite ADR 043; the audit-log description still claimed an actor foreign key removed by ADR 057. Storage Selection's claim that no Selector exists was also stale against CoreContainer. These are documentation corrections, not runtime changes.

## Verification

- Meaningful regression tests cover the removed cosmetic exemption, scoped loading, retained policy/guardrail blocks and live sample workflows.
- Archive preservation is checked against the source snapshot, allowing only repaired relative links and explicit archival provenance.
- Documentation links, Tier 1 language policy, project-dna byte size and existing native-workflow / worktree-hook contracts remain verification gates.

Scope regression cases exercise every declared simple glob with positive and negative samples using Python fnmatch. They are smoke tests, not a measurement of Claude Code's native matcher; native matcher behaviour remains an explicitly unverified limit.

## Supplementary Decision Record — Reference and Notification Ownership

This supplement records the implemented accepted batch retrospectively. The
[#414](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/414) audit and
[#418](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/418) describe
the source duplication and constraints. The comparisons below make the resulting
choice reviewable; they do not assert an undocumented formal alternatives process.

### Alternatives, rationale and costs

Keeping every catalog and feature paraphrase in auto-loaded rules gives a reader
one local surface, but repeats changing facts and turns synchronization into an
independent interpretation at each copy. Deleting those references outright
saves context while losing non-derivable policy, source discovery and provenance.
The selected middle ground keeps shared policy and stable navigation, consults
source-owned detail, and preserves superseded narrative once. Its cost is an
extra lookup and the need to verify what a source says, not merely that its link
resolves. Link and byte gates do not establish semantic equivalence.

For Error Notification specifically, putting all developer and operator material
in the operations runbook would replace several copies with a mixed-purpose
home. Keeping the old rules bodies would keep the original drift surface. The
selected allocation follows the consumers' responsibilities:

| Authority | Owns | Projection rule |
|---|---|---|
| [AGENTS Optional Infrastructure Toggles](../../AGENTS.md#optional-infrastructure-toggles) | Shared enable/disable, fallback and dispatch contract | Tool rules point to the contract rather than inventing another behavioral summary |
| [Error Notification runbook](../operations/error-notifications.md) | Setup, credentials, operational verification, troubleshooting and coverage implications | Explains operation against the shared contract; does not become a second home for developer wiring invariants |
| [project-dna §8](../ai/shared/project-dna.md#8-active-features) | The single prose home for registration-order, severity-band agreement and shared-disabled-client invariants | Preserve these developer constraints here; this ADR allocates ownership instead of restating their bodies |
| Live infrastructure and its tests | Executable wiring, routing, cooldown and disabled-client behavior | Changes must update the owning contract and evidence together |

This is a documentation ownership change, not a notification behavior change.
Runtime-owned identifiers and defaults still need code spot-checks. Archived
paraphrases remain historical evidence even when they describe an old or incorrect
state; moving an archive link does not itself warrant a new ADR.

### Validation and reconsideration

Verify the notification authority links and the owning DNA invariants together
with the existing [middleware-order](../../tests/unit/_apps/worker/test_task_bootstrap_order.py),
[cooldown](../../tests/unit/_core/infrastructure/notification/test_error_notifier.py),
[routing](../../tests/unit/_core/infrastructure/notification/test_notification_router.py)
and [shared-disabled-client](../../tests/integration/_core/infrastructure/test_optional_infra.py)
regressions. Keep the sync anti-refill rule so later updates do not reconstruct
feature bodies in tool projections. The source links do not replace checking the
contract against those tests and implementation.

Revisit allocation when a new consumer needs a different public contract, or a
source-backed defect shows that the current ownership/lookup boundary hides a
required invariant. Adjust the responsible home and its references together;
do not restore independent paraphrases merely to avoid following a pointer.
Re-test rule scopes when the native loader or matching behavior changes. Actual
missed context may justify a targeted scope change; the fnmatch smoke tests above
are not evidence that a native matcher behaved identically.
