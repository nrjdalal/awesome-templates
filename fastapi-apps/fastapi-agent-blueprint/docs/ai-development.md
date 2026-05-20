# AI-Native Development Guide

> For a quick overview, see the [README](../README.md#ai-native-development).

## Structure

This repository uses a **shared rules + shared references + tool-specific harness** structure:

| File | Role |
|------|------|
| `AGENTS.md` | Canonical shared rules for all AI tools |
| `docs/ai/shared/` | Shared workflow references and checklists used by Claude and Codex |
| `CLAUDE.md` | Claude-specific hooks, plugins, slash skills, and workflow notes |
| `.mcp.json` | Claude-only MCP server configuration |
| `.codex/config.toml` | Codex CLI project settings, profiles, features, and MCP configuration |
| `.codex/hooks.json` | Codex command-hook configuration |
| `.agents/skills/` | Repo-local Codex workflow skills |

## Shared Rules First

All tools should follow `AGENTS.md` for:
- project scale assumptions
- absolute prohibitions
- layer terminology and conversion patterns
- DTO creation criteria
- baseline run/test/lint/migration commands
- documentation drift management principles

Use `docs/ai/shared/` for the deeper workflow references that are too detailed for root `AGENTS.md`, such as `project-dna.md`, planning checklists, review checklists, and test patterns. When running `/sync-guidelines` or `$sync-guidelines`, always close with `project-dna`, `AUTO-FIX`, `REVIEW`, and `Remaining` so manual review items are not silently skipped.

## Claude Code

### Plugin Setup (Required)

Install the pyright-lsp plugin for code intelligence (symbol navigation, references, diagnostics):

```bash
uv sync                              # installs pyright binary as dev dependency
claude plugin install pyright-lsp    # installs Claude Code plugin
```

> `enabledPlugins` in `.claude/settings.json` will prompt installation automatically on first run.

### MCP Server Setup (`.mcp.json`)

**context7** -- Up-to-date library documentation
```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

> `.mcp.json` is the Claude-side MCP entrypoint. The project works without MCP servers, but Claude skills expect this configuration.

## Codex CLI

Codex uses the committed project config in `.codex/config.toml`:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"
web_search = "disabled"

[features]
codex_hooks = true

[profiles.research]
web_search = "live"

[mcp_servers.context7]
url = "https://mcp.context7.com/mcp"
```

> Codex uses the remote Context7 MCP endpoint so documentation lookups are not blocked by the sandboxed network restrictions that apply to locally spawned stdio servers.

Codex's repository workflow layer is split across:
- `.codex/config.toml` for base config and profiles
- `.codex/hooks.json` plus `.codex/hooks/` for command hooks
- `.agents/skills/` for repo-local workflows such as `$onboard`, `$plan-feature`, `$review-pr`
- `docs/ai/shared/` for shared references that both Claude and Codex consume

Recommended verification flow:
1. Trust the project in Codex.
2. Run `codex mcp list` and `codex mcp get context7`.
3. Run `codex debug prompt-input -c 'project_doc_max_bytes=400' "healthcheck" | rg "Shared Collaboration Rules|AGENTS\\.md"` and confirm `AGENTS.md` is included in the prompt input.
4. Use `codex -p research` or `codex --search` only when live web search is actually required.
5. Treat Codex memories as personal/session optimization only, not as team-shared governance.

> `.codex/config.toml` is the Codex-side harness entrypoint. Web search is disabled by default; enable it explicitly only when you need live external information.
