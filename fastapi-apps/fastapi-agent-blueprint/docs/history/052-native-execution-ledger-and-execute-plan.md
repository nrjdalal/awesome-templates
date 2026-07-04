# 052. Native Execution Ledger and Execute-Plan

- Status: Accepted
- Date: 2026-07-04
- Related issue: #185 (Phase 1 — work-ledger v1, PR #185), #257 (Phase 2 — execute-plan + ledger v2, PR #258)
- Builds on: ADR [045](045-hybrid-harness-target-architecture.md) (7-step Default Coding Flow — this adds the stateful execution layer under it)
- Consumed by: ADR [050](050-midtask-scope-expansion-gate.md) (the mid-task gate reads `workflow.stage`). See "Honest provenance note" below.
- Note: retroactive record. The mechanism shipped via PR #185 (merged 2026-05-09) and PR #258 (merged 2026-07-02, closing issue #257); this ADR backfills the *why*.

## Summary

To give multi-turn, multi-session, two-harness (Claude + Codex) work a place to remember what it is doing across a session boundary, we introduce a single **gitignored JSON state ledger** (`.agents/state/current-work.json`, owned by `.agents/shared/work_ledger.py`) plus a native **`/execute-plan`** skill that consumes it. `/plan-feature` **writes** the plan into the ledger; `/execute-plan` **advances** its `workflow.stage` through the Default-Flow lifecycle. The ledger is schema-versioned (v1→v2 migrate-on-read) and the whole mechanism is **advisory-first and fail-open**.

## Background

### Trigger — two issues, one decision record

1. **#185 (PR #185, merged 2026-05-09):** a Codex CLI harness audit (gpt-5.5, xhigh, 2 rounds) flagged R1/Q2 — *"no cross-session context continuity"*: when a session ended, the next re-derived goal/scope/plan/verification from scratch, a scope-drift/hallucination risk the audit was hunting. This first added `work_ledger.py` at **schema v1**.
2. **#257 (implemented by PR #258, merged 2026-07-02):** a follow-up "Strengthen native harness execution workflow" wanted agents to execute approved multi-task plans task-by-task *inside the existing architecture*, using the upstream "superpowers" project only as a design lens. This added `/execute-plan` + the Execution Packet contract and upgraded the ledger to **schema v2** (the `workflow` block).

### Honest provenance note

This ADR is written **retroactively**, and ADR 050 (2026-07-03) *already depends* on the v2 ledger's `workflow.stage` vocabulary for its mid-task gate. So 052 does not predate its consumers — it backfills provenance for a mechanism later ADRs already build on. It is scoped to the **ledger + execute-plan only**; #185 also carried an unrelated "Effect Answer" review-contract R-point, which belongs to the review-protocol / H-guard lineage (ADR 053), not here.

### Decision type

