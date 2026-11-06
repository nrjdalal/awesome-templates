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
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `onboard` routing.
Recursion guard: Do not invoke this skill recursively or invoke plan-feature from inside it.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/onboard.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Welcome — assess experience level and preferred format (Phase 0)
2. Methodology — architecture evolution history via ADRs (Phase 1)
3. Project Overview — structure, domains, tech stack (Phase 2)
4. Architecture Rules — Absolute Prohibitions and terminology (Phase 3)
5. Data Flow — conversion patterns with live code walkthrough (Phase 4)
6. Development Workflow — Skills and CLI commands (Phase 5)
7. Personalized Next Steps (Phase 6)

## Tool Sources
Use the native skill index plus user-invoked-only `/sync-guidelines`, `/migrate-domain`, `/trace`, and `/why` entries in `CLAUDE.md`. Architecture and overview rules are scoped; use their visible context only when their paths apply, and consult the relevant rule if needed and not already visible. Consult `docs/ai/shared/commands.md` for CLI guidance on demand. Include `CLAUDE.md` among Phase 6 references; the shared procedure defines topics and outputs.
