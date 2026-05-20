---
name: onboard
description: Interactive onboarding for contributors who are new to this repository or need a guided refresher on architecture, workflow, and AI collaboration assets.
metadata:
  short-description: Guided repository onboarding
---

# Onboard

## Default Flow Position
- **Outside** the normal Default Coding Flow — session-start orientation only
- Subsequent coding work after `/onboard` is treated as a fresh Default Flow run
- `[exploration]` / `[탐색]` token is appropriate for combining onboard with read-only investigation
- Recursion guard: do not invoke `/onboard` recursively, do not invoke `/plan-feature` from inside

## Procedure
1. Read `AGENTS.md` and `docs/ai/shared/skills/onboard.md` for the full onboarding flow.
2. Read `docs/ai/shared/project-dna.md`, `docs/ai/shared/onboarding-role-tracks.md`, and `README.md`.
3. Ask the user for experience level and preferred format if not already indicated.
4. Use `src/user/` as the reference domain and `src/_core/`, `src/_apps/` for shared infrastructure.
5. Cover in order: why this architecture exists, how layers work, prohibitions, conversion patterns, workflow tools, next steps.
6. Adapt depth using onboarding-role-tracks.md. Point to concrete files when context feels abstract.
7. Do not invent architecture rules. Use shared docs as the source of truth.
