# Execute Plan — Detailed Procedure

## Default Flow Position

This skill owns the native execution handoff after `/plan-feature` or
`$plan-feature` produces an approved Execution Packet.

- **Consumes**: Execution Packet with Goal, Scope, Success Criteria, Selected
  Approach, Architecture Impact, Task List, Verification Gates, and Review Gates.
- **Participates in**: `implement`, `verify`, `self-review`, and `completion gate`.
- **Routes to**: implementation skills such as `/new-domain`, `/add-api`,
  `/add-cross-domain`, `/add-worker-task`, `/migrate-domain`, and the matching
  Codex `$skill` names.

Do not use this skill for trivial single-file edits, one-step single-skill
work, or read-only exploration. Those continue through the normal Default
Coding Flow and exception-token rules.

## Required Inputs

Before execution starts, confirm the Execution Packet contains:

- **Goal** — one sentence describing the user-visible outcome.
- **Scope** — affected domains, harness files, interfaces, or explicitly
  out-of-scope surfaces.
- **Success Criteria** — observable conditions that prove the work is complete.
- **Selected Approach** — the chosen approach and one-line reason.
- **Architecture Impact** — layer, domain, dependency, DTO, and migration impact.
- **Task List** — ordered tasks with dependencies and mapped skills.
- **Verification Gates** — exact tests, checks, language-policy commands, or
  manual probes required before completion.
- **Review Gates** — self-review, architecture/security review, sync-guidelines,
  and governor-changing review mode when applicable.

If any field is missing, stop and return to `plan-feature`; do not infer the
missing contract during execution.

## Execution Procedure

1. **Record workflow start** in the shared ledger:
   ```python
   from work_ledger import update_workflow_state

   update_workflow_state(
       stage="executing",
       plan_ref="<issue, PR, or plan file>",
       current_task="<first task title>",
       tasks=[
           {"id": "1", "title": "<task title>", "status": "in_progress"},
       ],
       updated_by="skill:execute-plan",
   )
   ```
2. **Execute tasks in dependency order**. For each task, call the mapped
   implementation skill when one exists. Manual implementation is allowed only
   when the Task List marks the task as unmappable.
3. **Use test-first changes for behavior**. Add or update a failing test before
   production code whenever the task changes behavior, contracts, hooks, or
   workflow state.
4. **Update ledger task state** after each task:
   - `in_progress` when the task starts.
   - `completed` after its verification passes.
   - `blocked` with a reason when progress needs user or external input.
5. **Run Verification Gates exactly**. Verification failure returns to the
   current task; do not mark the task complete until the failing gate passes or
   is explicitly deferred with rationale.
6. **Run Review Gates** before completion. Governor-changing work defaults to
   cross-tool review by the other harness — Codex-implemented work is reviewed
   by Claude, Claude-implemented work is reviewed by Codex:
   ```bash
   # Codex-implemented change set → Claude reviews:
   claude -p --permission-mode plan "<review prompt>"
   # Claude-implemented change set → Codex reviews:
   codex exec --sandbox read-only "<review prompt>"
   ```
   Start from the default model and effort; escalate to a stronger model or
   higher effort only when warranted (AGENTS.md § Independent Review Trigger;
   `target-operating-model.md` §5 Model And Effort Cost Policy).
   If the reviewing tool's authentication or tooling fails, use
   `self-structured` or `human:<handle>` review instead, and record the
   fallback reason:
   ```python
   update_workflow_state(
       review_mode="self-structured",
       review_status="fallback",
       review_reason="cross-tool CLI authentication unavailable",
       updated_by="skill:execute-plan",
   )
   ```
7. **Close workflow state** only after Verification Gates and Review Gates are
   satisfied:
   ```python
   update_workflow_state(
       stage="complete",
       current_task=None,
       review_status="complete",
       updated_by="skill:execute-plan",
   )
   ```

## Advisory-First Enforcement

This workflow starts as advisory-first. Stop hooks may remind the agent when
workflow state is missing, verification is pending, or governor-changing work
has no recorded review state. These reminders do not block execution.

Future hardening PRs may promote only high-confidence conditions to hard gates
or CI failures. Candidate conditions must have tests and must avoid broad
false positives for exploration, trivial edits, and single-skill work.

## Output Contract

When closing, report:

- Task states and any deferred items.
- Verification commands and results.
- Review mode, status, fallback reason if any, and Governor Footer implications.
- Sync-guidelines result when shared rules, skills, wrappers, or harness
  behavior changed.
