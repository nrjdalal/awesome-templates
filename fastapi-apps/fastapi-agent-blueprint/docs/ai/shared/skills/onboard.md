# Interactive Onboarding — Detailed Procedure

## Default Flow Position

This skill is **outside** the normal Default Coding Flow. It belongs to **session-start** orientation only and is invoked explicitly by a user (typically a new contributor) at the beginning of a session, not as a step inside a coding task.

Implications:
- `/onboard` does not become an automatic phase of Default Flow.
- A coding-flow session that starts with `/onboard` should treat the subsequent coding work as a fresh Default Flow run (the onboard session is its own context).
- The `[exploration]` / `[탐색]` exception token is appropriate when a new contributor wants to combine onboarding with read-only investigation.

Recursion guard: do **not** invoke `/onboard` recursively, and do not invoke `/plan-feature` from inside this skill.

> **Design Principle**: This skill does not have its own architecture documentation.
> All information is read at runtime from existing sources (README.md, ADR, AGENTS.md, `docs/ai/shared/project-dna.md`, harness guides, rules files, `docs/ai/shared/`, `src/user/` code).
> When the structure changes, the source is updated, and onboarding automatically reflects the latest content.

## Phase 0: Welcome — Assess Experience Level and Format

### Step 1: Experience Level

Ask the user about their experience level:

> Welcome! Before we start the onboarding, one quick question.
>
> **How much experience do you have with Python/FastAPI?**
> - **(1) Beginner** -- Python basics, first time with FastAPI
> - **(2) Intermediate** -- FastAPI experience, first time with DDD/layered architecture
> - **(3) Advanced** -- DDD + DI Container experience, just need to understand this project's structure

### Step 2: Onboarding Format

After receiving the experience level, ask about the preferred format:

> **How would you like to proceed?**
> - **(A) Guided** -- Structured walkthrough, Phase by Phase
> - **(B) Q&A** -- Topic map provided, you explore by asking questions
> - **(C) Explore** -- Point at any code/file/directory and ask freely, uncovered essentials flagged at the end

After receiving both responses, refer to the level-specific adjustment criteria in `docs/ai/shared/onboarding-role-tracks.md`
to adjust the depth of each Phase. Track overview:

```
=== Onboarding Track ===
Experience: {selected level}
Format: {Guided | Q&A | Explore}
Phase: 1(Methodology) -> 2(Project Overview) -> 3(Architecture Rules) -> 4(Data Flow) -> 5(Skills) -> 6(Next Steps)
Depth Adjustment: {adjustment summary based on level}
```

Proceed to the next Phase after user confirmation.

### Q&A Mode Rules

When the user selects **Q&A** format, apply the following rules to **all Phases (1-6)**:

1. **Topic Map**: At the start of each Phase, present a brief overview with a numbered list of explorable topics.
   Each topic should include a one-line description so the user can judge what to ask about.
2. **User-Driven**: Wait for the user's questions. Answer by referencing the same sources as Guided mode
   (ADR, code, rules files, `docs/ai/shared/`, AGENTS.md, harness docs, etc.).
3. **Coverage Tracking**: Internally track which topics have been addressed by the user's questions.
4. **Gap Check**: When the user says 'next' (or equivalent), check for any **critical uncovered topics**.
   If found, briefly mention them: "Before moving on, these are worth knowing: ..." (1-2 sentences each).
   If all critical topics are covered, move on immediately.
5. **Depth Adjustment**: Experience-level depth adjustments from `docs/ai/shared/onboarding-role-tracks.md` still apply.
   For example, Advanced + Q&A skips DDD basics but still offers project-specific ADR topics to ask about.

### Explore Mode Rules

When the user selects **Explore** format, Phase 1-5 boundaries are removed. The user freely navigates the codebase:

1. **Entry Point**: Show the project directory tree (`src/` top-level structure) as a starting point.
   The user points at any file, directory, class, or function to ask about.
2. **On-Demand Explanation**: When the user points at code, explain it using the same sources as Guided mode
   (ADR, rules files, `docs/ai/shared/`, AGENTS.md, harness docs, live code reading, etc.).
   Connect to design decisions and architecture context where relevant.
