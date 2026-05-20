---
name: review-pr
argument-hint: "PR number, URL, or omit to detect current branch"
description: |
  Review a pull request against project architecture rules.
  Use when the user asks to "review PR", "check PR", "PR review",
  or wants architecture-aware review of a pull request before merge.
---

# Pull Request Architecture Review

Target: $ARGUMENTS (PR number, GitHub URL, or empty for current branch)

## Default Flow Position
- Step: **`completion gate`** (final review at end of work)
- Routes after: `/sync-guidelines` if drift detected
- Recursion guard: do not invoke `/review-pr` recursively, do not invoke `/plan-feature` from inside

## Procedure Overview
1. Resolve PR and load shared rule sources (Phase 0)
2. Review changed files against shared architecture and security rules (Phase 1)
3. Determine `Drift Candidates` and whether `Sync Required` is `true` or `false` (Phase 2)
4. Report using the shared review contract (Phase 3)
5. Post to GitHub only after user confirmation (Phase 4)

Read `docs/ai/shared/skills/review-pr.md` for detailed steps and output format.
For cross-tool review prompts, use that shared procedure's
`Cross-Tool Review Prompt Template` section; do not duplicate the template here.

## Claude-Specific: Rule Sources
You may cross-check the final wording against `.claude/rules/architecture-conventions.md`,
but do not create findings that are not already backed by the shared rule
sources loaded in `docs/ai/shared/skills/review-pr.md`.
