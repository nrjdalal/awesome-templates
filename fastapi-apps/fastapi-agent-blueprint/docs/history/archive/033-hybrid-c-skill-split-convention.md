# 033. Hybrid C Skill Split Convention

- Status: Accepted
- Date: 2026-04-13
- Related issue: #66
- Related ADR: [020](020-aidd-skills-governance.md)(AIDD skills governance), [031](031-shared-rules-tool-harness.md)(shared rules and thin harness), [032](032-codex-native-workflow-assets.md)(Codex native assets)

## Summary

To maintain 14 workflow skills across both Claude Code and Codex CLI without drift or duplication, we adopted a three-file split convention (Hybrid C): a shared procedure in `docs/ai/shared/skills/`, plus thin tool-specific wrappers in `.claude/skills/` and `.agents/skills/`.

## Background

- **Trigger**: ADR 032 established `docs/ai/shared/` as the shared reference layer and `.agents/skills/` as the Codex skill directory. However, it did not specify how individual skill content should be divided between the shared layer and each tool's wrapper. The first migration attempt (`.agents/plugins/` dual-registration) failed due to structural mismatch between Claude's `SKILL.md` format and Codex's plugin format, leading to its removal in commit 461df2a.
- **Decision type**: Experience-based correction — the initial approach (copy or dual-register) proved impractical, leading to the current split convention through iterative refinement.

The 14 skills ranged from 30 to 310 lines each (total ~1,400 lines). Any approach that duplicated this content across two tool directories would create a maintenance burden proportional to the total skill line count.

## Problem

### 1. Skills contained both shared logic and tool-specific instructions

Each Claude skill mixed general workflow steps (grep patterns, output formats, checklist items) with Claude-specific behavior (SKILL.md frontmatter, `.claude/rules/` post-steps, tool-specific interaction flow). Sharing the entire file with Codex would leak Claude-specific instructions into Codex sessions.

### 2. Dual-registration approach failed

The `.agents/plugins/` directory was an initial attempt to register existing skill procedures under Codex's plugin system. However, Claude's `SKILL.md` frontmatter format (name, description, argument-hint) and Codex's skill metadata format are structurally different. Maintaining both registrations for the same content created confusion rather than parity. This approach was removed in commit 461df2a.

### 3. Full duplication does not scale

With 14 skills averaging 100 lines each, maintaining two independent copies (Claude + Codex) means ~2,800 lines that must stay synchronized. Any change to a shared grep pattern, output format, or checklist item would require identical edits in two locations — the exact drift problem ADR 031 was designed to prevent.

## Alternatives Considered

### A. Full duplication: Copy all skill content into both tool directories

Each tool gets an independent, complete copy of every skill.

Rejected: 2,800 lines of duplicated content. When a skill's checklist or grep pattern changes, both copies must be updated identically. This is the textbook drift scenario — manageable at 2 skills, unmanageable at 14+.

### B. Single shared file: Both tools reference `docs/ai/shared/skills/{name}.md` directly

No tool-specific wrappers. Both Claude and Codex read the shared file as their skill definition.

Rejected: Claude and Codex have different skill metadata formats (SKILL.md frontmatter vs. Codex skill frontmatter). They also need different post-steps: Claude updates `.claude/rules/` files; Codex does not. A single file cannot serve as both tools' native skill definition without either (a) containing tool-specific sections that confuse the other tool, or (b) being so generic that neither tool gets proper guidance.

### C. Hybrid C: Shared procedure + thin tool-specific wrappers (chosen)

Extract the detailed procedure into a shared file. Each tool keeps a thin wrapper that contains only tool-specific metadata and a reference to the shared procedure.

Chosen: Achieves single-source-of-truth for procedure logic while preserving each tool's native skill format and tool-specific post-steps.

## Decision

### File Structure

For each skill `{name}`:

```
docs/ai/shared/skills/{name}.md        # Shared: detailed procedure
.claude/skills/{name}/SKILL.md         # Claude: thin wrapper (5-20 lines)
.agents/skills/{name}/SKILL.md         # Codex: thin wrapper (5-10 lines)
```

### What the wrapper keeps

**Claude wrapper** (`.claude/skills/{name}/SKILL.md`):
- SKILL.md frontmatter (`name`, `description`, `argument-hint`, `compatibility`)
- Phase/Step overview (1-2 line summary per phase — provides full-flow visibility before reading external file)
- `Read docs/ai/shared/skills/{name}.md` instruction
- Claude-specific post-steps (e.g., update `.claude/rules/` files)
- Tool-specific interaction flow when it differs from Codex

**Codex wrapper** (`.agents/skills/{name}/SKILL.md`):
- Codex skill frontmatter
- Step 1: `Read AGENTS.md and docs/ai/shared/skills/{name}.md`
- Tool-specific post-steps (if any)

### What the shared procedure contains

**Shared procedure** (`docs/ai/shared/skills/{name}.md`):
- Detailed steps per phase (inspection targets, conditions, branching logic)
- Output format examples
- Checklists, file lists, grep patterns
- Cross-references to other `docs/ai/shared/` documents

### Synchronization rules

1. **Phase count consistency**: The number of phases/steps in the shared procedure must match the overview in each wrapper. Detected by `/sync-guidelines` Phase 5.
2. **No tool-specific instructions in shared procedures**: Shared files must not contain `.claude/rules/`, `.claude/skills/`, or `.agents/skills/` references as instructions. Exception: `sync-guidelines.md` references both paths because its purpose is cross-tool inspection.
3. **Both wrappers must reference the shared procedure**: Verified by grep during `/sync-guidelines`.

### Migration result

All 14 skills were migrated to this convention:
- Shared procedures: ~1,200 lines total (in `docs/ai/shared/skills/`)
- Claude wrappers: ~200 lines total overhead (frontmatter + overview + post-steps)
- Codex wrappers: ~100 lines total overhead
- Total: ~1,500 lines vs. ~2,800 lines if fully duplicated

## Rationale

| Decision | Reason |
|----------|--------|
| Three-file split over duplication | Single procedure source eliminates drift. Wrappers are thin enough that tool-specific divergence is minimal and reviewable at a glance |
| Wrappers keep Phase overview | The agent sees the full flow summary before reading the external file. Without this, the agent reads the shared procedure without context for how it fits the wrapper's expectations |
| Shared procedures in `docs/ai/shared/skills/` | Accessible to both tools via standard file reading. Not hidden inside either tool's config directory |
| Phase count enforcement via `/sync-guidelines` | Automated detection prevents silent drift between wrapper overview and shared procedure |
| Tool-specific paths banned from shared procedures | Prevents one tool's instructions from confusing the other. The sync-guidelines exception is intentional — its purpose is cross-tool inspection |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
