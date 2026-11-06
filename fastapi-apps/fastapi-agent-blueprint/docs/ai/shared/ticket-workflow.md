# Ticket Workflow

This is an on-demand operating contract for issue #427, adopted by
[ADR 060](../../history/060-ticket-session-boundaries-and-review-packets.md).
It makes no measured claim of lower review time, hallucination, or quota use.

## Work units and handoff

- **Epic**: a parent issue whose tickets share one approved Execution Packet.
- **Ticket**: one independently reviewable outcome, one PR, one worktree, one fresh
  execution session. Keep tightly coupled changes together; do not split merely
  to reduce line count. A resumed session for the same ticket is allowed.
- **Task**: a dependency-ordered step inside a ticket, not another tracking system.

Planning ends with the approved packet and native ticket sub-issues. Each ticket
brief is a projection of that packet, not a second implementation plan. Use the
[native issue template](../../../.github/ISSUE_TEMPLATE/ticket.yml).
A standalone ticket may carry its packet in its own body. The brief records:

1. Intent, explicit non-goals, observable done-when criteria.
2. Premises with code, test, issue, ADR, or runtime evidence pointers. For an
   affected architectural choice, project the [scoped Decision Basis](adr-evidence.md)
   from the packet: why the current clause applies, the constraint on this ticket,
   and code/test evidence or an explicit unknown. An ADR ID alone is not evidence
   that the premise holds; keep implementation options in the parent packet.
