# Feature Planning Checklist Details

## 1. Requirements Interview Question Bank

### Data Model
- What are the core entities (data) for this feature? (e.g., Order, Product, Payment)
- What are the main fields for each entity? (e.g., name, price, status)
- Are there relationships between entities? (1:N, N:M, etc.)
- Are there unique constraints? (unique fields, composite keys, etc.)
- Should this data use RDB (relational, ACID) or DynamoDB (NoSQL, key-value, auto-scaling)?

### Business Rules
- Are there mandatory validation conditions when creating data?
- Are there state transition rules? (e.g., pending -> confirmed -> shipped)
- Are there calculated/derived values in the business logic?
- Are there cases requiring concurrency handling? (inventory deduction, seat reservation, etc.)

### User Types and Permissions
- What user types will use this feature? (anonymous, regular user, admin)
- If permission levels differ, what actions are available at each level?
- Is there a data ownership concept? (access only own data?)

### External Integrations
- Are external API calls needed? (payment gateway, notification service, etc.)
- Are file uploads/downloads needed? (S3, local storage)
- Are email/SMS/push notifications needed?

### Async Processing
- Which tasks need immediate response vs. can be processed in the background?
- Are there tasks that need scheduled execution?
- Are there cases requiring bulk data processing?

### Errors and Exceptions
- What are the main failure scenarios? (data not found, unauthorized, duplicate, external integration failure)
- Is rollback/compensating transaction needed on failure?
- Is a retry policy needed?

## 2. Security Assessment Matrix

### Authentication & Authorization
- [ ] Is this a login-required endpoint?
- [ ] Is role-based access control (RBAC) needed?
- [ ] Does a token verification middleware already exist, or does one need to be added?
- [ ] Is data ownership verification needed? (access only own data)

### Payment Processing
- [ ] Is payment amount integrity verification needed?
- [ ] Are audit logs needed for payment status changes?
- [ ] Is PCI DSS-related data being stored directly?
- [ ] Are payment failure/refund scenarios defined?

### Data Modification (CUD)
- [ ] CREATE: Is input data validation sufficient?
- [ ] UPDATE: Are permission checks in place for partial updates?
- [ ] DELETE: Physical delete vs. soft delete decision?
- [ ] Is change history (audit trail) needed?

### External API Integration
- [ ] Is the API key/secret management method defined? (env vars, secret manager)
- [ ] Are request/response logs free of sensitive data exposure?
- [ ] Are timeout and circuit breaker settings needed?
- [ ] Is there a fallback strategy for external API failures?

### Sensitive Data (PII)
- [ ] What PII data is being stored? (name, email, phone number, address)
- [ ] Is PII excluded from Response? (model_dump exclude applied)
- [ ] Is PII excluded from logs?
- [ ] Is data encryption (at rest, in transit) needed?

### File Processing
- [ ] Is upload file size limit configured?
- [ ] Is file extension/MIME type validation in place?
- [ ] Is the storage path free of path traversal risk?
- [ ] Is file access permission verification in place?

## 3. Skill Mapping Table

| Task Type | Mapped Skill | Argument Format | Notes |
|-----------|-------------|-----------------|-------|
| New domain creation | `/new-domain` | `{name}` | Default 44 files (15 content + 25 `__init__.py` + 4 tests) |
| CRUD API addition | `/add-api` | `"add {METHOD} /{path} to {domain}"` | Bottom-up implementation |
| Custom API addition | `/add-api` | `"{description}"` | Supervision Level required when business logic is included |
| Async task | `/add-worker-task` | `{domain} {task_name}` | Add UseCase method first if needed |
| Admin page addition | `/add-admin-page` | `{domain}` | Auto-discovers, no bootstrap changes needed |
| Cross-domain connection | `/add-cross-domain` | `from:{consumer} to:{provider}` | Protocol-based DIP |
| Test generation | `/test-domain` | `{domain} generate` | baseline + conditional test files (see `docs/ai/shared/test-files.md`) |
| Test execution | `/test-domain` | `{domain} run` | unit + integration + e2e |
| Architecture verification | `/review-architecture` | `{domain}` or `all` | 10 categories, severity-tagged architecture audit |
| Security audit | `/security-review` | `{domain}`, `{file}`, or `all` | 13 categories, feature-freshness preflight, stale-drift detection |
| Guideline sync | `/sync-guidelines` | (none) | Close the quality gate after design changes or review drift |
| Approved plan execution | `/execute-plan` / `$execute-plan` | `{Execution Packet or plan ref}` | Native execution workflow for complex, architecture-changing, governor-changing, or multi-task plans |
| Bug fix | `/fix-bug` | `"{description}"` | Reproduce (existence gate) -> Trace (Cause Impact Matrix) -> Fix -> Verify, then a Bug Fix Report carrying `Outcome` |
| DB migration | `/migrate-domain` | `generate\|upgrade\|downgrade\|status` | Manual review required after autogenerate |
| New member onboarding | `/onboard` | (none) | Experience-level adaptive (Beginner/Intermediate/Advanced) |
| Sub-feature design | `/plan-feature` | `"{description}"` | Decompose inside the same Execution Packet; never invoke recursively |
| PR review | `/review-pr` | `{number\|URL}` | Diff review + drift candidates + explicit sync-required decision |
| DynamoDB migration | `python -m migrations.dynamodb.cli --env {env}` | — | DynamoDB table/GSI creation (manual CLI) |
| **Unmappable** items | Manual implementation | — | External API integrations, middleware, etc. |

## 4. Supervision Level Definitions