Two phases. Phase 1 (#185) is an **experience-based correction** of an observed failure surfaced by an adversarial cross-tool audit. Phase 2 (#257/#258) is **upfront design** of a stateful execution layer on top of the now-existing ledger (the "Planned direction" bullets and the schema-v2 backward-compat acceptance criterion were written before implementation). Not an external factor — no dependency change forced it; superpowers was deliberately kept as a reference, not adopted.

## Problem

Multi-turn, multi-session AI-assisted work needs somewhere to remember what it is doing across a session boundary and across two harnesses. Two distinct gaps:

- **P1 (#185):** `SessionStart` re-derived goal/scope/plan/verification each session — context lost, inviting scope drift and re-invention (the exact failure the audit named).
- **P2 (#257):** ADR 045's 7-step Default Coding Flow ends at self-review + completion gate but has **no stateful layer** tracking a multi-task plan through implement→verify→review. Complex/governor-changing/multi-task work had no machine-readable notion of *which task is active, whether it was verified, whether it was reviewed and by whom*. And without persisted stage/task state, advisory hooks (`Stop`, `PostToolUse`) had **nothing to observe** — so neither ADR 050's mid-task gate nor the verify-first advisory could function.

## Alternatives Considered

### A. No persisted state — re-derive each session from the transcript

The status quo before #185. **Rejected:** this *is* the failure mode the #185 audit named (R1/Q2). Re-derivation loses scope and invites drift/hallucination; rejecting the disease is not a fix (cf. ADR 045's rejection of soft-only enforcement).

### B. External orchestration — import the upstream "superpowers" package as the workflow engine

Adopt an external process-governor dependency to own plan execution and state. **Rejected:** `target-operating-model.md` §4 explicitly forbids it — the repo carries no such dependency and "routine project operation remains local" ("Mostly Local with Philosophy Overlay", ~80% Keep). Consistent with ADR 045's rejection of full superpowers adoption (collides with ADR 040/042/043 boundaries). #257 direction: *"Keep superpowers as a design reference only; absorb operating rules into native harness assets."*

### C. Unversioned ledger (no `schema_version` / no migration)

Add the v2 fields by simply appending keys and trusting readers to tolerate missing ones. **Rejected:** #185 shipped v1 into real per-machine ledgers *before* #257 existed. #257's acceptance criteria require the ledger stay backward-compatible with v1 while supporting v2 fields. Without a version tag + migrate-on-read, a v1 document read by v2 code surfaces a partial/typeless `workflow` block; `_migrate_ledger` upgrades it safely on first read/write (PR #258 tests cover v1→v2 migration precisely because this was a required guarantee).

### D. Hard-gate enforcement from day one

Make `Stop`/`PostToolUse` hooks **block** when `workflow.stage` is inactive or verification is pending, rather than warn. **Rejected:** #257 planned "advisory-only hook output first, then later promote proven high-confidence conditions to hard gates." Candidate hard conditions "must have tests and must avoid broad false positives for exploration, trivial edits, and single-skill work." Mirrors ADR 045 D2's rejection of hard-only enforcement — false-positive cost normalizes bypass and disables the governor. Fail-open is a stated design constraint of the module.

## Decision

Introduce a single JSON state ledger at `.agents/state/current-work.json` (gitignored, machine-written), owned by `.agents/shared/work_ledger.py`, plus a native `/execute-plan` skill that consumes it.

- **D1 — One shared store:** the ledger holds `meta`, `last_prompt`, `goal`, `scope`, `plan`, `blockers`, `verification` (`status` / `last_verified_at` / `last_command` / `changed_py_files`), and (v2) a `workflow` block `{stage, plan_ref, current_task, tasks[], review{mode,status,reason}}`. One neutral path under `.agents/` so **both** harnesses read/write it.
- **D2 — Fixed stage vocabulary:** `idle | planned | executing | reviewing | complete | blocked` — the lifecycle a plan traverses, so a hook or a resuming session reads one enum and knows exactly where work stands.
- **D3 — Write/consume split:** `/plan-feature` **writes** the ledger at plan-approval time (`update_goal_scope_plan` + `update_workflow_state(stage="planned", plan_ref, tasks)`); `/execute-plan` **consumes** the approved Execution Packet, driving `stage="executing"`, per-task transitions, then `stage="complete"` only after Verification Gates and Review Gates pass. Hooks stay passive I/O (`SessionStart` summarizes, `UserPromptSubmit` snapshots `last_prompt`, `Stop` refreshes `changed_py_files` + builds advisory segments).
- **D4 — Versioned + fail-open:** `SCHEMA_VERSION = 2` with `_migrate_ledger` upgrading v1 documents; every public function suppresses I/O errors and returns `None`/empty, and `Stop` advisories only warn — never block.

## Rationale

A **local JSON file at a fixed path** is the minimum mechanism satisfying the two constraints that shaped every choice: cross-**session** persistence (must survive process exit → a file, not memory) and cross-**tool** sharing (Claude and Codex both use one path → a neutral `.agents/` location, not a tool-specific store). Gitignored because it is per-machine working state, not a committed artefact.

The stage vocabulary is deliberately the **lifecycle a plan traverses** (planned by `/plan-feature`; `executing`→`complete` by `/execute-plan`, which records review progress in the `review` substate rather than a distinct `reviewing` stage; `blocked` on failure). The **write/consume split follows ADR 045's own step ownership**: `/plan-feature` owns framing/approach/plan (so it seeds the packet + ledger), `/execute-plan` owns implement/verify/self-review/completion-gate (so it advances state) — the Execution Packet is the typed boundary object between them.

Versioning is load-bearing because #185 shipped v1 into real ledgers before #257 existed, so **migrate-on-read guarantees an old ledger never crashes a new session** (unreadable → `None` → callers fall back to defaults). The whole thing **extends ADR 045's 7-step flow into a stateful execution layer**: the seven steps stay the process contract; the ledger + execute-plan make the implement→verify→review portion *observable and resumable* rather than living only in the conversation transcript.

## Consequences

### Durable constraints

**ADR052-G1 (durable-governance)** — The ledger schema is **versioned**; any change to the `workflow` block or field layout bumps `SCHEMA_VERSION` and extends `_migrate_ledger` so an older on-disk document upgrades on read. Readers must tolerate a `None` return (migration/parse failure) and fall back to defaults — never assume the ledger exists or is current.

**ADR052-G2 (durable-governance)** — The **write/consume split is contractual**: `/plan-feature` is the only skill that seeds `goal/scope/plan` + `stage="planned"`; `/execute-plan` is the only skill that advances the stage from `executing` to `complete`, recording review outcome in the `review` substate (`review_status`) — not a distinct `reviewing` stage. (`reviewing` is a reserved vocabulary value the current shipped procedure does not write.) Hooks are passive readers/refreshers, never authorities on stage. A new skill that needs execution state uses `update_workflow_state`, it does not invent a parallel store.

**ADR052-G3 (durable-governance)** — Ledger-driven hook behavior is **advisory-first and fail-open**. Promoting any condition to a hard gate requires tests and a demonstrated absence of false positives against exploration / trivial / single-skill work (the ADR 045 D2 bar), and its own decision record.

### Enforcement gaps (explicit disclosure)

- **Mutable state outside git:** no audit trail of ledger transitions, and a stale/corrupt ledger is possible; mitigated only by fail-open + migrate-on-read.
- **Advisory, not enforced:** a `Stop` reminder can be ignored — hard gates were deliberately deferred.
- **Partial auto-capture:** only `last_prompt` / `changed_py_files` / verify-status are auto-collected; `goal/scope/plan/workflow` require explicit skill invocation. A contributor who never runs `/plan-feature` gets prompt+verify continuity but no plan/task state.
- **No `exit_code` capture:** `verification.status` `passed/failed` is set by `mark_verified` callers, not observed automatically — the `PostToolUse` payload carries no exit code (deferred R2 in #185); the auto path only promotes `unknown→pending` on changed `.py` files.
- **Two-harness parity:** Claude and Codex must keep hook adapters in sync (Codex lacks `PostToolUse Edit|Write`), a standing maintenance surface.

### Where the rules already live (point here, do not re-document)

- ADR 045 — the 7-step flow, precedence layers, exception tokens, and the hard-vs-advisory (D2) philosophy this extends.
- ADR 050 — the mid-task gate that *consumes* `workflow.stage` (cite it; do not re-document the gate here).
- `docs/ai/shared/target-operating-model.md` §4 — the native-execution-workflow narrative + Execution Packet as the planning/implementation boundary + advisory-first statement + "Mostly Local" model identity.
- `docs/ai/shared/skills/plan-feature.md` + `execute-plan.md` — the Execution Packet required-field contract.
- The `## Governor Footer` blocks on PR #185 and PR #258 — the per-PR R-point audit trail (ADR 047 contract).

### Self-check

- [x] Addresses the root cause (no cross-session/cross-tool state) rather than the symptom (re-derivation).
- [x] Right-sized: a single gitignored JSON file + advisory hooks, not an orchestration engine.
- [x] A reader in 6 months learns why it is local+native (not superpowers), why versioned, why advisory-first.
- [x] Honest about being retroactive (050 already consumes it) and about the enforcement gaps.
