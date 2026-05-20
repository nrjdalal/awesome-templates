# Absolute Prohibitions

> Source: `AGENTS.md` — this file projects safety-critical rules into Claude's auto-load path.
> When updating prohibitions, edit `AGENTS.md` first, then sync this file via `/sync-guidelines`.

- No Infrastructure imports from the Domain layer
- No exposing Model objects outside the Repository
- No separate Mapper classes (inline conversion is sufficient)
- No Entity pattern — unified to DTO (background: [ADR 004](../../docs/history/004-dto-entity-responsibility.md))
- No modifying or deleting shared rule sources without cross-reference verification
  - Shared rule sources: `AGENTS.md`, `docs/ai/shared/`, `.claude/`, `.codex/`, and `.agents/`
  - Claude verification: `rg -n "KEYWORD" .claude/skills/` to check skill dependencies before any change

Note: Domain → Interface **schema** imports (Request/Response types) are permitted.
When fields match, Request is passed directly to Service — creating a separate DTO is prohibited per ADR 004.