### L1: Fully Delegatable to AI
- Tasks that map 100% to existing Skills
- Repetition of existing patterns (new CRUD endpoints, etc.)
- Test generation/execution
- Architecture verification

### L2: Delegate After Human Confirmation
- New domain creation (field configuration review needed)
- UseCase implementation with business logic
- DTO decisions (direct Request pass-through vs. separate DTO)
- DB migration (alembic revision)

### L3: Human Supervision Required
- Security-related implementation (authentication, authorization, encryption)
- Payment processing logic
- External API integration (API key management, error handling)
- Data model design decisions (relationships, indexes, constraints)
- Existing API signature changes (backward compatibility)

## 5. Output Plan Template

```markdown
# Feature Implementation Plan: {Feature Name}
- Date: {date}
- Request: {user description}

## 1. Requirements Summary

### Functional Requirements
- [ ] {requirement 1}
- [ ] {requirement 2}

### Non-Functional Requirements
- [ ] {NFR 1}

### Edge Cases
- {edge case 1}

## 2. Approach Options

### Option A: {core idea in one line}
- Pros: {...}
- Cons: {...}
- Best fit: {situation where this approach is most appropriate}

### Option B: {core idea in one line}
- Pros: {...}
- Cons: {...}
- Best fit: {situation where this approach is most appropriate}

### (Option C — if applicable)

### Recommended Approach
- Selected: Option {X}
- Why: {rationale; for an affected architectural choice, link its scoped Decision Basis
  under Architecture Impact rather than only listing ADR IDs}
- Why not others: Option {Y} — {one-line reason}; Option {Z} — {one-line reason}

## 3. Architecture Impact Analysis

{For affected choices, apply `docs/ai/shared/adr-evidence.md` inside this section:
explain how the governing clause changes the choice and link current evidence or
limits. If none is affected, give one scope-based reason.}

### Changes by Layer
| Layer | Change Type | Details |
|-------|------------|---------|
| Domain | New/Modified/None | {details} |
| Application | New/Modified/None | {details} |
| Infrastructure | New/Modified/None | {details} |
| Interface | New/Modified/None | {details} |

### Domain Impact
- Existing domains: {list}
- New domain: {name or "not needed"}
- Cross-domain dependencies: {list or "none"}

### DTO Decisions
- {each DTO decision with rationale}

## 4. Security Assessment

| Item | Applicable | Required Action |
|------|-----------|----------------|
| Authentication/Authorization | {Y/N} | {action} |
| Payment Processing | {Y/N} | {action} |
| Data Modification | {Y/N} | {action} |
| External API | {Y/N} | {action} |
| Sensitive Data | {Y/N} | {action} |
| File Processing | {Y/N} | {action} |

## 5. Execution Task List

| # | Task | Skill | Supervision Level | Predecessor | Parallel Group |
|---|------|-------|----------|------------|----------|
| 1 | {task} | {skill} | L1/L2/L3 | - | A |
| 2 | {task} | {skill} | L1/L2/L3 | 1 | B |

## 6. Execution Order

### Stage 1 (Parallel Group A)
- Tasks 1, 2

### Stage 2 (Parallel Group B — after Stage 1 completion)
- Tasks 3, 4

### Critical Path
Task 1 -> 3 -> 5 -> 6

## 7. Verification Plan
- [ ] `/review-architecture {domain}` — confirm architecture compliance
- [ ] `/test-domain {domain} generate` — generate tests
- [ ] `/test-domain {domain} run` — run tests
- [ ] `pre-commit run --all-files` — lint/format check
- [ ] Verify endpoint behavior in Swagger UI
```

## 6. Execution Packet Contract

Every approved multi-task, architecture-changing, or governor-changing plan must
end with an **Execution Packet** for `/execute-plan` / `$execute-plan`.

Required fields:

- **Goal**: one sentence.
- **Scope**: affected domains, files, interfaces, and explicit exclusions.
- **Success Criteria**: observable completion conditions.
- **Selected Approach**: selected option and rationale, including how applicable
  decision clauses influenced the choice; link the existing Architecture Impact evidence.
- **Architecture Impact**: layer, domain, dependency, DTO, migration, and
  compatibility impact, with a scoped [Decision Basis](adr-evidence.md) for affected
  choices (or a scope-based no-affected-decision reason). This reuses the existing
  field; it adds no required top-level packet field.
- **Task List**: ordered task IDs, titles, mapped skills, dependencies, and
  initial status.
- **Verification Gates**: exact commands or manual probes with expected result.
- **Review Gates**: self-review, architecture/security review, sync-guidelines,
  cross-tool review by the other harness when governor-changing, and fallback
  policy.

After approval, record the packet in the work ledger:

```python
from work_ledger import update_goal_scope_plan, update_workflow_state

update_goal_scope_plan(
    goal="<Goal>",
    scope="<Scope>",
    plan="<Task List>",
    updated_by="skill:plan-feature",
)
update_workflow_state(
    stage="planned",
    plan_ref="<issue, PR, or plan file>",
    tasks=[{"id": "1", "title": "<task>", "status": "pending"}],
    updated_by="skill:plan-feature",
)
```

## 7. Ticket Brief Projection

Project an approved Execution Packet into the [ticket contract](ticket-workflow.md):
intent, non-goals, done-when, premises with evidence, approved packet/approval,
predecessors, file set, Parallel Group and Supervision L1-L3. Keep implementation
choices in the packet; project applicable decision constraints and their evidence
through the existing premises field, linking the packet's Decision Basis rather
than copying the ADR. Epic/ticket/task criteria and fresh-session execution live
in that contract; native issue bodies use the repository Execution Ticket template.
