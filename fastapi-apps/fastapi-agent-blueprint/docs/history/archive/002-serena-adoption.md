# 002. Serena MCP Server Adoption and Claude Code Parallel Strategy

- Status: Superseded by 030
- Date: 2026-03-18
- Related issue: #57

## Summary

To overcome Claude Code's text-based search limitations for structural code navigation and enable team-shared knowledge, we adopted Serena MCP Server in parallel with Claude Code — each tool covering the other's gaps.

## Background

- **Trigger**: As the project grew into a DDD-based modular layered architecture, Protocol-based dependencies across domains, BaseRepository inheritance chains, and refactoring impact analysis required AST-level understanding that text-based Grep/Glob could not provide. Additionally, Claude Code's auto-memory was machine-local, making team knowledge sharing impossible.
- **Decision type**: Upfront design — addressed proactively as the architecture grew, before navigation failures caused costly mistakes.

As the project grew into a DDD-based modular layered architecture, the accuracy of AI coding tools' code navigation became critical.
Text-based search using Claude Code's Grep/Glob alone made it difficult to structurally understand class hierarchies, method signatures, and reference relationships.

The limitations became particularly apparent in the following tasks:
- Tracking Protocol-based dependencies across domains (which classes implement which Protocols)
- Checking BaseRepository's Generic type parameters (tracing the inheritance chain)
- Analyzing impact scope during refactoring (find_referencing_symbols)

## Problem

### Limitations of Claude Code Text Search

```
Grep: "class UserRepository" -> Text matching (file:line number)
  - Does not know inheritance structure
  - Does not know what methods exist
  - Does not know who references this class

Serena: find_symbol "UserRepository" -> AST-level understanding
  - Confirms BaseRepository[BaseModel, UserDTO, BaseModel] inheritance
  - Structurally identifies method list + signatures
  - Tracks all references via find_referencing_symbols
```

### Lack of Team Knowledge Sharing

Claude Code auto-memory is stored locally on the machine at `~/.claude/projects/`, making team sharing impossible.
There was no means to store team-shared knowledge such as refactoring progress status and architecture conventions.

## Alternatives Considered

### A. Claude Code Standalone (Grep/Glob + auto-memory)
- Most tasks achievable with text search
- No symbol-level navigation -> weak for refactoring and impact analysis
- Memory is machine-local -> team sharing impossible

### B. Serena Standalone
- Provides LSP-based symbol navigation + memory system
- No skill system or hook system -> unable to build automated workflows
- File-level editing tools more limited than Claude Code

### C. Claude Code + Serena Parallel Use (chosen)
- Claude Code: skill system, hook system, Grep/Glob text search, auto-memory
- Serena: LSP symbol navigation, team-shared memory (.serena/ git commit)
- Combines the strengths of each tool

## Decision

**Adopt Claude Code + Serena Parallel Use**

### 4-Layer Memory Architecture

| Layer | Storage | Sharing | Role | Update Owner |
|-------|---------|---------|------|-------------|
| CLAUDE.md | Project root | git (team) | Immutable team rules | Manual (human) |
| project-dna.md | .claude/skills/_shared/ | git (team) | Pattern references extracted from code | /sync-guidelines (auto) |
| Serena memories | .serena/memories/ | git (team) | Dynamic project state + symbol navigation context | /sync-guidelines + manual |
| Claude auto-memory | ~/.claude/projects/ | Local (personal) | Session feedback, personal learning | Claude auto |

### Tool Role Separation

```
Code navigation:
  1st priority — Serena symbol tools (get_symbols_overview, find_symbol, find_referencing_symbols)
  2nd priority — Grep/Glob (text pattern search, config files)
  3rd priority — Read (non-code files, when symbol navigation is insufficient)

Code editing:
  Full symbol replacement — Serena replace_symbol_body
  Partial modification — Claude Code Edit
  New code insertion — Serena insert_before/after_symbol or Edit

Automation:
  Skill system — Claude Code (.claude/skills/)
  Hook system — Claude Code (.claude/settings.local.json)
  Security checks — Claude Code PreToolUse hooks

Memory:
  Team-shared dynamic state — Serena (.serena/memories/, git commit)
  Personal feedback — Claude Code auto-memory (machine-local)
```

### Serena Memory Composition (4 entries)

| Memory | Role | Unique Information |
|--------|------|--------------------|
| architecture_conventions | Context priming before symbol navigation | Data flow diagrams, object roles (DTO/Model/Schema locations) |
| refactoring_status | Track ongoing architecture changes | Per-phase completion status, violation check results |
| project_overview | Project-level context | Purpose, app entry points, dependency directions |
| suggested_commands | Developer CLI reference | Run/test/lint/migration commands |

### Automatic Synchronization Mechanism

```
On code changes:
  Stop hook -> detect changed files via git diff -> classify as Foundation/Structure -> recommend /sync-guidelines
  /sync-guidelines -> Regenerates project-dna.md + Updates Serena memories
```

## Rationale

| Criteria | Claude Code Standalone | Serena Standalone | Claude Code + Serena |
|----------|----------------------|-------------------|---------------------|
| Symbol-level navigation | Impossible (Grep only) | Strong (LSP) | Strong |
| Skill/hook automation | Strong | None | Strong |
| Team-shared memory | Impossible (local only) | Possible (.serena/ git) | Possible |
| Personal learning memory | Possible | Limited | Possible |
| Code editing tools | Strong (Edit/Write) | Available (symbol-based) | Complementary |

1. The two tools operate under **different paradigms**, so they complement rather than conflict
2. Serena's core value is not memory but **LSP-based symbol navigation** — a capability absent from Claude Code
3. Committing `.serena/` to git makes it the **only team-shareable dynamic knowledge store**
4. Clear role separation maximizes each tool's strengths without duplication

### Evolution Direction for 10+ Domain Scaling

- Add `domain_dependencies` memory (Protocol dependency map across domains)
- Add `active_work` memory (work status tracking for 5+ team members)
- Keep total memories at 10 or fewer (tool call cost management)

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

### Cases Where Serena Would Become Unnecessary
- When Claude Code natively supports LSP-based symbol navigation
- When Claude Code auto-memory supports team sharing
- When the project shrinks to a single domain where symbol tracking is unnecessary
