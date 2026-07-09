# 054. Plan→Execute Boundary — Hard Gate on the `planned` Stage

- Status: Accepted
- Date: 2026-07-09
- Related: maintainer report (2026-07-09) — `/plan-feature` output slides into implementation without an explicit `/execute-plan` invocation.
- Amends: ADR [050](050-midtask-scope-expansion-gate.md) — narrows **ADR050-G1** (the stage gate is no longer advisory-only for the `planned` stage on Claude) and extends **ADR050-G2** with a sibling allowlist (`PLAN_EXECUTE_GATED_STAGES`). The `GATED_STAGES` advisory (no-plan case) and all other ADR 050 decisions remain in force unchanged.
- Constraints: ADR [052](052-native-execution-ledger-and-execute-plan.md) `/execute-plan` advisory-first policy and its false-positive-test bar are honoured (this is that bar's first invocation). Phase-5 governor architecture (fail-open shims over `.agents/shared/governor`) is reused, not modified.

## Summary

ADR 050 gave the Default Coding Flow a runtime nudge for the *no-plan* failure mode: an implementation edit while `workflow.stage ∈ {idle, complete, blocked}` fires an advisory routing to `/plan-feature`. It deliberately left the **`planned`** stage silent ("active stage") — but `planned` is precisely the window the maintainer wants held shut: a plan exists, `/execute-plan` has **not** been invoked, and the agent begins implementing anyway.

This ADR closes that window with a **hard gate**, scoped to exactly the `planned` stage and only on Claude:

1. **Shared policy** — a `PLAN_EXECUTE_GATED_STAGES = {planned}` allowlist, a canonical `PLAN_EXECUTE_REMINDER`, and two pure decisions (`should_block_plan_execute_edit`, `should_plan_execute_gate`) in `governor/stage_gate.py`.
2. **Claude hard block** — a `PreToolUse Edit|Write` hook that blocks (exit 2 + model-visible stderr) when an implementation-source edit is attempted while the ledger stage is `planned` and no plan-waiver token is active.
3. **Codex advisory** — Codex has no `PreToolUse`; it gets a Stop-time advisory (`plan_execute_segment`) reusing the shared policy, mirroring the #269 `stage_gate_segment` adapter.

## Background

The building blocks are all from ADR 050 / ADR 052:

- `.agents/state/current-work.json` records `workflow.stage`. `/plan-feature` writes `planned`; `/execute-plan` writes `executing` on entry (ADR 052).
- `governor/stage_gate.py` already owns `is_implementation_source`, `read_ledger_stage`, `PLAN_WAIVER_TOKENS` reads, and the once-per-session marker lifecycle.
- ADR050-G1 explicitly pre-authorised this: *"Promotion to a hard gate requires a dedicated hardening PR with false-positive tests covering exploration, trivial edits, and single-skill work."* This ADR is that promotion, restricted to the `planned` stage.

Why the `planned` case justifies a block where the no-plan case (ADR 050 D1) did not: the no-plan advisory fires in ordinary auto-mode work where blocking would punish exploration and trivial edits with approval fatigue. The `planned` gate fires only when a plan **explicitly exists** and execution has been **explicitly deferred** to `/execute-plan` — a narrow, intentional state that the developer entered on purpose. Blocking there enforces a boundary the developer already declared, rather than second-guessing ordinary work.

## Decision

### D1 — Hard block, `planned` stage only, Claude only

A `PreToolUse Edit|Write` hook blocks the edit (exit 2) when `should_block_plan_execute_edit` is true. The block is confined to `PLAN_EXECUTE_GATED_STAGES = {planned}`. Every other stage (`idle`/`complete`/`blocked` → ADR 050 advisory; `executing`/`reviewing` → silent; unknown → silent) is unaffected.

### D2 — Separate allowlist, mutually exclusive with `GATED_STAGES`

`PLAN_EXECUTE_GATED_STAGES` is a distinct frozenset, not an addition to `GATED_STAGES`. The two never overlap: a stage is either "no plan" (ADR 050) or "planned, not executing" (this ADR) or neither. This preserves ADR050-G2's allowlist discipline — unknown stages stay silent in both gates.

### D3 — Channel: `PreToolUse` exit 2 + stderr (mirrors `pre_tool_security.py`)

ADR 050 D3 chose `PostToolUse` *because it wanted a non-blocking, model-visible channel* — and `PreToolUse` has none (exit 2 blocks; a permission-decision reason targets the user). Here the goal is the opposite: **block the edit**. `PreToolUse` exit 2 is therefore the correct mechanism, and its stderr is fed back to the model (the same channel `pre_tool_security.py` relies on to surface `[BLOCKED]` messages). The wrapper propagates the Python exit code (it does **not** force `exit 0`, unlike `stage-gate.sh`).

### D4 — No Claude `PostToolUse` advisory for `planned` (would be dead code)

A `PostToolUse` advisory mirroring ADR 050's for the `planned` stage was considered and rejected: the `PreToolUse` block intercepts exactly the cases it would fire on *before* the edit completes, so no `PostToolUse` runs; and in the one case the block yields (a plan-waiver token), the advisory would honour the same token and stay silent too. It would never surface. Planned-stage detection therefore lives as **shared policy** consumed by two call sites — the Claude block (D1) and the Codex Stop advisory (D8) — with no Claude `PostToolUse` participant.

### D5 — No once-per-session dedup on the block

The ADR 050 advisory fires once per session (D5) — a nudge budget. A **block** must not dedup: if it fired only once, the agent's second attempt would pass and the boundary would be illusory. `should_block_plan_execute_edit` therefore has no `has_fired_this_session` term; it holds on every edit until `/execute-plan` advances the stage to `executing` (or a waiver token is used).

### D6 — Suppression + release paths

The block yields when a **plan-waiver token** (`[trivial]`/`[hotfix]` and Korean equivalents, `PLAN_WAIVER_TOKENS`, read via `MarkerLifecycle.READ_ONLY` with the 24h filter) is active — consistent with ADR 050 D6. `[exploration]` does not suppress (it also implies no committed plan). The intended release path is **invoking `/execute-plan`**, which advances the stage to `executing` and the block stops matching. A developer who used `/plan-feature` only to think and wants to proceed manually uses a waiver token or resets the ledger stage.

### D7 — Surface unchanged: `.py` under `src/`/`examples/`, `Edit|Write` only

The block reuses `is_implementation_source` verbatim — no widening, so ADR050-G3 is not re-entered. Like the ADR 050 advisory, it inspects `tool_input.file_path` (`Edit`/`Write`) and does **not** parse `Bash` redirect/`tee`/heredoc writes. A `Bash`-based write to `src/*.py` while `planned` is a known bypass, at parity with the advisory; closing it (reusing `pre_tool_security._extract_bash_write`) is a documented follow-up, not this ADR's surface.

### D8 — Codex parity: Stop-time advisory, not a block

Codex has no `PreToolUse` and cannot hard-block. It gets `plan_execute_segment` in `.codex/hooks/stop-sync-reminder.py`, a Stop-time advisory reusing the shared `should_plan_execute_gate` (with once-per-session dedup, the Codex advisory budget) — the exact shape of the #269 `stage_gate_segment`. The resulting asymmetry is intentional and recorded: **Claude blocks at edit time; Codex advises at Stop time.** Codex's enforcement model is Stop-time review, so an advisory there is the faithful analogue of a Claude edit-time block.

### D9 — Best-effort by fail-open

Every failure path allows the edit (HC-5.5): shared-import failure, unreadable ledger, malformed payload, or any exception → exit 0 (no block). The block **reduces** the leak; it does not guarantee it. Making the gate fail-closed was rejected — a ledger I/O error must never wedge the developer's ability to edit code.

### D10 — Depends on `/plan-feature` writing `stage=planned`

The block only fires when the ledger positively reads `planned`. If `/plan-feature` skips its ledger write, the stage stays `idle`/`complete` and the ADR 050 advisory (not this block) is what fires. Task T5 hardens the `/plan-feature` wrapper wording so the ledger write is a required close-out step, shrinking this gap.

### Fail-open invariants (inherited, restated)

The block hook performs no network access, writes nothing (pure read of ledger + token marker), contains no top-level `sys.exit`/`SystemExit` outside `if __name__ == "__main__"`, and allows the edit on any shared-import or evaluation failure.

## Consequences

- The plan→execute boundary is enforced on Claude: an approved plan can no longer silently slide into implementation. Auto-mode work outside the `planned` stage is unaffected (no new blocking surface for ordinary edits).
- The work ledger gains a second load-bearing consumer of `stage=planned`. Skills that forget to write the stage weaken the block to an advisory (D10) — never a false block.
- One more `PreToolUse` command runs per `Edit`/`Write` (one JSON read + one ledger read + one token-marker glob; negligible, and only on the `Edit|Write` matcher).
- Claude and Codex diverge in enforcement strength for this boundary (D8). This is the first intentional Claude/Codex asymmetry in the governor surface and is pinned by ADR054-G4.

### Durable Governance Constraints

- **ADR054-G1** — The `planned`-stage gate is a **hard block on Claude** (`PreToolUse` exit 2), superseding ADR050-G1 for this stage only. ADR050-G1 remains in force for `GATED_STAGES`. The promotion is justified by the false-positive suite (exploration, trivial/hotfix, single-skill/`executing`, non-impl paths, missing ledger) required by ADR050-G1 / ADR 052.
- **ADR054-G2** — `PLAN_EXECUTE_GATED_STAGES` is a separate allowlist, disjoint from `GATED_STAGES`. Adding or moving stages between the two re-enters this ADR.
- **ADR054-G3** — Block release paths are `/execute-plan` (stage→`executing`) and `PLAN_WAIVER_TOKENS`. Removing or adding an escape is a governor change.
- **ADR054-G4** — Claude blocks; Codex advises (no `PreToolUse`). Introducing a blocking Codex path, or downgrading the Claude block to advisory, re-enters this ADR.
- **ADR054-G5** — The gate is best-effort by fail-open (D9). Making it fail-closed is a governor change.
- **ADR054-G6** — Surface is `.py` under `src/`/`examples/` via `Edit|Write` only (D7). Widening to `Bash` writes or other paths re-enters this ADR (and ADR050-G3).
