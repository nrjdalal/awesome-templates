# 050. Mid-Task Scope-Expansion Gate — Stage-Based Advisory Reminder + Direction in Project DNA

- Status: Accepted
- Date: 2026-07-03
- Related issue: [#268](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/268)
- Extends: ADR [045](045-hybrid-harness-target-architecture.md) — adds a mid-task re-entry rule to the Default Coding Flow. The seven steps, precedence layers, and exception-token vocabulary are unchanged.
- Constraints: ADR [047](047-governor-review-provenance-consolidation.md) footer contract and ADR [048](048-independent-review-generalization.md) review modes remain in force. Phase-5 governor architecture (fail-open shims over `.agents/shared/governor`) is reused, not modified.

## Summary

The Default Coding Flow (ADR 045) mandates `framing → plan` before `implement`, but every rule and every enforcement surface is **prompt-scoped**: exception tokens are recognised on prompt line 1, auto-escapes are evaluated per prompt, and `UserPromptSubmit` is the only routing hook. When an agent running in auto-accept mode discovers a missing capability **mid-task**, the discovery never re-enters the flow — the agent classifies it as a continuation of the current task and implements immediately, skipping `/plan-feature`.

This ADR closes the gap with three coordinated changes:

1. **Canonical rule** — a "Mid-Task Scope Expansion" subsection in `target-operating-model.md` §2 (synced to AGENTS.md § Default Coding Flow): a capability gap discovered during execution is *new implementation-class work*; the agent stops, reports the gap, and routes to `/plan-feature` / `$plan-feature`.
2. **Advisory stage-gate hook** — a `PostToolUse Edit|Write` reminder (mirroring the verify-first Phase-3 contract, HC-3.3) that fires when a `.py` file under `src/` or `examples/` is edited while the work ledger's `workflow.stage` is inactive, no plan-waiver token marker (`[trivial]`/`[hotfix]`, see D6) is present — `[exploration]` does not suppress the gate — and the reminder has not already fired this session.
3. **Direction & Non-goals** — a subsection in `project-dna.md` §0 giving planning and review steps a repo-level direction reference, so "is this aligned?" has a citable answer instead of living in issues and maintainer memory.

## Background

Observed failure mode (maintainer report, 2026-07-03): during auto-mode execution the agent notices "feature X does not exist", says so, and immediately begins implementing X. The Default Coding Flow does not fire because no new prompt was submitted; no hook fires because nothing observes the relationship between an implementation edit and the ledger's workflow state.

The building blocks already exist:

- `.agents/state/current-work.json` records `workflow.stage` (`idle|planned|executing|reviewing|complete|blocked`), written by `/plan-feature` and `/execute-plan`.
- The Phase-5 governor package (`.agents/shared/governor`) provides marker lifecycle (IC-11/IC-12), token vocabulary, fail-open shim conventions (HC-5.5, Plan §D3), and a proven advisory channel (verify-first).
- `/execute-plan`'s enforcement policy is explicitly **advisory-first**: reminders do not block; only high-confidence conditions with false-positive tests may later be promoted to hard gates.

## Decision

### D1 — Non-blocking advisory, not a hard gate

The gate emits a reminder and never blocks the tool call (wrapper always exits 0, HC-3.3). Rejected alternatives: a blocking `PreToolUse` permission decision (destroys auto-mode value and punishes false positives with approval fatigue); a doc-only rule (the failure mode *is* passive rules losing to task momentum — a rule with no runtime nudge changes nothing).

### D2 — Stage-based detection with an explicit gated-stage allowlist

The gate fires only when `workflow.stage` is one of `GATED_STAGES = {idle, complete, blocked}`. Active stages (`planned`, `executing`, `reviewing`) are silent. Missing ledger, unreadable JSON, or an **unknown stage string** are silent (fail-open): the gate fires only on positive evidence of "no active plan". Scope-glob matching (per-file plan-scope check requiring a ledger schema change) was considered and deferred — stage granularity is cheap, schema-stable, and sufficient for the observed failure mode.

### D3 — `PostToolUse` with `additionalContext`, not `PreToolUse`

The approved plan initially named `PreToolUse`. Implementation refines this to `PostToolUse` with identical semantics: per the hooks reference, `PreToolUse` has no non-blocking model-visible channel (exit 2 blocks; a permission-decision reason targets the user). The edit itself is not worth blocking — the goal is to interrupt the *next* decision, not the current write.

Delivery channel: exit 0 + stdout JSON `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": <reminder>}}`. This is the documented model-visible non-blocking channel; plain stderr/stdout text on exit 0 reaches only the user-facing transcript, **not** the model (verified empirically during this change and against the hooks reference). Drift candidate recorded: the Phase-3 verify-first shim still emits stderr-on-exit-0 and is therefore likely invisible to the model — remediation tracked separately (same channel fix, own issue).

### D4 — Implementation surface = `.py` under `src/` or `examples/`

Only Python files under `src/` and `examples/` gate. Tests, docs, tooling, and harness paths are excluded: editing those without an active plan is lower-risk, and harness/doc drift is already covered by the Stop-hook sync advisory and the governor completion gate.

### D5 — Once per session

Dedup marker `stage-gate-<session_id>.json` (in `.claude/state/`, 24h defensive window per IC-11 convention, self-pruning on write). The claim is an **exclusive create** (cross-review R1.3): when concurrent hook invocations race, only the writer that wins the marker emits the advisory — the shim prints nothing unless `mark_fired` returns the claimed path. One nudge per session is the advisory-first noise budget: the rule does the persuading; the hook only breaks the momentum once. Per-prompt refire was rejected for v1 — it requires coupling marker cleanup into `UserPromptSubmit` and risks nagging.

### D6 — Suppression conditions

Only **plan-waiver tokens** suppress the gate (cross-review R1.1 narrowed this from "any matched token"): `[trivial]` waives framing/approach/plan outright, and `[hotfix]` is an explicit urgency escape where a mid-fix nudge would fight the token's purpose (each including its Korean equivalent; `PLAN_WAIVER_TOKENS` in `governor/tokens.py`, read via `MarkerLifecycle.READ_ONLY` with the 24h filter). `[exploration]` (and its Korean equivalent) deliberately does **not** suppress: it declares a read-only session, so an implementation edit under it is itself a signal worth surfacing. Because `.agents/state/` is untracked, contributors and CI have no ledger and never see the reminder; this is a maintainer-workflow feature by construction.

### D7 — Codex parity: documented deferral

Codex has no `PostToolUse`. The parity adapter (Stop-time advisory evaluating changed implementation files against the ledger stage) is specified in `migration-strategy.md` and deferred to a follow-up issue rather than widening this PR. Codex retains the canonical rule (prompt-time routing) meanwhile.

### D8 — Direction & Non-goals lives in `project-dna.md` §0

No new Tier-A document and no public `ROADMAP.md` for now: the governance surface is already large, and §0 ("Project Scale and Design Philosophy") is the existing home for exactly this kind of judgment reference. `plan-feature` Phase 1's repo-specific-fit axis links to it. A public roadmap remains a future option once direction content stabilises.

### Fail-open invariants (inherited, restated)

The hook performs no network access, writes only under `HARNESS_STATE_ROOT/.claude/state`, contains no top-level `sys.exit`/`SystemExit` (Plan §D3), and returns 0 silently on shared-import failure (HC-5.5).

## Consequences

- Mid-task capability discovery now has both a canonical rule and a runtime nudge; auto-mode sessions keep their speed (nothing blocks) while losing the silent-scope-creep default.
- The work ledger becomes load-bearing for a new consumer: skills that forget to update `workflow.stage` will cause false reminders. `/plan-feature` and `/execute-plan` already write the stage; no new obligation is added.
- One more `PostToolUse` command runs per Edit/Write (single JSON read + one stat'd directory; negligible).

### Durable Governance Constraints

- **ADR050-G1** — The stage gate stays advisory. Promotion to a hard gate requires a dedicated hardening PR with false-positive tests covering exploration, trivial edits, and single-skill work (per `/execute-plan` § Advisory-First Enforcement).
- **ADR050-G2** — Gating is allowlist-based: the gate fires only on `GATED_STAGES` membership. New ledger stages are silent until explicitly classified.
- **ADR050-G3** — Widening the implementation surface (beyond `.py` under `src/`, `examples/`) or tightening dedup (per-prompt) is a governor change: it re-enters this ADR, not a hook-local edit.
- **ADR050-G4** — The reminder text is canonical English in `governor/stage_gate.py`, locale-rendered via `governor.locale` at emit time (issue #133 pattern); translations live only in `_LOCALE_KO`.
