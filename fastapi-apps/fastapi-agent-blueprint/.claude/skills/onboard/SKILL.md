---
name: onboard
argument-hint: "(no arguments)"
description: |
  This skill should be used when the user asks to
  "project introduction", "getting started",
  "how does this project work", "I'm new to this project",
  or is a new team member needing orientation to the project.
---

# Interactive Onboarding for New Team Members

## Default Flow Position
- **Outside** the normal Default Coding Flow — session-start orientation only
- Subsequent coding work after `/onboard` is treated as a fresh Default Flow run
- `[exploration]` / `[탐색]` token is appropriate for combining onboard with read-only investigation
- Recursion guard: do not invoke `/onboard` recursively, do not invoke `/plan-feature` from inside

## Pre-check: Collect Project State

Execute the following to understand the current project state (do not output to the user):

1. Read `.claude/rules/project-overview.md` -- tech stack and app structure
2. Read `.claude/rules/project-status.md` -- confirm work in progress
3. Read `.claude/rules/architecture-conventions.md` -- current DO/DON'T rules
4. Glob `src/*/` to identify current domain list (excluding `_core`, `_apps`)
5. `git log --oneline -5` to check recent activity

## Procedure Overview
1. Welcome — assess experience level and preferred format (Phase 0)
2. Methodology — architecture evolution history via ADRs (Phase 1)
3. Project Overview — structure, domains, tech stack (Phase 2)
4. Architecture Rules — Absolute Prohibitions and terminology (Phase 3)
5. Data Flow — conversion patterns with live code walkthrough (Phase 4)
6. Development Workflow — Skills and CLI commands (Phase 5)
7. Personalized Next Steps (Phase 6)

Read `docs/ai/shared/skills/onboard.md` for the full onboarding flow, including
Q&A/Explore mode rules, topic maps, and experience-level adjustments.

## Claude-Specific: Phase 2 and Phase 5 Sources
- Phase 2 tech stack: read from `.claude/rules/project-overview.md`
- Phase 5 Skills list: read from `CLAUDE.md` Skills section
- Phase 5 CLI commands: read from `.claude/rules/commands.md`
- Phase 6 wrap-up: include `CLAUDE.md` as a key reference material
