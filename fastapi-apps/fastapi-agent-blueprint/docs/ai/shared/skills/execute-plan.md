# Execute Plan — Detailed Procedure

## Default Flow Position
See [target-operating-model §1](../target-operating-model.md) — `execute-plan` routing.

## Required Inputs

Use this skill for complex, architecture-changing, governor-changing, or multi-task work after an approved Execution Packet. Do not use it for trivial single-file edits, one-step single-skill work, or read-only exploration; those follow the normal Default Coding Flow and exception-token rules.

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

Within Selected Approach / Architecture Impact, carry the approved
[ADR decision basis](../adr-evidence.md), or the scoped reason none applies.
Recheck its material code/configuration premises in the fresh session. If an older
packet lacks this context, retrieve it from the approved decision and current
sources; report an unknown or contradiction rather than inventing intent, treating
it as missing approval, or silently choosing a new design. Existing scope and
ADR 050/054 boundaries remain authoritative.

If any field is missing, stop and return to `plan-feature`; do not infer the
missing contract during execution.

## Ticket input and fresh session

Accept a ticket issue reference; load its approved parent Execution Packet and the
[ticket workflow](../ticket-workflow.md). Run in a fresh session for that ticket,
retaining existing explicit authorization. Verify premises and predecessor/PR/CI
state first. Hydrate the existing ledger goal/scope/plan and planned task fields
from the issue before entering executing; a missing local ledger is not a missing
approval. A stale or contradictory ledger cannot supply intent. Keep ADR 054's
explicit execute-plan boundary and the existing stage vocabulary/schema.

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
6. **Run Review Gates** before completion. Implementation tickets default to one precision-filter
   cross-tool review by the other harness per `review-protocol.md` §7; mandatory
   governor review and full requested audits remain required. Codex-implemented work is reviewed
   by Claude, Claude-implemented work is reviewed by Codex:
   ```bash
   # Codex-implemented change set → Claude reviews:
   claude -p --permission-mode plan "<review prompt>"
   # Claude-implemented change set → Codex reviews:
   codex exec --model gpt-6.1-sol --sandbox read-only "<review prompt>"
   ```
   Use the ticket review model above with default effort; escalate to a stronger model or
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
7. **Integrate sync into the feature PR** before final review; standalone sync
   is reserved for release audits or post-merge drift. Generate the review packet
   (`uv run python tools/review_packet.py --base origin/main`) and report actual gate
   outputs and unverified limits. Follow the ticket measurement protocol.
8. **Close workflow state** only after Verification Gates and Review Gates are
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
