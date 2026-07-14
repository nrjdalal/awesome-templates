# Shared Repo Facts

This file contains stable repository facts for Claude, Codex, and Antigravity workflows.

## Canonical Sources

- Shared rules: `AGENTS.md`
- Shared workflow references: `docs/ai/shared/`
- Claude harness: `CLAUDE.md`, `.claude/`
- Codex harness: `.codex/config.toml`, `.codex/hooks.json`, `.agents/skills/`
- Antigravity harness: `.gemini/settings.json`, `.antigravity/`

## Reference Code

- Use `src/user/` as the reference RDB domain when checking current patterns.
- Shared infrastructure lives under `src/_core/`.
- App entrypoints and bootstrap wiring live under `src/_apps/`.

## Shared Workflow Asset Map

- `docs/ai/shared/project-dna.md`: architecture truth and reference patterns
- `docs/ai/shared/scaffolding-layers.md`: new-domain file layout
- `docs/ai/shared/planning-checklists.md`: plan-feature questions, security matrix, task mapping, Execution Packet contract for `/execute-plan` / `$execute-plan`
- `docs/ai/shared/architecture-review-checklist.md`: architecture audit rules
- `docs/ai/shared/security-checklist.md`: OWASP-oriented review checklist
- `docs/ai/shared/test-patterns.md`: domain test generation patterns
- `docs/ai/shared/drift-checklist.md`: rule and docs drift inspection items
- `docs/ai/shared/onboarding-role-tracks.md`: onboarding depth tracks
- `docs/ai/shared/harness-asset-matrix.md`: living inventory of every harness asset and its bucket (Keep / Replace / Overlay / Drop)
- `docs/ai/shared/target-operating-model.md`: 7-step Default Coding Flow + exception-token vocabulary + Claude/Codex/Antigravity alignment + sample-workflow traces
- `docs/ai/shared/migration-strategy.md`: phased migration plan for the hybrid harness target architecture (Phase 0~5)
- `docs/history/archive/governor-review-log/`: **closed historical archive** (post-ADR-047) of 18 entries from the Phase 1~5 build-out. New independent review provenance lives in PR description Governor Footer (see ADR 047 D2, ADR 048 D1). See `governor-review-log/README.md` banner for the alias map back to ADR 047 G-slots.
- `docs/ai/shared/governor-paths.md`: canonical source of governor-changing path globs (Tier A / B / C + exclusions, including ADR 047 D4 sync-cosmetic carve-out). All consumer docs link this file; do not redeclare the list (Round-4 R4.3)
- `.agents/shared/governor/` (Phase 5 / #124, extended by ADR 047 PR B-F and the Antigravity adapter): shared governor *policy* Python package consumed by Claude/Codex/Antigravity hook adapters as thin shims. Modules — `paths.py` (REPO_ROOT discovery), `time_window.py` (single `_within_24h`), `tokens.py` (Phase 2 parser + EXPLORATION_TOKENS), `markers.py` (write_marker + read_latest_token + MarkerLifecycle enum + consume_phase2_markers per IC-11/IC-12), `safety.py` (HC-1 single-entry `safe_parse_exception_token` returning `Blocked | ParsedToken`), `verify.py` (Phase 3 REMINDER_TEXT + should_remind_claude), `completion_gate.py` (Phase 4 GateResult + evaluate_gate + render_reminder + parse_trigger_globs + match_log_entry), `sync_cosmetic.py` (ADR 047 D4 governor_subset + is_sync_cosmetic_only — `/sync-guidelines` self-loop carve-out), `locale.py` (AGENT_LOCALE rendering), and `__init__.py` (public API + `__all__`). Boundary: this package owns *policy*; tool-specific runtime utilities (`.codex/hooks/_shared.py`, Codex `session_id()` / verify-log writer / `cleanup_stale_verify_logs`, and `.antigravity/hooks/_shared.py`) remain per-tool. Hooks must not redeclare reminder strings or governor-paths globs inline (`tests/unit/agents_shared/test_governor_boundary.py` enforces this).
- `.agents/shared/work_ledger.py`: cross-session native workflow state. Schema v2 preserves v1 goal/scope/plan/verification fields and adds `workflow.stage`, `workflow.plan_ref`, `workflow.current_task`, `workflow.tasks[]`, and `workflow.review.{mode,status,reason}` for plan-feature / execute-plan handoff and advisory-only Stop reminders.
- `tools/check_governor_footer.py` (ADR 047 PR B-F / issue #157): CI checker enforcing the `## Governor Footer` block shape (10 fields, exact order, enum vocabularies, ADR{NNN}-G{N} grammar, fenced-block ignore) on governor-changing PR descriptions. Replaces the retired `tools/check_g_closure.py`. Wired in `.github/workflows/governor-footer-lint.yml` with `--require-governor-footer --changed-files @changed_files.txt` for the requiredness check.
- `.agents/shared/harness-python.sh`: POSIX shell launcher for agent hook Python execution. Resolution order is project `.venv/bin/python`, `uv run --no-sync python`, then compatible system Python `>=3.12.9`. Normal hooks fail open only on interpreter-resolution failure; doctor/canary mode sets `HARNESS_LAUNCHER_STRICT=1` to fail hard.
- `tools/check_harness_hook_surface.py`: local/pre-commit guard that rejects bare `python3` only in live agent hook execution surfaces (`.codex/hooks.json` and `.gemini/settings.json` command strings, plus executable lines in `.claude/hooks/*.sh`).
- `.github/pull_request_template.md`: GitHub PR template with the Governor-Changing PR checklist that artefact-locks independent review (ADR 048, superseding ADR 045 Pillar 5's cross-tool-only model) and self-application proof
- `.claude/state/` + `.codex/state/` + `.antigravity/state/` (gitignored): per-session governance state surfaces. Phase 2 (#121) writes exception-token marker JSON files here when a leading `[trivial]` / `[hotfix]` / `[exploration]` / `[자명]` / `[긴급]` / `[탐색]` token is recognised. Phase 4 (#123) resolves the IC-11 lifecycle: **Option A — read-and-delete on Stop**. Stop / AfterAgent adapters invoke `completion_gate.consume_phase2_markers()` which deletes all `exception-token-*.json` files in the respective state dir after reading. `read_latest_token_marker` also skips markers older than 24h (defensive against session-end failure leftovers).
- `.codex/state/verify-log-{session_id}.json` and `.antigravity/state/verify-log-{session_id}.json` (gitignored): Phase 3 (#122) per-session verify-class command logs. JSONL append-only — post-tool adapters record `pytest` / `make test` / `make demo[-rag]` / `alembic upgrade` invocations. Stop / AfterAgent adapters read only the *current session's* file (R0.2 — defeats cross-session silence) to decide whether to emit the verify-first reminder segment. Each entry stores `ts_epoch_ns` (R0.3) for subsecond freshness comparison against `Path.stat().st_mtime_ns`. Phase 4 (#123) adds opportunistic 24h cleanup of OTHER sessions' stale log files via `completion_gate.cleanup_stale_verify_logs()` on session end; the current session's log is never deleted.

## Context Management

- Keep root `AGENTS.md` short and stable.
- Prefer named skills (`.agents/skills/*/SKILL.md`) for local extension; `AGENTS.override.md` may be used only if it is explicitly subject to the same drift-management and language-policy governance as `AGENTS.md` itself.
- Put repeatable procedures in `.agents/skills/*/SKILL.md`.
- Use `codex -p research` or `codex --search` only when live web search is necessary.
- Treat Codex memories as personal or session-local optimization only, never as team governance.

## Verification Commands

```bash
codex mcp list
codex mcp get context7
codex debug prompt-input -c 'project_doc_max_bytes=400' "healthcheck" | rg "Shared Collaboration Rules|AGENTS\\.md"
codex execpolicy check --rules .codex/rules/fastapi-agent-blueprint.rules git push origin main
```

## Why context7 stays MCP (not plugin) — 2026-04-26 review

We considered migrating context7 from MCP (`.mcp.json` + `.codex/config.toml`)
to a Claude Code / Codex CLI plugin, motivated by `uv sync`-style one-shot
team setup. Decision: **keep MCP**. Two findings drove this:

- **Plugin SKILL auto-trigger reliability ≈ 50% in practice.** Token-budget
  truncation, YAML formatter conflicts, and Claude's task-completion bias
  cause silent skips. MCP + the explicit `CLAUDE.md` "Proactively use
  context7" rule yields deterministic invocation.
- **upstash/context7 has no official Codex CLI plugin.** Official targets
  are `--cursor`, `--claude`, `--opencode`. Splitting Claude(plugin) /
  Codex(MCP) creates a dual-track setup; using a third-party Codex plugin
  introduces maintenance risk.

Re-evaluate when any of the following becomes true:

1. upstash/context7 ships an official Codex CLI plugin.
2. Claude Code supports plugin auto-install ([anthropics/claude-code#28310](https://github.com/anthropics/claude-code/issues/28310)).
3. Skill auto-trigger reliability publicly improves to ≥ 80%, or the
   `SLASH_COMMAND_TOOL_CHAR_BUDGET` default is raised meaningfully.
4. The team grows enough that plugin-based onboarding automation becomes
   a clear win over the current `.mcp.json` + `.codex/config.toml` flow.
