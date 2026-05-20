# 032. Codex Native Workflow Assets After the Thin Harness Phase

- Status: Accepted
- Date: 2026-04-13
- Related issue: #66
- Related ADR: [020](020-aidd-skills-governance.md)(AIDD skills governance), [021](021-architecture-governance-hooks-ci.md)(hooks and CI enforcement), [031](031-shared-rules-tool-harness.md)(shared rules and thin harness split)

## Summary

After completing the thin Codex harness from ADR 031, we now adopt Codex-native workflow assets: repo-local skills, command hooks, and shared workflow references that both Claude and Codex can consume.

## Background

- **Trigger**: ADR 031 intentionally stopped at `AGENTS.md` plus `.codex/config.toml` because issue #66 only required a usable Codex baseline. That made Codex functional, but still much thinner than the mature Claude workflow.
- **Decision type**: Experience-based extension — once the shared rule layer proved stable, the next bottleneck was workflow parity and context management rather than raw tool availability.

The user problem was not "Can Codex open the repo?" but "Can Codex work with the same confidence, guardrails, and repeatability as Claude?"

## Problem

### 1. Codex lacked native workflow assets

The repository had a mature Claude layer with skills and hooks, while Codex only had a base config and MCP definition. This created an uneven collaboration experience.

### 2. Shared workflow references lived inside Claude-only paths

Important workflow knowledge such as `project-dna.md` and several checklists lived under `.claude/skills/`, which made Codex parity awkward and encouraged duplicated copies.

### 3. Root-context pressure would increase over time

Adding more rules to `AGENTS.md` alone would eventually create context pressure. Codex supports hierarchical project docs, repo-local skills, profiles, and memories, so the architecture needed to use those native layers intentionally.

## Alternatives Considered

### A. Keep Codex as a thin harness only

Rejected: adequate for minimum support, inadequate for day-to-day parity with Claude.

### B. Copy Claude assets directly into Codex-specific folders

Rejected: direct duplication would recreate the exact drift problem ADR 031 was trying to avoid.

### C. Move everything into Codex-native assets and stop using `AGENTS.md`

Rejected: `AGENTS.md` remains the best shared canonical rule source across tools. Codex-native assets should extend it, not replace it.

## Decision

Adopt a layered Codex operating model:

### Layer 1: Shared canonical governance

- `AGENTS.md` remains the canonical shared rules source.
- Tool-agnostic workflow references move to `docs/ai/shared/`.

### Layer 2: Codex-native workflow assets

- `.agents/skills/` provides repo-local Codex workflows with names aligned to Claude skills.
- `.codex/hooks.json` plus `.codex/hooks/` provides command-focused Codex hooks.
- `.codex/config.toml` remains the Codex base config and now adds a dedicated `research` profile for live web search.

### Layer 3: Context management rules

- Keep root `AGENTS.md` short and stable.
- Use `AGENTS.override.md` for subtree-specific instructions when needed.
- Prefer named skills and shared references over expanding root instructions.
- Treat Codex memories as personal/session optimization, not team governance.

## Rationale

| Decision | Reason |
|----------|--------|
| Keep `AGENTS.md` canonical | Preserves one shared rule source across tools |
| Extract shared references to `docs/ai/shared/` | Lets Claude and Codex read the same workflow knowledge |
| Add repo-local Codex skills | Restores repeatable workflows without bloating root instructions |
| Add Codex hooks | Gives Codex command-time enforcement and reminders similar in outcome to Claude hooks |
| Use a `research` profile for web search | Keeps default sessions repo-first while still supporting deliberate live research |
| Keep memories non-canonical | Avoids hidden, user-local rule drift |

## Consequences

- Codex now has a first-class repository workflow layer instead of only a bootstrap config.
- Claude and Codex share the same governance references, which reduces drift.
- Verification expands from MCP and prompt-doc checks to skills and hooks.
- Future workflow additions should update `docs/ai/shared/` first, then the Claude/Codex entrypoints that reference it.

### Self-check
- [x] Does this decision extend ADR 031 instead of contradicting it?
- [x] Does this keep one canonical shared-rule source?
- [x] Does this reduce context pressure rather than move it around?
- [x] Does this explain why Codex-native assets were adopted later, not initially?
