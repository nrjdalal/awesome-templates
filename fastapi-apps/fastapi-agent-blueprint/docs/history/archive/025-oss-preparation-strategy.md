# 025. OSS Preparation and Internationalization Strategy

- Status: Accepted
- Date: 2026-03 ~ 2026-04
- Related issue: #24
- Related ADR: [015](015-rebrand-agent-platform.md)(Rebrand to AI Agent Backend Platform)

## Summary

To release the project as a genuine open-source blueprint (not just published code), we conducted a comprehensive internationalization effort — translating all documentation, ADRs, skills, hooks, memories, and code comments from Korean to English, and adding full OSS governance artifacts.

## Background

- **Trigger**: ADR 015 rebranded the project as "FastAPI Agent Blueprint" — an AI Agent Backend Platform. To achieve the rebranding goal of attracting international contributors and differentiating from other FastAPI templates, the project needed to be accessible to English-speaking developers. At the time, all documentation, skills, and in-code comments were in Korean.
- **Decision type**: Upfront design — a strategic decision to invest in internationalization before seeking contributors, not after receiving complaints.

The project had:
- 16 ADRs in Korean
- 14 skills with Korean instructions
- CLAUDE.md with Korean collaboration rules
- Code comments in Korean
- Serena memories in Korean
- Pre-commit hook scripts with Korean messages

## Problem

### 1. Language Barrier for Contributors

A non-Korean-speaking developer cloning the repository would find documentation, skills, and even code comments they cannot read — effectively excluding the global developer community.

### 2. Discoverability

GitHub search, Stack Overflow, and AI tools index English content. Korean-only documentation reduces the project's visibility in these channels.

### 3. Consistency

A mix of Korean and English within the same document or codebase creates cognitive overhead for all developers, regardless of language.

## Alternatives Considered

### A. Bilingual Documentation (Korean + English)

Maintain both Korean and English versions of all documentation.

Rejected: Double maintenance burden. Documentation drift between languages is inevitable. Two versions of each file creates confusion about which is authoritative.

### B. English README Only

Translate only the README and leave internal documentation in Korean.

Rejected: Contributors who get past the README immediately hit Korean skills, ADRs, and code comments. This approach attracts contributors but fails to retain them.

### C. Machine Translation On-Demand

Keep Korean originals and offer machine-translated versions.

Rejected: Machine translation of technical documentation produces inaccurate or confusing results, especially for architecture concepts. Translated documentation must be authored, not generated.

## Decision

A comprehensive English-first approach across 5 translation batches:

### 1. Foundation Documents (i18n: #24)
- `README.md` → English (Korean version preserved as `docs/README.ko.md`)
- `CONTRIBUTING.md` → English
- `CLAUDE.md` → English (except personal collaboration rules which remain Korean)

### 2. Architecture Decision Records
- All 16 ADRs translated to English
- Technical terms and code references verified for accuracy

### 3. Skills and References
- All 14 skills' `SKILL.md` files translated
- Reference documents in `references/` directories translated
- `project-dna.md` translated

### 4. Configuration and Hooks
- `.claude/settings.json` hook scripts → English messages
- Serena memories → English
- Code comments → English

### 5. OSS Governance Artifacts
New files added:
- `CODE_OF_CONDUCT.md` — Contributor Covenant
- `SECURITY.md` — Security vulnerability reporting process
- `LICENSE` — MIT License
- `.github/ISSUE_TEMPLATE/` — Bug report and feature request templates
- `.github/PULL_REQUEST_TEMPLATE.md` — PR template

### Korean Preservation
- `docs/README.ko.md` — Korean README preserved for Korean-speaking users
- Personal collaboration rules in user's `CLAUDE.md` remain Korean (user-specific, not project-public)

## Rationale

| Decision | Reason |
|----------|--------|
| English-first over bilingual | Single source of truth. No drift between translations. English is the lingua franca of open source |
| Korean README preserved | Respects the project's origin and Korean developer community. One file to maintain, not 40+ |
| All layers translated | Partial translation creates a "glass door" — contributors can see the project but can't work with it. Full translation enables genuine contribution |
| OSS governance artifacts | LICENSE, CODE_OF_CONDUCT, SECURITY.md signal maturity and professionalism. Contributors expect these in serious open-source projects |
| Issue/PR templates | Standardize contributor interactions. Reduce maintainer burden by guiding contributors to provide necessary context |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
