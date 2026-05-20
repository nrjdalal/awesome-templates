# 015. Rebrand to AI Agent Backend Platform

- Status: Accepted
- Date: 2026-04-03
- Related issue: #42

## Summary

To correct the branding to reflect the project's original scope — which included Agent/MCP development from the start — we rebranded from "FastAPI Blueprint" to "FastAPI Agent Blueprint."

## Background

- **Trigger**: Agent/MCP development was part of the project scope from the beginning, but the initial branding as "FastAPI Blueprint" did not reflect this. A Django comparison exposed the weak differentiation of the generic positioning, making it clear that the branding needed to match the actual project intent.
- **Decision type**: Experience-based correction — this was not a pivot to a new direction, but a correction of branding that had failed to reflect the original scope.

The project was originally positioned as "FastAPI Blueprint" — a generic production-ready FastAPI backend template focused on zero-boilerplate CRUD and DDD architecture. This positioning placed it in direct competition with Django's mature ecosystem, where a solo-maintained FastAPI template cannot win on breadth of built-in features (auth, admin, ORM, caching, rate limiting, etc.).

## Problem

1. **Weak differentiation**: "FastAPI Blueprint" reads as "yet another FastAPI template" among 50+ similar repos on GitHub
2. **Django comparison unfavorable**: 11 standard backend features checked — 4 unimplemented, and Django provides all of them built-in
3. **FastAPI justification unclear**: No WebSocket, SSE, or ML serving usage — the primary reasons to choose FastAPI over Django were not leveraged
4. **Template adoption barrier**: No clear value proposition that would make developers choose this over tiangolo/full-stack-fastapi-template (30k+ stars)

## Alternatives Considered

### A. Stay as generic "FastAPI Blueprint"
- Keep the current branding and compete in the general-purpose template space
- Disadvantage: Does not reflect the project's actual scope (Agent/MCP), weak differentiation against Django and existing templates (30k+ stars), FastAPI's async strengths not leveraged in the branding

### B. Correct branding to "FastAPI Agent Blueprint" (chosen)
- Align branding with the original project scope: AI Agent Backend Platform
- FastAPI's async strengths (concurrent LLM calls, SSE streaming, FastMCP on Starlette) become the differentiator
- No existing FastAPI template combines MCP + PydanticAI + pgvector + DDD auto-discovery
- Risk: Phase 1 features (FastMCP, PydanticAI, pgvector) must be implemented to validate the positioning

## Decision

Rebrand from **FastAPI Blueprint** to **FastAPI Agent Blueprint** — an AI Agent Backend Platform template.

### What changed
- Project name: `fastapi-blueprint` → `fastapi-agent-blueprint`
- Positioning: Generic CRUD template → AI Agent Backend Platform
- Key Features reordered: AI Agent Platform → Production-Ready Architecture → Developer Experience
- Tech Stack: Added "AI & Agent" category (FastMCP, PydanticAI, pgvector — planned)
- Roadmap: Restructured into Phase 1 (AI Foundation) → Phase 2 (Production) → Phase 3 (Ecosystem)
- All 14 files updated across README, metadata, internal docs, and configs

### What didn't change
- Core architecture (DDD layered, BaseRepository/BaseService generics, auto-discovery)
- Existing features (HTTP API, Taskiq worker, SQLAdmin, pre-commit enforcement)
- Claude Code skills system (14 skills)
- Logo (deferred to separate task)

## Rationale

### Why FastAPI is justified for the agent platform direction

| Workload | Why async matters | Django alternative |
|----------|-------------------|-------------------|
| LLM API calls | Concurrent I/O-bound requests | Possible but less natural |
| MCP server | FastMCP runs on Starlette natively | Awkward on Django |
| Streaming responses (SSE) | FastAPI handles natively | Requires Django Channels |
| Vector search (pgvector) | Async queries via asyncpg | Django ORM pgvector support is limited |
| PydanticAI | Pydantic-native structured outputs | Django Ninja possible but indirect |

### Why this differentiates from existing templates

No existing FastAPI template combines:
- MCP server interface (FastMCP)
- AI agent orchestration (PydanticAI)
- Vector search (pgvector)
- DDD architecture with auto-discovery
- 14 Claude Code AI development skills

### Dual-purpose strategy

1. **Open-source template** — for teams building AI-powered backends
2. **Production codebase** — will be forked for a production AI service

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Future Considerations

- Phase 1 implementation (FastMCP #18, PydanticAI #15, pgvector #11) must be completed to validate the new positioning
- If Phase 1 features are not implemented, the rebrand becomes aspirational branding without substance
- GitHub repo rename (`fastapi-blueprint` → `fastapi-agent-blueprint`) to be executed post-merge