3. **Coverage Tracking**: Internally map the user's questions to the critical topics across all Phases:
   - Phase 1 critical: structural evolution (ADR 006), Entity→DTO (ADR 004), 3-Tier Hybrid (ADR 011), IoC Container (ADR 013)
   - Phase 2 critical: domain directory structure, tech stack
   - Phase 3 critical: Absolute Prohibitions (5 rules)
   - Phase 4 critical: Write/Read conversion patterns
   - Phase 5 critical: Skills overview
4. **Gap Check**: When the user says 'done' (or equivalent), review uncovered critical topics.
   If found, briefly present them grouped by theme (1-2 sentences each).
   If all covered, skip directly to Phase 6 (Next Steps).
5. **Depth Adjustment**: Experience-level adjustments from `docs/ai/shared/onboarding-role-tracks.md` still apply to explanations.

## Phase 1: Methodology and Architecture Evolution History

**Information Source**: `README.md`, `docs/history/` ADR files

> The purpose of this Phase is to help understand "why it was built this way."
> Before explaining rules and structure, the background must be conveyed first so the rules resonate.

**Q&A Mode**: Present the following topic map and wait for questions.
> **Phase 1 Topics -- Architecture Evolution**
> 1. DDD concepts (Bounded Context, Layered Architecture, Dependency Direction)
> 2. Structural evolution -- why `src/{domain}/` flat structure? (ADR 006)
> 3. Entity → DTO unification -- why no Entity pattern? (ADR 004)
> 4. 4-Tier → 3-Tier Hybrid -- why is UseCase optional? (ADR 011)
> 5. IoC Container -- why not FastAPI Depends()? (ADR 013)
> 6. AIDD -- how does AI pair programming work here?
>
> Ask about any topic, or say 'next' to move on.
>
> Critical topics (will be flagged if skipped): 2, 3, 4, 5

**Guided Mode**: Proceed with the sections below.

### 1.1 DDD (Domain-Driven Design) Core Concepts

Explain the following:
- **Bounded Context**: Each domain has independent models and logic. In this project, `src/{domain}/` represents one Bounded Context
- **Layered Architecture**: Separating concerns so each layer can be independently replaced/tested
- **Dependency Direction**: Interface -> Application -> Domain <- Infrastructure (Domain is central, unaware of Infrastructure)

**Experience level adjustment**:
- **Beginner**: Explain each concept in detail with analogies. "Layers are like floors in a building -- the upper floor (Router) knows about the lower floor (Service), but the lower floor doesn't know about the upper floor"
- **Intermediate**: Briefly touch on concepts and move on
- **Advanced**: Skip DDD concept explanation, go directly to 1.2

### 1.2 Evolution of This Project

Reference the ADRs in `docs/history/` directory and convey in narrative form what **problem** each major decision originated from:

**Story 1: Structural Evolution**
- Read `docs/history/006-ddd-layered-architecture.md` and convey the key points
- "Originally apps/ and domains/ were separate, but code navigation was inconvenient, so we switched to per-domain flattening"
- Key takeaway: Opening just one domain folder shows all code for that feature

**Story 2: Entity -> DTO Unification**
- Read `docs/history/004-dto-entity-responsibility.md` and convey the key points
- "Entity was introduced following the DDD pattern, but since there was no business logic, its role overlapped with DTO"
- "to_entity/from_entity conversion was repeated in every handler -> removed and unified to DTO"
- Key takeaway: This is the background for the "No Entity pattern, DTO unification" rule

**Story 3: 4-Tier -> 3-Tier Hybrid**
- Read `docs/history/011-3tier-hybrid-architecture.md` and convey the key points
- "UseCase -> Service -> Repository each simply delegated to the layer below (passthrough)"
- "BaseService was restored, and UseCase is added only when needed -- transitioning to a hybrid"
- Key takeaway: This is the background for the "UseCase is optional" rule. More layers does not mean better architecture

