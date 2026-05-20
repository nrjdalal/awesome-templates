# 016. Worker Payload Schema

- Status: Accepted
- Date: 2026-04-06
- Related issue: #37
- Related ADR: [003](../003-response-request-pattern.md)(Response/Request Pattern), [004](../004-dto-entity-responsibility.md)(DTO/Entity Responsibility)

## Summary

To eliminate implicit message contracts in worker tasks, we introduced Payload schemas in `interface/worker/payloads/` — mirroring the Request/Response pattern that the HTTP interface already had.

## Background

- **Trigger**: As the project targets 10+ domains with independent teams developing Producers and Consumers, the lack of explicit message contracts in worker tasks became a concrete risk — unlike the HTTP interface, which already had Request schemas.
- **Decision type**: Upfront design — addressing the gap before scaling, not after a production incident.

The project has progressively established data object roles:

- ADR 003 separated Request/Response as HTTP communication contracts
- ADR 004 removed Entity and redefined DTO as the internal data carrier between layers
- Model is restricted to DB table mapping, never exposed outside Repository

As a result, the HTTP interface (`server/`) has explicit contracts via `schemas/`.
However, the worker interface (`worker/`) had no equivalent contract.

Worker tasks received messages via `**kwargs` and validated directly with domain DTOs:

```python
async def consume_task(**kwargs):
    dto = UserDTO.model_validate(kwargs)
```

In the early stages, with a single domain (user) and simple tasks, this approach caused no issues.
However, as the project targets 10+ domains and 5+ team members,
different teams will develop Producer (server) and Consumer (worker) independently.
At this scale, implicit message contracts become a real risk.

## Problem

### 1. Implicit Contract

Producers cannot determine what fields to send by looking at the code.
`**kwargs` reveals nothing about the expected message shape — developers must read task internals.

### 2. Domain DTO Coupling

When a domain DTO gains or changes fields, existing messages fail at runtime.
Example: if `UserDTO` adds a required `role` field, messages from existing Producers
will raise `ValidationError`, but this cannot be detected before deployment.

### 3. No Producer-Side Validation

There is no way to validate message format before sending.
Malformed messages enter the queue and are only discovered when the Consumer fails to process them.

The HTTP interface already solved all three problems with Request schemas.
The worker interface lacked the same level of safety — an asymmetry in the architecture.

## Alternatives Considered

### A. Merge into schemas/ directory

Place worker schemas alongside server schemas in `interface/server/schemas/`.

Rejected: Server schemas (camelCase, API-facing) and worker schemas (snake_case, internal)
serve different purposes with different configurations. Mixing them causes name collisions and role confusion.

### B. Continue using domain DTO directly

Keep the current approach and manage contracts through documentation only.

Rejected: Documentation inevitably drifts from code.
Errors catchable at construction time (Pydantic validation) get deferred to runtime.

### C. Convert Payload → DTO before passing to Service

Initially implemented: validate `**kwargs` into a Payload, then convert to DTO for the Service.

```python
payload = UserTestPayload.model_validate(kwargs)
dto = UserDTO(**payload.model_dump())           # unnecessary conversion
await user_service.process_user(dto=dto)
```

Rejected after review: this introduced an inconsistency with the Router pattern.
Routers pass Request objects directly to Service (`entity=item`) without converting to DTO
when fields match (see AGENTS.md "Write DTO Creation Criteria").
Since `BaseService` methods accept `entity: BaseModel`, both Request and Payload
can be passed directly — the Service never imports either type; it simply receives a BaseModel.
Forcing Payload → DTO conversion only in the worker created an unnecessary asymmetry.

## Decision

Define Payload schemas in `interface/worker/payloads/`.

- **Terminology**: "Payload" — the industry-standard term used by [AsyncAPI](https://www.asyncapi.com/docs/concepts/asyncapi-document/define-payload) for message data schemas
- **Base config**: `frozen=True` (immutable message) + `extra="forbid"` (strict contract)
- **Location**: Interface layer (`interface/worker/payloads/`)
- **Pass-through rule**: When fields match, pass Payload directly to Service — same principle as Router passing Request directly
- **Independent from DTO**: Declared separately even when fields are identical. Message contracts and domain data can evolve independently.

```python
# After: explicit contract, direct pass-through
async def consume_task(**kwargs):
    payload = UserTestPayload.model_validate(kwargs)    # message contract validation
    await user_service.process_user(dto=payload)         # direct pass (same as Request)
```

This completes the project's four data object roles:

| Object | Role | Location | ADR |
|--------|------|----------|-----|
| Request/Response | HTTP communication contract | `interface/server/schemas/` | 003 |
| Payload | Worker message contract | `interface/worker/payloads/` | 016 |
| DTO | Internal data carrier between layers | `domain/dtos/` | 004 |
| Model | DB table mapping | `infrastructure/database/models/` | — |

## Rationale

| Decision | Reason |
|----------|--------|
| Separate directory (`payloads/`) | Different purpose and config from server schemas. Separation avoids confusion |
| `frozen=True` | Received messages are immutable. Tasks must not mutate them |
| `extra="forbid"` | Immediately rejects unexpected fields. Catches Producer mistakes early |
| Independent from DTO | Message contracts can change without affecting domain DTOs, and vice versa |
| Direct pass to Service | Consistent with Router's Request pass-through. `BaseService` accepts `entity: BaseModel`, so no conversion needed when fields match. Only convert when Payload and DTO fields actually differ |
| AsyncAPI "Payload" terminology | Industry-standard term reduces communication overhead across teams |
| No TaskiqManager changes | Producers serialize via `payload.model_dump()`. Avoids adding Application-layer dependency to Infrastructure |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
