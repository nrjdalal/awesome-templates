# 031. Shared Rules and Tool-Specific Harnesses

- Status: Accepted
- Date: 2026-04-12
- Related issue: #66
- Related ADR: [020](020-aidd-skills-governance.md)(AIDD governance), [021](021-architecture-governance-hooks-ci.md)(architecture enforcement), [030](030-serena-removal-pyright-rules.md)(Claude harness simplification)

## Summary

To support both Claude Code and Codex CLI without duplicating project rules, we introduced `AGENTS.md` as the canonical shared rule source and reorganized tool-specific behavior into thin harness files such as `CLAUDE.md`, `.mcp.json`, and `.codex/config.toml`.

## Background

- **Trigger**: The repository already had a mature Claude-centered AIDD structure, but Codex CLI support was being added. Keeping all shared rules inside `CLAUDE.md` would force Codex support to either duplicate those rules or couple itself to a Claude-specific file.
- **Decision type**: Experience-based extension — the original governance system worked well for Claude, but expanding to a second tool exposed the need to separate stable project rules from tool runtime configuration.

The goal was not to rebuild the entire AI workflow system. It was to preserve the existing Claude workflow while making Codex usable at the repository level with minimal friction and minimal drift risk.

## Problem

### 1. Shared rules were stored in a Claude-specific file

`CLAUDE.md` contained both project-wide rules and Claude-only operational guidance. This made the file a poor fit as a cross-tool source of truth.

### 2. Rule duplication would create drift

If Codex received its own copy of architecture rules, conversion patterns, DTO criteria, and command references, those copies would drift from Claude docs and from each other.

### 3. Verification was under-specified for Codex

Codex support needed an explicit, documented verification path:
- confirm the project config is loaded
- confirm `AGENTS.md` reaches the model context
- confirm `context7` is visible and can be exercised
- document a workaround for local session permission failures

## Alternatives Considered

### A. Keep `CLAUDE.md` as the single source of truth

Rejected: This keeps shared rules coupled to one tool's harness format and makes Codex support depend on a file that is not conceptually Codex-native.

### B. Duplicate shared rules into `CLAUDE.md` and `AGENTS.md`

Rejected: This directly recreates documentation drift. The exact problem this change is solving would remain.

### C. Fully adopt Codex-native agents/skills/hooks immediately

Rejected: Too large for the scope of issue #66. The immediate need was a stable shared-rule layer plus a usable Codex project harness, not a full second workflow framework.

## Decision

Adopt a two-layer structure:

### Layer 1: Shared rules

`AGENTS.md` becomes the canonical source for:
- project scale assumptions
- absolute prohibitions
- layer structure and terminology
- conversion patterns
- write DTO criteria
- baseline run/test/lint/migration commands
- documentation and rule drift management principles

### Layer 2: Tool-specific harnesses

- `CLAUDE.md`: Claude-only hooks, plugins, slash skills, `.claude/settings.json`, `.mcp.json`, and tool guidance
- `.mcp.json`: Claude-only MCP server definition
- `.codex/config.toml`: Codex project settings, MCP server definition, sandbox/approval defaults, web search policy, and project-doc fallback

Codex-native `.agents/skills`, `.codex/agents`, and Codex hooks are explicitly deferred.

## Rationale

| Decision | Reason |
|----------|--------|
| `AGENTS.md` as canonical shared rules | Keeps architecture rules tool-agnostic and reusable |
| Thin `CLAUDE.md` | Preserves the existing Claude workflow without forcing Codex to depend on Claude-specific operational details |
| `.codex/config.toml` for Codex harness | Gives Codex a committed, team-shared entrypoint for MCP and project behavior |
| Separate `.mcp.json` and `.codex/config.toml` roles | Avoids implying that Claude and Codex consume MCP config the same way |
| Explicit Codex verification steps | Makes support observable instead of aspirational |
| Documented `CODEX_HOME` trust bootstrap workaround | Matches real CLI behavior when `~/.codex/sessions` is not usable |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