**Story 4: Why IoC Container**
- Read `docs/history/archive/013-why-ioc-container.md` and convey the key points
- "Inheritance implies an is-a relationship, but Service uses (has-a) Repository, not is-a"
- "FastAPI Depends() only works in Router -> cannot be reused in Worker"
- "Container connects Protocol (interface) and implementation at runtime"
- Key takeaway: This is the mechanism that enables the "No Infrastructure import in Domain" rule

### 1.3 AIDD (AI-Driven Development)

Read the **AI Pair Programming (AIDD)** section of `README.md` and explain the following:
- This project is designed for pair programming with AI coding agents
- 14 Skills (slash commands) automate domain creation, API addition, architecture verification, etc.
- Skills reference `AGENTS.md`, `docs/ai/shared/project-dna.md`, shared checklists, and rules to automatically follow project rules

> "If you have any questions, feel free to ask. Otherwise, say 'next'."

## Phase 2: Project Overview

**Information Source**: `docs/ai/shared/project-dna.md` sections 0-1, project overview rules

**Q&A Mode**: Present the following topic map and wait for questions.
> **Phase 2 Topics -- Project Structure**
> 1. Project purpose and scale
> 2. Architecture diagram (3-Tier Hybrid)
> 3. Domain directory structure -- what files make up a domain?
> 4. Current domain list and recent activity
> 5. Tech stack overview
>
> Ask about any topic, or say 'next' to move on.
>
> Critical topics (will be flagged if skipped): 3, 5

**Guided Mode**:

1. Read the **section 0 Project Scale** of `docs/ai/shared/project-dna.md`
   and explain the project's purpose and scale.

2. Show the architecture core using the canonical diagrams in
   `docs/ai/shared/architecture-diagrams.md`. Do **not** dump the Mermaid
   source into the chat — most CLI/terminal clients cannot render it, and
   reading raw Mermaid is worse than no diagram. Instead, pick the first
   option that fits the current viewer:

   **a) Viewer can render images (most chat UIs, IDE Markdown previews)**
   — reference the committed SVG exports directly:
   - `docs/assets/architecture/01-layer-dependency.svg`
   - `docs/assets/architecture/02-write-post-put-delete.svg`
   - `docs/assets/architecture/03-read-get.svg`

   **b) Viewer can render Mermaid natively (GitHub web, some IDEs)**
   — point the user at the canonical file on GitHub:
   `https://github.com/Mr-DooSun/fastapi-agent-blueprint/blob/main/docs/ai/shared/architecture-diagrams.md`

   **c) Plain terminal with no image/Mermaid support** — give the text
   fallback below and link the GitHub URL so the reader can open it:
   ```
   Basic:   Router -> Service(BaseService) -> Repository(BaseRepository)
   Complex: Router -> UseCase -> Service -> Repository   (when combining multiple Services)
   Domain sits at the center; Interface and Infrastructure depend on it.
   Cross-domain access uses Protocol-based DIP, never direct imports.
   ```

   After the diagram is shown (or the links are given), summarise in one
   or two sentences: Domain at the center, UseCase optional, `_core`
   provides base classes and DI.

3. Read **section 1 Domain Directory Structure** of `docs/ai/shared/project-dna.md` and show the file composition of a single domain.

4. Show the current domain list and recent git activity collected during Pre-check.

5. Present the tech stack from the project overview information gathered during Pre-check.

**Experience level adjustment** (refer to `docs/ai/shared/onboarding-role-tracks.md` section 2):
- **Beginner**: Additional explanation of DI Container, Protocol, Pydantic BaseModel
- **Advanced**: Present only domain list + tech stack summary

> "If you have any questions, feel free to ask. Otherwise, say 'next'."

## Phase 3: Architecture Rules

**Information Source**: `AGENTS.md` Absolute Prohibitions section

**Q&A Mode**: Present the following topic map and wait for questions.
> **Phase 3 Topics -- Rules & Terminology**
> 1. Absolute Prohibitions -- 5 rules and their ADR origins
> 2. Terminology -- Request/Response vs DTO vs Model roles and locations
>
> Ask about any topic, or say 'next' to move on.
>
> Critical topics (will be flagged if skipped): 1

