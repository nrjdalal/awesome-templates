# 020. AIDD Methodology and Skills Governance System

- Status: Accepted
- Date: 2026-03
- Related ADR: [002](002-serena-adoption.md)(Serena MCP Server), [014](014-omc-vs-native-orchestration.md)(OMC vs Native Orchestration)

## Summary

To codify development workflows and maintain architecture consistency at scale, we adopted an AI-Driven Development (AIDD) methodology: Claude Code Skills serve as executable workflow templates, `project-dna.md` serves as the machine-readable architecture truth, and harness hooks enforce compliance — forming a three-layer governance system.

## Background

- **Trigger**: As the project grew to 14+ repeatable development tasks (domain scaffolding, API addition, PR creation, architecture review, etc.), inconsistencies emerged when different conversations with Claude Code produced different results for the same task type. A developer asking Claude to "add a new domain" could get varying directory structures, missing files, or incorrect naming conventions depending on the conversation context.
- **Decision type**: Upfront design — designing the development process as a system before scaling the team.

Traditional development teams rely on:
1. **Documentation** (README, wiki) — read by humans, ignored by AI
2. **Code review** — catches problems after they're created
3. **Linting/CI** — catches syntax and style issues, not architectural patterns

This project needed a mechanism that works for both human developers and AI assistants, catching architectural violations at creation time rather than review time.

## Problem

### 1. Inconsistent AI-Assisted Development

Claude Code conversations are stateless across sessions. Without persistent, structured instructions, each session starts with zero knowledge of project conventions. The same question produces different answers depending on which files the AI reads.

### 2. Documentation-Code Drift

Traditional documentation drifts from code over time. Architecture rules written in a wiki become outdated as the code evolves. There is no mechanism to detect or prevent this drift.

### 3. Knowledge Transfer Bottleneck

When a new team member (human or AI session) joins, they need to learn: project structure, naming conventions, layer rules, conversion patterns, prohibited patterns, and workflow procedures. Without structured onboarding, this knowledge is acquired through trial and error.

## Alternatives Considered

### A. Documentation Only (README + Wiki)

Rely on comprehensive documentation for all conventions.

Rejected: Documentation is passive — it requires the reader to find, read, and follow it. AI assistants do not proactively read wiki pages. Documentation drift is inevitable without enforcement mechanisms.

### B. Custom CLI Tool

Build a project-specific CLI that generates domains, APIs, etc.

Rejected: Requires maintaining a separate tool codebase. Cannot adapt to novel situations (e.g., "add this endpoint but with special auth logic"). Rigid templates cannot handle the flexibility needed for real development tasks.

### C. Code Review Only

Rely on human code review to catch convention violations.

Rejected: Reactive, not proactive. Violations are caught after the developer has invested time implementing the wrong approach. Does not scale when multiple developers work in parallel.

## Decision

A three-layer governance system:

### Layer 1: Skills (Executable Workflow Templates)

13 skills in `.claude/skills/` that codify repeatable development workflows:

| Category | Skills |
|----------|--------|
| Scaffolding | `/new-domain`, `/add-api`, `/add-worker-task`, `/add-cross-domain` |
| Quality | `/review-architecture`, `/security-review`, `/test-domain` |
| Workflow | `/plan-feature`, `/fix-bug`, `/review-pr` |
| Governance | `/sync-guidelines`, `/onboard`, `/migrate-domain` |

Each skill is a `SKILL.md` file with:
- Structured steps that the AI follows sequentially
- References to `project-dna.md` for architecture patterns
- Guard clauses that prevent common mistakes

### Layer 2: project-dna.md (Architecture Truth)

A single file (`.claude/skills/_shared/project-dna.md`) that contains:
- Canonical directory structure patterns
- Layer conversion patterns (Write/Read/Worker directions)
- Naming conventions
- Prohibited patterns with rationale

This file is the source of truth that all skills reference. When architecture evolves, updating this single file propagates changes to all skills.

### Layer 3: CLAUDE.md + Hooks (Enforcement)

- `CLAUDE.md`: Project-level rules loaded into every AI session (absolute prohibitions, layer architecture, terminology, conversion patterns)
- `settings.json` hooks: `PreToolUse` and `Stop` hooks that run shell scripts for security checks and guideline sync reminders

### Feedback Loop: /sync-guidelines

The `/sync-guidelines` skill detects drift between code, documentation, and skills by:
1. Reading the reference domain's current code
2. Comparing against project-dna.md patterns
3. Checking skill references for consistency
4. Reporting and fixing discrepancies

## Rationale

| Decision | Reason |
|----------|--------|
| Skills over custom CLI | Skills are flexible natural-language instructions that handle edge cases. CLI tools are rigid templates |
| project-dna.md as single source | One file to update when architecture evolves. Skills reference it, so changes propagate automatically |
| CLAUDE.md for absolute rules | Loaded into every conversation context — AI cannot miss these rules |
| Hooks for enforcement | Pre-tool security checks run before every edit/write/bash — catch violations at creation time, not review time |
| /sync-guidelines feedback loop | Prevents documentation-code drift by detecting and fixing discrepancies programmatically |
| ADR as separate governance layer | Skills handle "how", ADRs handle "why". Skills tell the AI what to do; ADRs tell the reader why the project is structured this way |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Post-decision Update (2026-04-13)

The governance system evolved from Claude-only to multi-tool (Claude Code + Codex CLI):

- `project-dna.md` moved: `.claude/skills/_shared/` → `docs/ai/shared/` ([ADR 032](032-codex-native-workflow-assets.md))
- Skills split into shared procedures + tool-specific wrappers ([ADR 033](033-hybrid-c-skill-split-convention.md))
- Skill count: 13 → 14 (`/onboard` added)
- Layer 2 path: `project-dna.md` + shared checklists now in `docs/ai/shared/`
- Layer 3 enforcement: Claude hooks + Codex hooks (both detect same foundation file changes)
- Canonical shared rules extracted to `AGENTS.md` ([ADR 031](031-shared-rules-tool-harness.md))

The three-layer model (Skills → Architecture Truth → Enforcement) remains intact.
What changed is that each layer now serves two tools instead of one.
See ADR [031](031-shared-rules-tool-harness.md), [032](032-codex-native-workflow-assets.md), [033](033-hybrid-c-skill-split-convention.md) for the detailed evolution.
