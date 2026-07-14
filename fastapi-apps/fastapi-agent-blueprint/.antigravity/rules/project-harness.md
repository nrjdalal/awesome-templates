# Antigravity Project Harness

This plugin is a thin Antigravity 2.0 adapter for the FastAPI Agent
Blueprint harness.

Shared rules are canonical in `AGENTS.md`. Do not copy architecture,
workflow, language-policy, or governor rules into Antigravity-specific
files. Antigravity hooks and settings must import or invoke shared assets
from `.agents/shared/` whenever policy decisions are needed.

Use `.agents/skills/*/SKILL.md` for project workflow skills. Antigravity
and Gemini CLI may discover those workspace skills directly; this plugin
exists to wire hooks, rules, MCP, and permission templates without changing
the shared skill source of truth.

Runtime state belongs under `.antigravity/state/`, which is gitignored.
Committed Antigravity files must never contain credentials or user-local
machine paths.
