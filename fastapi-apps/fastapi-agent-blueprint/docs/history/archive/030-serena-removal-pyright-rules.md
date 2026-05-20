# 030. Serena MCP Removal: Migration to pyright-lsp Plugin and .claude/rules/

- Status: Accepted
- Date: 2026-04-11
- Related issue: #63
- Supersedes: [002](002-serena-adoption.md)

## Summary

To eliminate a redundant MCP server dependency, we removed Serena and replaced its two core functions: LSP code intelligence (now provided by Claude Code's native pyright-lsp plugin) and team-shared memory (now provided by `.claude/rules/` directory committed to git).

## Background

- **Trigger**: Claude Code now ships with the official pyright-lsp plugin (released December 2025), providing native LSP-based symbol navigation (go-to-definition, find-references, hover, diagnostics). This eliminates Serena's primary value proposition identified in ADR 002. Additionally, Claude Code's `.claude/rules/` directory provides git-committed, auto-loaded context files — replacing the Serena memory system without requiring MCP tool calls.
- **Decision type**: Experience-based correction — ADR 002 explicitly predicted this migration under "Cases Where Serena Would Become Unnecessary": *"When Claude Code natively supports LSP-based symbol navigation."*

## Problem

### 1. Serena's high-value features were not being used

A full audit of all 14 custom skills revealed that Serena's differentiating capabilities — `replace_symbol_body`, `insert_before/after_symbol`, `find_referencing_symbols`, `safe_delete_symbol` — were **never directly called** by any skill. Actual usage was limited to `find_symbol` (replaceable by Grep) and `read_memory` (replaceable by file Read).

### 2. Memories were static, not dynamic

The four Serena memory files (217 lines total) contained static reference information — architecture conventions, project overview, CLI commands, and project status. None required the "dynamic learning during a session" capability that justifies a memory system. They were essentially well-structured markdown documents updated only during `/sync-guidelines` runs.

### 3. MCP overhead for simple file reads

Reading project context required explicit MCP tool calls (`read_memory`), while `.claude/rules/` files are auto-loaded at session start with zero tool call overhead. The MCP layer added latency and token cost for what was fundamentally a file-read operation.

### 4. Redundant LSP capabilities

With pyright-lsp providing native symbol navigation, Serena's LSP-based tools became redundant. Running two LSP servers (pyright-lsp and Serena's internal Pyright) against the same codebase wastes resources and risks conflicting diagnostics.

## Alternatives Considered

### A. Keep Serena alongside pyright-lsp

Both provide LSP capabilities, leading to redundant symbol navigation tools in the context window. Memory reads still require MCP calls. Ongoing maintenance of `.serena/` configuration and Serena-specific references across 9 skills.

### B. Remove Serena with no memory replacement

Loses team-shared project context. Each Claude session starts without architecture conventions, project status, or command references. Skills lose their pre-check context that improves output quality.

### C. Remove Serena, migrate memories to `.claude/rules/` (chosen)

pyright-lsp handles code intelligence natively. `.claude/rules/` files auto-load at session start, are git-committed for team sharing, and support path-scoping for token efficiency as domains scale. PostToolUse hook replaces implicit format-after-edit behavior. All 9 affected skills are updated to use Grep/Read + `.claude/rules/` paths.

## Decision

**Remove Serena MCP server entirely. Replace with three native mechanisms:**

### 1. Code intelligence: pyright-lsp plugin

| Capability | Before (Serena) | After (pyright-lsp / native) |
|---|---|---|
| Symbol overview | `get_symbols_overview` | `documentSymbol` (automatic) |
| Find symbol | `find_symbol` | `goToDefinition` + Grep |
| Find references | `find_referencing_symbols` | `findReferences` + Grep |
| Replace symbol | `replace_symbol_body` | Claude Code `Edit` |
| Insert code | `insert_before/after_symbol` | Claude Code `Edit` |
| Diagnostics | Not available | `getDiagnostics` (automatic) |

### 2. Team-shared knowledge: `.claude/rules/`

| Serena Memory | .claude/rules/ File | Auto-loaded | Path-scopable |
|---|---|---|---|
| `architecture_conventions` | `architecture-conventions.md` | Yes | Yes |
| `project_overview` | `project-overview.md` | Yes | Yes |
| `project_status` | `project-status.md` | Yes | Yes |
| `suggested_commands` | `commands.md` | Yes | Yes |

### 3. Code formatting: PostToolUse hook

A `post-tool-format.sh` hook runs `ruff format` + `ruff check --fix` automatically after every Edit/Write operation on `.py` files, replacing the manual formatting step.

### Skill migration

All 9 skills with Serena references were updated:
- `find_symbol` references → Grep/Read
- `read_memory` references → Read `.claude/rules/*.md`
- `write_memory` references → Edit `.claude/rules/*.md`
- `get_symbols_overview` references → Glob/Read

## Rationale

1. **ADR 002 predicted this**: The "Cases Where Serena Would Become Unnecessary" section listed exactly this scenario — native LSP support in Claude Code
2. **Zero actual loss**: No skill used Serena's differentiating edit tools; all actual usage patterns have direct Claude Code equivalents
3. **Improved DX**: `.claude/rules/` auto-loads without tool calls, reducing both latency and token usage
4. **Simpler onboarding**: One fewer external dependency (no `uvx` + `git+oraios/serena` setup)
5. **Future-ready**: `.claude/rules/` supports path-scoped rules for 10+ domain scaling, which Serena memories cannot

### Trade-offs Accepted

- **Loss of `rename_symbol`**: Serena provided workspace-wide symbol renaming via LSP. This must now be done via manual Grep + Edit, or via pyright-lsp if it adds rename support. Acceptable because this project's skills never used rename_symbol.
- **Loss of `safe_delete_symbol`**: Serena could verify no references before deleting. Now requires manual Grep verification. Acceptable for the same reason.
- **No automatic token-efficient symbol reading**: Serena's `find_symbol(include_body=True)` read only the requested symbol body. Grep/Read may read more content. Mitigated by Claude Code's 1M context window and pyright-lsp's `documentSymbol` for navigation.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
