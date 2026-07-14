# Migration Strategy

> Last synced: 2026-05-06 (PR-B.4b — Phase 1-5 closed, migration complete)
> Source of truth for the phased migration from the current harness to the Target Operating Model.
> Sibling docs: [ADR 045](../../history/045-hybrid-harness-target-architecture.md) · [harness-asset-matrix.md](harness-asset-matrix.md) · [target-operating-model.md](target-operating-model.md)

> **Migration record (2026-05-06):** All five phases of Hybrid Harness v1 (#117) are closed. Phase 1 (Default Flow + skill wrappers), Phase 2 (exception-token UserPromptSubmit, PR #126), Phase 3 (verification-first adapters, PR #127), Phase 4 (completion-gate Stop adapter, PR #128), and Phase 5 (shared governor module, PR #130) are all shipped. The `completion gate` step is now mandatory-by-default with non-blocking enforcement via the Phase 4 Stop hook and Governor Footer Lint CI. The dual-system window described in §3 is closed; escape tokens remain a permanent feature. This document is now a historical migration record; the Target Operating Model is the authoritative runtime reference.

## Purpose

This document answers issue #117 Required Output #3: define the phased migration that takes the repo from "good rules without strong default routing" to the Target Operating Model. The migration is intentionally **phased, additive, and rollback-safe** — never a big-bang replacement.

## §1 Phase Structure

Each phase has three parts (per Codex review R2):

- **Shared policy** — what the phase decides at the canonical level (`AGENTS.md`, shared docs).
- **Claude adapter** — how Claude's hook surface implements the policy.
- **Codex adapter** — how Codex's hook surface implements the policy.

The shared-policy part is identical across tools; the adapters differ because the hook surfaces differ (see [target-operating-model.md §5](target-operating-model.md)).

### Phase 0 — Design Outputs (this PR)

**Shared policy**:
- ADR 045 (decisions + design-question resolutions)
- `harness-asset-matrix.md` (living inventory)
- `target-operating-model.md` (workflow + sample traces)
- `migration-strategy.md` (this file)

**Claude adapter**: cross-link in `CLAUDE.md` (Quality Gate Flow section update).
**Codex adapter**: none (config / hooks unchanged in Phase 0).

**Acceptance**: ADR 045 reviewable, all four design docs present, asset-matrix bucket distribution within ±15% of the predicted ~70% Keep.
**Rollback**: revert this PR.

### Phase 1 — Default Flow Constitutional Section + Skill Body Mandatory Phases (this PR)

**Shared policy**:
- `AGENTS.md` § Default Coding Flow (precedence rules, mandatory subset, exception vocabulary)
- 14 skills × 3 wrapper layers gain a "Default Flow Position" section
- `docs/ai/shared/skills/{name}.md` shared procedures gain explicit pre-/post-step routing notes
- `.codex/rules/fastapi-agent-blueprint.rules` `git push` justification updated to reference Default Flow verification

**Claude adapter**: `CLAUDE.md` Quality Gate Flow update; `.claude/rules/architecture-conventions.md` Default Flow cross-link.
**Codex adapter**: none (no hook changes; the adapter for Codex is the rule-file justification update + skill-body wrappers).

**Acceptance**:
- All 14 × 3 wrappers have consistent Default Flow Position content (verified by `/sync-guidelines`).
- Recursion guards present in `plan-feature`, `review-pr`, `review-architecture`, `security-review`, `sync-guidelines`, `fix-bug`, `onboard`.
- Drift checklist in `drift-checklist.md` includes a row for matrix-vs-filesystem.

**Rollback**: revert the Phase 1 PR. Pre-existing skill bodies are unchanged in essence; the position section is additive and removable.

### Phase 2 — Exception Token Vocabulary + UserPromptSubmit Adapters (separate issue)

**Shared policy**:
- Exception-token recognition rules formalised as a regex (`^\s*\[(trivial|hotfix|exploration|자명|긴급|탐색)\](?:\s|$)`) with NFKC normalisation.
- Decision payload schema (`{"matched": bool, "token": str|null, "rationale_required": bool}`) shared between Claude, Codex, and later Antigravity implementations.
- Token usage carries a follow-up obligation logged to a per-session marker file.

**Claude adapter**: new `.claude/hooks/user-prompt-submit.sh` (Claude does not currently have one). Wires to a `.claude/settings.json` UserPromptSubmit entry with no matcher (all prompts).
**Codex adapter**: extend `.codex/hooks/user-prompt-submit.py` with the same parser. Output is informational (does not block prompt submission).

**Acceptance**:
- Identical decisions on identical input across tools.
- Korean tokens stable through NFKC.
- Hook output is logged but does not change prompt-submission behaviour (informational-only in this phase).
- Parser fixtures cover at minimum: no token, English tokens, Korean tokens, NFKC-normalised Korean variants, body-only token (must be ignored), malformed bracket (must be ignored), token followed by no-whitespace boundary. Fixtures live in the Phase 2 PR under the per-tool hook tests; Phase 5 may relocate them to `.agents/shared/governor/`.

**Rollback**: revert the Phase 2 PR; the hooks are additive.

**Risk**: Medium. New Claude hook entry; payload schema must be confirmed against Claude SDK spec before implementation.

### Phase 3 — Verification-First Adapter (separate issue)

**Shared policy**:
- After each `implement` step, the Default Flow expects a `verify` step within the same session (or before commit).
- "Verification" includes: test invocation, `make demo`, `make demo-rag`, `alembic upgrade head` (for migration changes), or an explicit user confirmation.

**Claude adapter**: extend `.claude/hooks/post-tool-format.sh` (or add a new sibling) on `PostToolUse Edit|Write` matchers. After Python file edits, suggest `/test-domain run {domain}`. Output is an advisory reminder, not a block — since #271 delivered as model-visible `hookSpecificOutput.additionalContext` JSON on stdout with exit 0 (the original stderr-on-exit-0 emit reached only the user transcript, never the model; recorded as an ADR 050 D3 drift candidate).
**Codex adapter**: **cannot rely on `PostToolUse Bash`** (Codex review R7). Instead, extend `.codex/hooks/stop-sync-reminder.py` to compute `git status --porcelain` and produce the verification reminder when source files changed without a verify-class command being run. Run a small in-session log file under `.codex/state/` (gitignored) to track verify invocations within a session.

**Acceptance**:
- Claude adapter triggers on `Edit`/`Write` hooks for `.py` files.
- Codex adapter triggers on Stop when `git status --porcelain` shows changed `*.py` files and no verify-class log entry exists.
- Both adapters use **identical reminder message format** at delivery. Implementation: each adapter may stage a per-tool inline template (or a per-tool template file) until Phase 5 consolidates them into a shared template under `.agents/shared/templates/`. Phase 3 must not depend on a Phase 5 deliverable.
- False-positive rate measured during a one-week soak test before promoting from informational to harder reminder.

**Rollback**: revert the Phase 3 PR. Hook scripts are independently editable.

**Risk**: Medium-high. The Codex adapter introduces a new state-tracking file pattern; semantics must be agreed across both tools.

### Phase 4 — Completion Gate Hook (separate issue)

**Shared policy**:
- At session end (Stop), a "completion gate" check evaluates whether the session produced uncommitted source changes that lacked verification or self-review.
- The check is a **hard reminder** (clear stderr output). It does **not** block `git commit` directly; the user is informed and may choose to act.
- If an exception token was used, the gate accepts that as the rationale and does not warn.

**Claude adapter**: extend `.claude/hooks/stop-sync-reminder.sh` to merge completion-gate output with the existing sync-reminder output (single Stop hook output).
**Codex adapter**: extend `.codex/hooks/stop-sync-reminder.py` similarly. Output format identical across tools.

**Acceptance**:
- Output is merged with sync-reminder in a single Stop event (no duplicate Stop hooks).
- Gate respects auto-escapes (changed_files == 0, **general** doc-only, comment-only) and exception tokens. Policy/harness doc paths are **not** auto-escaped (see `target-operating-model.md` §3 carve-out).
- Sample workflow traces from `target-operating-model.md` Appendix B can be reproduced under the gate without false-positive warnings.
- **Governor-changing PR check** (Pillar 7, post-ADR-047): when `changed_files` intersects the trigger globs in [`governor-paths.md`](governor-paths.md) (Tier A / B / C minus exclusions, including the new `/sync-guidelines` cosmetic carve-out from ADR 047 D4), the gate emits a reminder pointing to the PR-description `## Governor Footer` requirement. The local Stop hook cannot inspect the PR body, so the actual presence + shape check happens in the `Governor Footer Lint` CI workflow (`tools/check_governor_footer.py --require-governor-footer`); the Stop hook reminder is informational and points at the same authority. This is a reminder, not a hard block — consistent with issue #117 Non-Goals.
- The log-only backfill exclusion in [`governor-paths.md`](governor-paths.md) applies: a PR whose changed files lie entirely under `governor-review-log/` (extending or correcting an existing entry in the closed historical archive) is exempt.
- The sync-cosmetic exclusion (ADR 047 D4) applies: a PR whose governor-matching subset is limited to `Last synced:` lines and `Recent Major Changes` table rows on the three covered `.claude/rules/*.md` files is exempt.
- Sample runs to validate the gate:
  - Session edits `AGENTS.md` only → reminder surfaces (CI footer linter then enforces presence + shape).
  - Session edits `src/user/...` plus `.claude/rules/project-status.md` `Last synced:` line → no reminder (sync-cosmetic exemption applies to the governor-matching subset).
  - Session edits `AGENTS.md` plus `.claude/rules/project-status.md` `Last synced:` line → reminder surfaces (subset includes AGENTS.md, which is not in the cosmetic set).
  - Session edits only `governor-review-log/pr-100-*.md` (errata to a frozen entry) → no reminder.

**Rollback**: revert the Phase 4 PR. The merge with sync-reminder is structured so the existing reminder remains if the gate logic is removed.

**Risk**: Medium. Output merge with existing reminders requires careful template design.

### Phase 5 — Cross-Tool Consolidation (separate issue)

**Shared policy**:
- Common parser, policy logic, and reminder templates extracted to `.agents/shared/governor/` so both adapters import the same module rather than maintain parallel implementations.
- The shared module is Python (Codex hooks are Python); Claude shell hooks call it through `.agents/shared/harness-python.sh` so hook execution uses the project-compatible interpreter.

**Claude adapter**: shell hooks call into the shared module.
**Codex adapter**: Python hooks `import` the shared module directly.
**Antigravity adapter**: Python hooks under `.antigravity/hooks/` import the shared module directly and are wired through `.gemini/settings.json`.

**Acceptance**:
- Single source for token vocabulary, parser, completion-gate logic.
- No silent divergence possible; tests in `tests/unit/agents_shared/` enforce parity.
- Phase 2~4 hooks rewritten to consume the shared module; behaviour unchanged.

**Rollback**: revert the Phase 5 PR. Phase 2~4 hooks return to their per-tool implementations.

**Risk**: Low (pure refactor by the time we reach Phase 5).

### Post-v1 — Mid-Task Stage-Gate Adapters (ADR 050, issue #268)

Policy lives in `.agents/shared/governor/stage_gate.py` (Phase-5 architecture reused). Adapter status:

- **Claude adapter (shipped, #268)**: `PostToolUse Edit|Write` shim `.claude/hooks/post_tool_stage_gate.py` emitting `hookSpecificOutput.additionalContext` JSON — the documented model-visible non-blocking channel (ADR 050 D3).
- **Codex adapter (shipped, #269)**: Codex has no PostToolUse. The parity shape mirrors Phase 3 ("Claude PostToolUse + Codex Stop changed-files"): a Stop-time advisory in `.codex/hooks/stop-sync-reminder.py` (`stage_gate_segment`, advisory #6) that bridges the changed-file set to the shared single-file `should_stage_gate` policy — it synthesizes a payload for the first changed implementation source, evaluates it against the ledger stage, and dedupes per `CODEX_THREAD_ID` via the shared `stage_gate.mark_fired`. The decision runs before Phase 2 marker consumption because the shared policy reads the exception-token (plan-waiver) markers that consumption deletes. Reuses `governor.stage_gate` unchanged — adapter-only, no policy change; parity + decision + ordering tests in `tests/unit/agents_shared/test_stage_gate.py`.
- **Antigravity adapter (shipped, 2026-07-09)**: `.gemini/settings.json` wires Antigravity / Gemini CLI events to `.antigravity/hooks/`. `BeforeAgent` mirrors UserPromptSubmit token parsing, `BeforeTool` mirrors shell/code safety, `AfterTool` records verify-class commands, and `AfterAgent` merges sync, verify-first, completion-gate, native workflow, and stage-gate advisories. Runtime state is isolated under `.antigravity/state/`. The adapter reuses `.agents/shared/governor/` policy unchanged and is covered by `tests/unit/agents_shared/test_antigravity_harness.py` plus the shared boundary and language-policy tests.

### Post-v1 — Plan→Execute Boundary Adapters (ADR 054)

Same shared policy (`governor/stage_gate.py`), a **disjoint sibling gate** keyed to `PLAN_EXECUTE_GATED_STAGES = {planned}`. Here the two adapters diverge in **enforcement strength** — the first intentional Claude/Codex asymmetry in the governor surface (ADR054-G4):

- **Claude adapter (this change)**: a `PreToolUse Edit|Write` **hard block** `.claude/hooks/pre_tool_stage_block.py`, using `should_block_plan_execute_edit` (no session dedup — the block must hold on every edit). It blocks with exit 2 + stderr (the model-visible `PreToolUse` channel that `pre_tool_security.py` uses), not `additionalContext` — because here the goal is to *block* the edit, the inverse of ADR 050's non-blocking intent (ADR 054 D3). No Claude `PostToolUse` advisory for `planned`: the block intercepts the same cases pre-edit, so one would be dead code (ADR 054 D4).
- **Codex adapter (this change)**: Codex has no `PreToolUse` and cannot block, so parity is an *advisory*, not a block: `plan_execute_segment` in `.codex/hooks/stop-sync-reminder.py`, mirroring `stage_gate_segment` but calling `should_plan_execute_gate` (with per-session dedup). The two Stop segments key off disjoint stages, so at most one fires; they share the once-per-session marker. Reuses `governor.stage_gate` unchanged — adapter-only. Tests in `tests/unit/agents_shared/test_plan_execute_gate.py`.

Both are best-effort by fail-open (ADR054-G5): any unreadable ledger / import failure / malformed payload allows the edit. The Claude wrapper `pre-tool-stage-block.sh` propagates the Python exit code (unlike `stage-gate.sh`, which always exits 0), and the harness-python launcher itself exits 0 when no interpreter resolves, so a broken environment never wedges editing.

## §2 Rollback

Every phase is single-PR-revertable. The repo is never left in an intermediate state where one tool implements a phase and the other does not, because each phase is merged as a unit (shared policy + both adapters + tests).

| Phase | Rollback action |
|---|---|
| 0 | revert this PR (only loses design docs and matrix; no behaviour change) |
| 1 | revert Phase 1 PR (skill bodies revert to pre-Default-Flow text; AGENTS.md § removed) |
| 2 | revert Phase 2 PR (hooks reverted; vocabulary still defined in §3 of operating model but parser absent) |
| 3 | revert Phase 3 PR (verification reminders disappear; sessions return to manual verification discipline) |
| 4 | revert Phase 4 PR (completion-gate output disappears; sync-reminder remains) |
| 5 | revert Phase 5 PR (per-tool implementations remain; only the consolidation is undone) |

The single-PR-revertable invariant requires that no phase depend on the *internal implementation* of a previous phase. Phases depend only on each other's *acceptance criteria*. If Phase 5 needs to be reverted, Phase 2~4 still work because their per-tool implementations remain valid.

## §3 Dual-System Operation Window

During Phases 1~4 the repo operates a **dual system**:

- The pre-existing free-form invocation (user types a slash command when they want to) continues to work for users and tools that do not yet route through Default Flow.
- The Default Flow guidance + adapters provide informational prompts that nudge work into the canonical flow.

This window is intentional: it lets the team observe false-positive rates and refine adapters before any phase becomes a hard block.

The window closes at Phase 5 only in the sense that the parser/policy is consolidated; **even after Phase 5, escape tokens remain a permanent feature**. The model is hybrid forever; full hard-blocking enforcement is explicitly out of scope (see [ADR 045 §Alternatives Considered](../../history/045-hybrid-harness-target-architecture.md)).

## §4 Asset Movement Order

The order in which assets are touched matters for review-burden management.

1. **First (Phase 0+1, this PR)** — `AGENTS.md` § Default Coding Flow + the four design docs + 14 × 3 skill wrappers + minor cross-links and rule-file justification update. All additive changes; no file removals.
2. **Second (Phase 2)** — `UserPromptSubmit` hooks. New hook entry on Claude side; existing hook extension on Codex side. Touches `.claude/settings.json` and `.codex/hooks.json`.
3. **Third (Phase 3)** — `PostToolUse` (Claude) / Stop (Codex) verification adapters. Touches existing hook scripts.
4. **Fourth (Phase 4)** — Stop completion gate. Output merge into existing sync-reminder.
5. **Fifth (Phase 5)** — `.agents/shared/governor/` module creation; per-tool hooks rewritten to consume it.

Hook surfaces (`.claude/settings.json`, `.codex/hooks.json`, and later `.gemini/settings.json`) are touched only when a tool adapter needs a runtime event mapping. Hook implementation files (`.claude/hooks/*`, `.codex/hooks/*`, `.antigravity/hooks/*`) are thin shims over shared policy after Phase 5. Constitutional surfaces (`AGENTS.md`, ADRs) are stable from Phase 1 onward except for explicit governor-changing extensions.

## §5 What Stays Stable Until the End

The following assets are **not** touched by Phases 1~5 (their content is constant; only cross-link metadata may add):

- `.claude/rules/absolute-prohibitions.md`
- `.claude/rules/project-overview.md`
- `.claude/rules/architecture-conventions.md` (one cross-link added in Phase 1; structural content unchanged)
- `.codex/rules/fastapi-agent-blueprint.rules` (one justification line updated in Phase 1)
- `docs/ai/shared/project-dna.md`
- `docs/ai/shared/scaffolding-layers.md`
- `docs/ai/shared/architecture-diagrams.md`
- All ADRs in `docs/history/0XX-*.md` for `XX < 45` (architecture / DI / responsibility decisions are immutable)
- All implementation skill **bodies** (the Default Flow Position section is additive; the procedure detail does not change)

If any of these need to change during the migration, that change is its own ADR, not part of this strategy.

## §6 Full Replacement vs Hybrid — When to Re-Evaluate

The model is "Mostly Local with Philosophy Overlay" because the asset-matrix bucket distribution is approximately ~80% Keep / ~20% Overlay / 0% Replace / 0% Drop (Phase 5 #124 closure; [harness-asset-matrix.md §Bucket Distribution Summary](harness-asset-matrix.md#bucket-distribution-summary)).

The hybrid model is justified as long as:
- Keep ≥ 60%, AND
- Overlay ≤ 30%, AND
- No phase has reduced the per-tool diff for an adapter to less than ~50 lines (i.e. the adapters remain meaningfully tool-specific).

If a future audit shows Keep < 30% (i.e. ≥70% of assets have moved to Overlay or Replace), full philosophy adoption — possibly absorbing one or more upstream packages — would justify re-evaluation. The threshold is intentionally high; reaching it would imply that >70% of the harness has become commodity scaffolding, which is unlikely in a project-specific FastAPI/DDD architecture.

## §7 Follow-Up Issues

Phase 2~5 each correspond to a separate GitHub issue, registered immediately after Phase 0+1 (this PR) merges. The issue titles follow the pattern:

- `#121 — Hybrid Harness Phase 2: exception-token UserPromptSubmit adapters` (PR #126)
- `#122 — Hybrid Harness Phase 3: verification-first adapters (Claude PostToolUse Edit|Write + Codex Stop changed-files)` (PR #127)
- `#123 — Hybrid Harness Phase 4: completion-gate Stop adapter (merged with sync-reminder)`
- `#124 — Hybrid Harness Phase 5: shared governor module under .agents/shared/governor/`

Each issue copies its acceptance criteria from this document and references ADR 045 for context.

The "Hybrid Harness v1" milestone groups these four issues so progress is visible. Closure of all four issues plus this PR's merge is the completion criterion for issue #117.
