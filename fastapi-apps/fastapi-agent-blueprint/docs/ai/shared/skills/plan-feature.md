# Feature Implementation Planning — Detailed Procedure

## Default Flow Position

This skill is the canonical owner of three Default Coding Flow steps:
- **`framing`** — Phase 0 (Requirements Interview)
- **`approach options`** — Phase 1 (Approach Options, ported from #115/#116)
- **`plan`** — Phases 2~4 (Architecture / Security / Tasks)

After this skill completes, control returns to the user; the user invokes the appropriate `implement` skill (`/new-domain`, `/add-api`, `/add-cross-domain`, etc.) and proceeds through `verify` and `self-review`.

Recursion guard: do **not** invoke `/plan-feature` recursively from within itself. Implementation skills (`/new-domain`, `/add-api`, etc.) must **not** invoke `/plan-feature` either — `framing`/`approach`/`plan` happen *before* the implement skill is reached.

When the user uses an exception token on prompt entry, `/plan-feature` is short-circuited per the [`target-operating-model.md` §3](../target-operating-model.md) escape rules.

## Phase 0: Requirements Interview

Ask the user 3-5 questions from the following categories.
Refer to the "Question Bank" in `docs/ai/shared/planning-checklists.md`, but select questions appropriate for the feature.

**Required question categories**:
1. **Data Model** -- What are the core entities and fields?
2. **Business Rules** -- Are there validation/constraint requirements?
3. **User Types** -- Who uses this feature? (Authentication required?)
4. **External Integrations** -- External APIs, file storage, message queues?
5. **Async Processing** -- Are there tasks requiring immediate response vs. background processing?

After receiving user responses, organize the following:
- [ ] Functional requirements checklist
- [ ] Non-functional requirements (performance, security, scalability)
- [ ] Identified edge cases

## Phase 1: Approach Options

Before diving into architecture details, propose 2-3 candidate approaches
for implementing the requirements gathered in Phase 0.

**Requirements**:
- Minimum 2, maximum 3 candidate approaches.
- Each candidate is a *product/design-level* choice, not a listing of
  low-level implementation details.
- Compare along four axes: scope, complexity, extensibility, and
  repo-specific fit.
- Conclude with exactly one `Recommended Approach`.

**Procedure**:
1. For each candidate, write a short description (one-line core idea).
2. List pros, cons, and situations where this approach fits best.
3. Identify the recommended approach; briefly state why others were
   rejected (one line each).

**Output**: populated into the `Approach Options` section of the final
plan (see Output Plan Template).

## Phase 2: Architecture Impact Analysis

### 2.1 Layer Impact Analysis
Determine whether changes/additions are needed for each layer:
- **Domain**: New DTO, Protocol, Service, Exception needed?
- **Application**: New UseCase method needed? Existing UseCase modification?
- **Infrastructure**: New Model, Repository, DI Container needed? DB migration?
- **Interface**: New Router, Request/Response DTO, Worker Task needed?

### 2.2 Domain Impact Analysis
- Is modifying existing domains sufficient? -> Which layer of which domain?
- Is a new domain needed? -> Suggest domain name with rationale
- Search related existing code

### 2.3 DTO Decision
Decide based on the Write DTO criteria in `AGENTS.md`:
- Request fields == Domain fields? -> No separate DTO needed, pass Request directly
- Request fields != Domain fields? -> Separate Create/Update DTO needed, location: `application/` or `domain/dtos/`

### 2.4 Cross-Domain Dependencies
- Does the new feature reference data from existing domains?
- Is Protocol-based DIP needed? -> Apply `/add-cross-domain` pattern

## Phase 3: Security Checkpoint

Evaluate 6 items according to the "Security Assessment Matrix" in `docs/ai/shared/planning-checklists.md`:

| Item | Applicable | Required Action |
|------|-----------|----------------|
| Authentication/Authorization | Y/N | |
| Payment Processing | Y/N | |
| Data Mutation (CUD) | Y/N | |
| External API Integration | Y/N | |
| Sensitive Data (PII) | Y/N | |
| File Upload/Download | Y/N | |

Derive specific security requirements for any applicable items.
**If 1 or more items apply**: Confirm security requirements with the user before proceeding to the next Phase.

## Phase 4: Task Breakdown

### 4.1 Task Identification
Break down Phase 2 analysis results into actionable task units.
Map each task to an existing Skill (refer to the "Skill Mapping Table" in `docs/ai/shared/planning-checklists.md`):

| Task Type | Mapped Skill | Example |
|-----------|-------------|---------|
| New domain creation | `/new-domain {name}` | `/new-domain order` |
| Add API endpoint | `/add-api {desc}` | `/add-api "add POST /orders to order"` |
| Add async task | `/add-worker-task {domain} {task}` | `/add-worker-task order send_notification` |
| Cross-domain connection | `/add-cross-domain from:{a} to:{b}` | `/add-cross-domain from:order to:user` |
| Test generation | `/test-domain {domain} generate` | `/test-domain order generate` |
| Architecture verification | `/review-architecture {domain}` | `/review-architecture order` |
| **Not mappable** | Manual implementation | External API integration, custom middleware, etc. |

### 4.2 Supervision Level Determination
For each task (refer to "Supervision Level Definitions" in `docs/ai/shared/planning-checklists.md`):
- **L1 (AI Delegation)**: 100% mapped to existing Skill, pattern is clear
- **L2 (Confirm then Delegate)**: Business logic decisions, new domain field composition, etc.
- **L3 (Supervision Required)**: Security-related, payment processing, external API integration, DB design decisions

### 4.3 Execution Order and Parallelization
- Create dependency graph (which tasks must precede others)
- Identify task groups that can be executed in parallel
- Identify the critical path

## Output: Feature Implementation Plan

Organize the results of Phases 0-4 above in the following format and present to the user
(refer to the "Output Plan Template" in `docs/ai/shared/planning-checklists.md`):

```
# Feature Implementation Plan: {Feature Name}

## 1. Requirements Summary
(Phase 0 results)

## 2. Approach Options
(Phase 1 results)

## 3. Architecture Impact Analysis
(Phase 2 results -- per-layer change table)

## 4. Security Assessment
(Phase 3 results -- security matrix table)

## 5. Execution Task List
| # | Task | Skill | Supervision Level | Preceding Tasks | Parallel Group |
|---|------|-------|--------------------|-----------------|----------------|
(Phase 4 results)

## 6. Execution Order
(Dependency graph in text representation)

## 7. Verification Plan
- Run /review-architecture {domain}
- Run /test-domain {domain} generate -> run
- Run full pre-commit
```

## After Plan Approval

When the user approves the plan:
1. Suggest executing from the first task in order
2. Guide the corresponding Skill before each task execution
3. Request user confirmation before executing "L3 Supervision Required" tasks