**Guided Mode**:

1. Read the **Absolute Prohibitions** section of `AGENTS.md` and present the 5 rules.
   Since the history was already conveyed in Phase 1, connect each rule to **which story it originated from**:
   - "No Infrastructure import in Domain" <- Story 4 (IoC Container enables this)
   - "No Model exposure outside Repository" <- Story 2 (DTO handles inter-layer data transfer)
   - "No Mapper class" <- Inline conversion is sufficient (Story 2)
   - "No Entity pattern, DTO unification" <- Story 2 (ADR 004)
   - "No modifying/deleting shared rule sources without cross-reference verification" <- Meta-rule for consistency maintenance across Skills and guidelines

2. Read the **Terminology** section of `AGENTS.md` and explain the roles and locations of Request/Response, DTO, and Model.

**Experience level adjustment**:
- **Advanced**: Just the rule list + story connections, kept concise

> "If you have any questions, feel free to ask. Otherwise, say 'next'."

## Phase 4: Data Flow Walkthrough

**Information Source**: `AGENTS.md` Conversion Patterns section, `src/user/` live code

**Q&A Mode**: Present the following topic map and wait for questions.
> **Phase 4 Topics -- Data Flow**
> 1. Write path (Request → Service → Repository → DB) conversion pattern
> 2. Read path (DB → Repository → Service → Router) conversion pattern
> 3. Live code example -- `src/user/` create flow
> 4. Live code example -- `src/user/` query flow
>
> Ask about any topic, or say 'next' to move on.
>
> Critical topics (will be flagged if skipped): 1, 2

**Guided Mode**:

1. Read the **Conversion Patterns** section of `AGENTS.md` (Write direction, Read direction) and show the overall flow.

2. Read the actual code from the `src/user/` domain live and show concrete examples:

   **Write Path (Create):**
   - Read the Request DTO and show the field structure
   - Read the Router's create method and show the Request -> Service passing pattern
   - Read the Repository's insert method and show the `Model(**entity.model_dump())` conversion

   **Read Path (Query):**
   - Read the Repository's select method and show the `DTO.model_validate(model)` conversion
   - Show the Router's response return pattern

**Experience level adjustment**:
- **Advanced**: Present only the conversion pattern summary table, skip code walkthrough

> "If you have any questions, feel free to ask. Otherwise, say 'next'."

## Phase 5: Development Workflow and Skills

**Information Source**: Harness guide Skills section, commands reference

**Q&A Mode**: Present the following topic map and wait for questions.
> **Phase 5 Topics -- Workflow & Skills**
> 1. Skills overview -- 14 slash commands and their workflow order
> 2. Frequently used CLI commands (server start, tests, lint)
>
> Ask about any topic, or say 'next' to move on.
>
> Critical topics (will be flagged if skipped): 1

**Guided Mode**:

1. Present the full Skills list in workflow order:
   > "When developing a new feature, use Skills in this order:"
   > Design(`/plan-feature`) -> Create(`/new-domain`, `/add-api`) -> Verify(`/review-architecture`, `/test-domain`) -> Fix(`/fix-bug`)

2. Present frequently used commands (server start, tests, lint, etc.).

**Experience level adjustment**:
- **Advanced**: Present Skills list only

> "If you have any questions, feel free to ask. Otherwise, say 'next'."

## Phase 6: Personalized Next Steps

**Information Source**: `docs/ai/shared/onboarding-role-tracks.md` section 4 Next Step Recommendations

Read the "first 3 tasks" for the user's experience level from `docs/ai/shared/onboarding-role-tracks.md` section 4.

Wrap-up:
```
=== Onboarding Complete ===
Feel free to ask any additional questions at any time.

Key reference materials:
- AGENTS.md -- Shared project rules
- docs/ai/shared/project-dna.md -- Code pattern Reference
- docs/history/ -- Architecture Decision Records (ADR)
- src/user/ -- Reference domain implementation
```
