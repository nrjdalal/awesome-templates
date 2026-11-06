# FastAPI Agent Blueprint — Claude Harness Guide

Shared project rules live in [AGENTS.md](AGENTS.md).
This file intentionally keeps only Claude-specific setup and workflow guidance.

## Pre-work Checklist
1. Read `AGENTS.md` explicitly (not auto-loaded). Keep the core Default Coding Flow, exception tokens, ADR 050/054 boundaries and Reasoning-Level Consistency Guards in scope for all work. For routine source work, the Tool-Specific Harnesses, Common Commands and Drift Management sections and the Default Coding Flow subsections on Independent Review Trigger, Skill Mapping and Alignment may be deferred until harness/governor work needs them. Language Policy may be deferred only when no Tier 1 path is being edited.
2. Read shared workflow references from `docs/ai/shared/` when the task needs deeper context (`project-dna.md`, checklists, onboarding tracks)
3. Check current project status via `.claude/rules/project-status.md` (auto-loaded)
4. Check DO/DON'T in shared `AGENTS.md` / `project-dna.md`; architecture and overview projections are path-scoped. Consult a relevant projection if needed and not visible.

## Claude Collaboration Rules
- If diagnosis/review result is "adequate", do not force improvement suggestions
- Only propose modifying or deleting existing Claude-specific structures when the benefit is clear
- Skill frontmatter follows the [Claude Code reference](https://code.claude.com/docs/en/skills#frontmatter-reference), including `context: fork`, `agent`, `model`, `effort`, `allowed-tools` and `paths`; consult the reference for supported fields and semantics instead of maintaining a local exhaustive list.
- Before changing shared rules or structure, follow the drift management rules in `AGENTS.md`
- Shared workflow references now live under `docs/ai/shared/`; Claude skills should point there instead of keeping private copies
- When delegating to agents, explicitly pass the list of changed files
- Tier 1 shared/governance files are English-only; bilingual escape tokens and locale data files (`LOCALE_DATA_FILES`) are the two narrowly-scoped exceptions. See [AGENTS.md § Language Policy](AGENTS.md#language-policy) for the path list, hidden-rationale prohibition, and AI-when-editing rule. Conversation language is user-local (set by your global CLAUDE.md); file artefacts are governed strictly by the path policy.
- Reasoning-Level Consistency Guards (F / G / H / I) apply to every conversation, cross-review, and document-generation step — not only to PR-level work. See [AGENTS.md § Reasoning-Level Consistency Guards](AGENTS.md#reasoning-level-consistency-guards) for the canonical surface.

## Skills — defined in `.claude/skills/` (auto-listed each session; Codex: `.agents/skills/`)

Four are user-invoked only (`disable-model-invocation: true`) and therefore absent from the auto list:
`/sync-guidelines` (closure), `/migrate-domain {generate|upgrade|downgrade|status}`, and on-demand `/trace` and `/why`.

## Default Coding Flow

> Canonical: [`AGENTS.md` § Default Coding Flow](AGENTS.md#default-coding-flow). Long-form: [`docs/ai/shared/target-operating-model.md`](docs/ai/shared/target-operating-model.md).

Coding work routes through seven steps by default — `framing → approach options → plan → implement → verify → self-review → completion gate`. The Quality Gate Flow below is the `self-review` + `completion gate` portion of this flow; it is no longer the entire ceremony.

Default Flow is **subordinate** to (a) active sandbox / approval policy, (b) `.codex/rules/*` prefix rules, (c) safety hooks, (d) Absolute Prohibitions. Exception tokens (`[trivial]` / `[hotfix]` / `[exploration]` / `[자명]` / `[긴급]` / `[탐색]`, leading bracket on prompt line 1) reduce process burden but never override these.

## Quality Gate Flow (self-review + completion gate)
- Start with `/review-pr` for change-scoped review or `/review-architecture` for domain/full-repo structure audits.
- Run `/security-review` when the change touches security-sensitive surfaces — see `docs/ai/shared/skills/security-review.md` §"When to Use" for the canonical trigger list.
- If any review reports `Drift Candidates` or `Sync Required: true`, close the work with `/sync-guidelines` before treating the review as complete.
- `/sync-guidelines` is the closure step for shared docs, `project-dna.md`, skill wrappers, and Claude-specific rules that depend on shared references.

> Review output contract: `/review-pr`, `/review-architecture`, `/security-review` each emit
> `Scope / Sources Loaded / Findings / Drift Candidates / Next Actions / Completion State / Sync Required`.
> `/sync-guidelines` uses a separate terminal contract: `Mode / Input Drift Candidates / project-dna / AUTO-FIX / REVIEW / Remaining / Next Actions`.

## Domain Auto-discovery
- `discover_domains()` in `src/_core/infrastructure/discovery.py` auto-detects domains
- Server/Worker App-level Containers use `DynamicContainer` + factory function
- **No need to modify `container.py` or `bootstrap.py` when adding a new domain** (auto-registered)
- Domain Containers themselves use `DeclarativeContainer`

## Tool Selection Guidelines

> Shared architecture rules, terminology, conversion patterns, and DTO criteria are defined in `AGENTS.md`.
> Shared workflow references live in `docs/ai/shared/`.
> Consult [shared shell commands](docs/ai/shared/commands.md) when needed; architecture / overview rules load only for their scoped paths. Shared policy remains in `AGENTS.md`.
> context7 is a project-required MCP server for Claude (configured via `.mcp.json`).

### Code Exploration / Reading (by priority)
1. **Grep/Glob** (pattern search): symbol names, string patterns, config files, non-code files
2. **Read** (full content): when full file content is needed

### Impact Analysis
- For refactoring/signature changes: Grep for the symbol, its aliases and dynamic registrations (`getattr`, Selector maps, `__all__`), then run `uv run pyright` and the relevant tests. pyright catches a statically typed caller the search missed, but only inside `[tool.pyright] include`, and not a dynamic call — inspect those by hand
- For simple string search: Grep

### Editing
- All edits: Claude Code `Edit` tool
- PostToolUse hook auto-formats `.py` files after edits (ruff format + check)

### Routine Tasks
- Domain creation/API addition/tests/etc.: Skills (`/new-domain`, `/add-api`, etc.)

### Library Documentation
- **Proactively** use context7 whenever looking up library/framework/tool docs — do not wait for user to request it
- Applies to: API syntax, configuration, version migration, conventions (SQLAlchemy 2.0, Pydantic 2.x, Taskiq, Conventional Commits, etc.)
