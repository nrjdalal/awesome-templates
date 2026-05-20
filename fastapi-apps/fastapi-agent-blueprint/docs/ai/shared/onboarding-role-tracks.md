# Onboarding Guide by Experience Level

## 1. Experience Level Definitions

| Level | Target Audience | Onboarding Approach |
|-------|----------------|---------------------|
| Beginner | Python basics, first time with FastAPI | Includes concept explanations, detailed walkthrough of all Phases |
| Intermediate | Has FastAPI experience, first time with DDD/layered architecture | Standard track |
| Advanced | Has DDD + DI Container experience | Shortened track, highlight only project-specific aspects |

### Format Comparison

| Aspect | Guided | Q&A | Explore |
|--------|--------|-----|---------|
| Flow | Phase-by-Phase sequential | Phase-by-Phase, topic map per Phase | No Phase boundaries |
| User action | Listen, ask questions | Pick topics from map | Point at code freely |
| Entry point | Phase 1 starts automatically | Phase 1 topic map | Project directory tree |
| Critical topic check | Built into each Phase | On 'next' per Phase | On 'done' (all at once) |
| Best for | First-timers wanting full context | Users who know what they want to learn | Experienced devs who prefer reading code |

## 2. Phase Depth by Level

### Phase 1: Methodology and Evolution History

| Item | Beginner | Intermediate | Advanced |
|------|----------|-------------|----------|
| DDD concepts | Detailed with analogies | Brief overview | Skip |
| Layered architecture basics | Explain why layers are separated | Brief overview | Skip |
| Evolution history (4 ADRs) | Detailed delivery | Detailed delivery | Key points only |
| AIDD methodology | Detailed explanation | Detailed explanation | Skills list only |

### Phase 2: Project Overview

| Item | Beginner | Intermediate | Advanced |
|------|----------|-------------|----------|
| Project scale/purpose | Explain | Explain | Summary |
| Directory structure | Detailed | Detailed | List only |
| Tech stack | Explain role of each technology (incl. DynamoDB as optional NoSQL) | List (incl. DynamoDB) | List |
| Additional concepts | Explain DI Container, Protocol, Pydantic | - | - |

### Phase 3: Architecture Rules

| Item | Beginner | Intermediate | Advanced |
|------|----------|-------------|----------|
| 5 Absolute Prohibitions | Reason + story for each | Reason + story | List only |
| Terminology definitions | Detailed explanation | Explanation | Skip |

### Phase 4: Data Flow

| Item | Beginner | Intermediate | Advanced |
|------|----------|-------------|----------|
| Conversion Patterns | Diagram + code walkthrough | Diagram + code walkthrough | Pattern table only |
| src/user/ live code | Full path tracing | Full path tracing | Skip |

### Phase 5: Skills Workflow

| Item | Beginner | Intermediate | Advanced |
|------|----------|-------------|----------|
| Skills guide | Explain role of each Skill | Guide in workflow order | List only |
| Execution commands | Detailed | Detailed | Skip |

### Advanced Only: Project-Specific Highlights
Advanced users are already familiar with DDD/DI, so deliver only what differentiates this project:
- No Entity pattern -> unified with DTOs (background: ADR 004)
- Mapper class prohibited -> inline conversion (`model_dump()`, `model_validate()`)
- UseCase is optional (not mandatory, add only when needed)
- Automatic domain discovery (no Container/Bootstrap modification needed)

## 3. Recommended Skills (Workflow Order)

1. `/plan-feature` -> Feature design
2. `/new-domain` -> Domain creation
3. `/add-api` -> API addition
4. `/add-worker-task` -> Async tasks
5. `/add-admin-page` -> Admin page for existing domain
6. `/add-cross-domain` -> Cross-domain connections
7. `/review-architecture` -> Architecture verification
8. `/security-review` -> Security audit
9. `/test-domain` -> Test generation/execution
10. `/fix-bug` -> Bug fixes
11. `/sync-guidelines` -> Guideline synchronization
12. `/migrate-domain` -> DB migration
13. `/review-pr` -> PR review

## 4. Recommended Next Steps (by Experience Level)

### Beginner
1. Explore the entire directory structure of `src/user/` domain to understand the reference implementation
2. Create a practice domain with `/new-domain practice` to internalize the structure
3. Practice adding an API with `/add-api "add GET /items to practice"`

### Intermediate
1. Familiarize yourself with the Absolute Prohibitions in AGENTS.md
2. Once assigned a domain, start with `/plan-feature` for design
3. Run `/review-architecture {domain}` before your first PR

### Advanced
1. Skim the ADR list in `docs/history/` to understand the context of structural decisions
2. Review `docs/ai/shared/project-dna.md` section 5 (DI), section 6 (Conversion Patterns)
3. Ready to start working immediately — begin with `/plan-feature`