3. Parent packet/reference and approval evidence, predecessors, file set,
   Parallel Group, and Supervision L1/L2/L3 from
   [planning-checklists](planning-checklists.md#4-supervision-level-definitions).
4. Exact verification gates and review gates, including known unverified limits.

The human approves the brief and reviews the final diff at its risk depth.
Existing explicit approval remains valid; do not manufacture repeated approvals.
If GitHub write access is unavailable, emit the complete ticket bodies and report
that native publication remains pending; never pretend draft bodies are sub-issues.

Start `/execute-plan <ticket issue>` in a fresh session. Read the issue, its parent
packet, approval evidence, predecessors, and current PR/CI state. Try to falsify
its premises before editing, using the existence gate in
[fix-bug Phase 1](skills/fix-bug.md#phase-1-reproduce): distinguish observed,
inferred, and second-hand claims; a disproved premise needs a corrected contract,
not a speculative implementation. Check only relevant references, avoiding broad
repository rediscovery. Recheck only the applicable clause's status/amendments and
current carrier against the ticket's code evidence; an Accepted ADR alone cannot
confirm a runtime claim. Report unresolved decision/code conflicts through the
scoped contract rather than silently overriding current rules. Newly missing
capability follows ADR 050.

Run sequentially by default. Parallel tickets require disjoint declared file sets,
no unresolved dependency, and available human review capacity. Discovery of overlap
returns the tickets to serial execution. No external orchestrator is introduced.

Issue scope and approval, PR diffs/reviews, and CI results are durable evidence.
Reconcile disagreements against the actual code and acceptance criteria; issue
closure or green CI alone does not prove success. The gitignored work ledger is
only local resumable state. Hydrate its existing fields from the approved ticket
before entering `executing`; keep ADR 054's explicit execute-plan boundary and
existing hooks. Do not make the ledger, or a stale SessionStart summary, the source
of approval or completion. No ledger schema change is needed.

## Review packet and depth

Run `uv run python tools/review_packet.py --base origin/main` on the final tracked diff
(stage new files first). It compares the merge-base of the base and HEAD with the
tracked working tree, including staged edits; unrelated base-tip commits are excluded.
The command reports changed files ranked by risk and
added/deleted counts; binary changes are high risk. It does not run verification.
The PR's first screen contains intent, derived risk + reasons, highest-risk files,
commands with concise observed output/exit status, and unverified limits. For an
affected design choice, connect intent/change summary to its governing clause and
current evidence through the packet's scoped Decision Basis; do not add a ceremonial
ADR-read checkbox. Put
supporting details below the collapsed section; keep the real Governor Footer
outside it. Never copy a template example as a test result.

Risk is a floor, independent of governor Tier A/B/C:

| Risk | Deterministic floor | Human review depth |
|---|---|---|
| High | Governor trigger, CI, migration, auth/security/credential path, binary diff | Read affected contracts and failure paths as well as the full diff |
| Medium | Runtime/build/dependency change, unknown file type, or total added+deleted >400 | Read the complete diff and verification evidence |
| Low | Only general documentation/assets/tests, at most 400 added+deleted | Inspect intent, focused diff, and relevant evidence |

A reviewer may raise risk with reasons. File names cannot prove the absence of
security or contract effects: discovered semantic risk raises the tier. Size never
lowers path risk, generated files are counted, and renamed/deleted paths are
examined on both sides. Existing mandatory security/architecture and governor
review obligations still apply.

Use one independent cross-vendor precision-filter round for implementation tickets
as specified in [review-protocol](review-protocol.md#7-independent-review--fallback).
Close known findings using verified evidence; do not start open-ended review loops.
Explicit full security/architecture audits retain their full severity coverage.
Fold guideline sync into the feature PR, before final review. Standalone sync PRs
are reserved for a release audit or independently discovered post-merge drift.
The merged-PR Footer audit in drift-checklist §1D runs at release; a feature PR
checks its own Footer and changed rules. This changes packaging, not sync quality.

## Measurement protocol

Use [ticket-metrics.csv](ticket-metrics.csv) as an empty collection schema. Unknown
values stay empty, never zero. One row per ticket; keep evidence URLs and sample
size. Record review rounds (including pre-PR rounds), distinct human corrections,
and post-merge fix-up PRs linked to the ticket within 14 calendar days. Zero
fix-ups is final only after that window, or record `observation_end` as censored.
A human correction is a distinct factual, scope, or behavior correction requiring
a change, not each message, clarification, preference, or repeated finding.

Human review active minutes require owner-provided start/stop intervals; exclude
breaks and machine waiting. Open-to-merge and CI durations are wait/lead-time
proxies only. Quota snapshots are optional manually recorded Claude `/usage` and
Codex usage-dashboard observations, with timestamp, plan/window, and overlapping
work noted. Session count or API prices do not measure subscription quota.

Compare a prospective sequential-ticket pilot with comparable historical tickets
by risk and size, disclosing non-random assignment and missing measurements.
Report medians, sample sizes, correction/fix-up counts, and censored windows;
small observational samples cannot establish causation. Decide whether to change
execution topology only after the owner reviews that evidence.

A transcript-derived owner-review/wait proxy is an investigation, not a result:
use an explicitly authorized, redacted sample; compare inferred intervals with
owner timings, record uncertainty, and discard the proxy if agreement is poor.
Do not collect transcripts automatically or treat silence as active review.

## Lightweighting implementation status (#414)

The integrated change set implements the supported Tier A and Tier B work below.
Implementation completion does not establish measured effectiveness or finish the
prospective observation window of parent #427.

| Candidate | Implemented result | Evidence / rollback boundary |
|---|---|---|
| B1 scoped rules | Commands are consulted shared references; scoped rule projections retain unconditional layer-selection policy and correct Storage facts | Context budgets, rule-scope and reference tests; restore paths/config together |
| B2 verify runtime | Removed verify-first/log consumers across all three adapters; actual outcomes, safety, locale and marker lifecycle remain (ADR 061) | Launcher, doctor, lifecycle and retirement regressions; restore writer/consumer contracts together |
| B3 inventory | Reviewed bucket map, tracked-scope generator and generated-output gate (ADR 062) | Indexed completeness and generation tests; restore map/generator/CSV together |
| B4 historical docs | Archived migration/repository facts and TOM A/C; retained navigators and live Appendix B traces | Archive-body and inbound-reference checks; restore moves and links together |
| B5 project-dna | Reduced by block below the stated budget; §5 policies, §14 guardrails and all numbered headings remain | Heading/source-policy/byte checks; restore relevant blocks if undiscoverable |
| B6 skill wrappers | Standardized the original 30 wrapper bodies; retained frontmatter, plan terms and legitimate tool notes. New trace/why wrappers remain compact with their isolation constraints | Native parity, invocation-flag, outline and source-authority regressions; restore wrappers and shared contracts together |
| B7 sync packaging | Sync is part of the feature PR; release/post-merge audits remain standalone | Review/sync contracts and release Footer trigger; restore packaging rules together |
| B8 security categories | Retired duplicate runtime content heuristics and added the production sensitive-logging commit gate; code_safety compatibility remains (ADR 061) | Real hook positive/negative/skip probes; removed pre-edit rejection is a disclosed guarantee change, not equivalent SQL coverage |
| B9 summaries | Completed clean cache is suppressed; unresolved review/blockers and idle prompt/verification continuity remain | Complete/idle/outcome/worktree regressions; restore the summary predicate and framing together |

The remaining observation and owner-timing work is tracked only in
[measurement follow-up #433](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/433).
It has no invented measurements: collect the prospective data and owner review
before claiming #427's effectiveness goals or selecting a new execution topology.
Parent #427 therefore retains a measurement remainder despite implemented workflow
contracts. Antigravity/Gemini removal remains a separate owner product decision;
this work preserves the adapters. The three refuted removals in #414 remain
rejected: doctor coverage, safe launcher behavior and review-protocol ownership
are retained. No observation-dependent success claim is used to close a gate.
