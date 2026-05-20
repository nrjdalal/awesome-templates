# 004. DTO/Entity Responsibility Redefinition

- Status: Accepted
- Date: 2025-07-15
- Related issues: #6, #57
- Related PR: #7
- Related commits: `bbfd2bf`, `ceebe9c`

## Summary

To eliminate unnecessary conversion boilerplate and concern mixing caused by a misapplied Entity pattern, we removed the Entity layer and let DTOs directly handle data transfer between layers.

## Background

- **Trigger**: Entity was being used as a pure data structure without business logic — effectively duplicating DTO. Conversion boilerplate (`to_entity`/`from_entity`) accumulated in every handler, and multiple inheritance mixed response format concerns with domain data.
- **Decision type**: Experience-based correction — the misapplication of the Entity pattern was recognized through accumulated boilerplate pain, not anticipated upfront.

The project had three types of objects representing data:

- **DTO**: Request/Response data exchanged with clients
- **Entity**: Objects wrapping data as it moves between layers
- **Model**: SQLAlchemy ORM table mapping objects

Among these, Entity's role was understood as "a data carrier that must always wrap data when moving between layers,"
and a structure was used where data was always converted to Entity when moving between use case -> service -> repository.

## Problem

### 1. Misunderstanding of Entity's Role

In DDD, an Entity is a domain object with **business behavior and a unique identifier**.
However, in this project, Entities were used as pure data structures without any business logic.
They were effectively serving the same role as DTOs, merely bearing the name Entity.

### 2. Conversion Required at Every Layer

By treating Entity as a mandatory intermediary object, conversion was required at every layer transition:

```python
# Converting Request -> Entity in Router
create_data.to_entity(CoreCreateUsersEntity)

# Converting Service result Entity -> Response
CoreUsersResponse.from_entity(data)
```

This conversion code was repeated in every API handler,
and `dtos_to_entities()` and `entities_to_dtos()` utilities were even created in `dto_utils.py` for batch data processing.

### 3. Concern Mixing Through Multiple Inheritance

A structure where Response DTOs inherited from Entities was used:

```python
# Problematic multiple inheritance pattern
class CoreUsersResponse(BaseResponse, CoreUsersEntity):
    pass

class CoreCreateUsersRequest(BaseRequest, CoreCreateUsersEntity):
    pass
```

Two different concerns — "response format" (BaseResponse) and "domain data" (Entity) — were mixed through multiple inheritance.
This caused:
- Blurred boundaries between DTO and Entity
- Potential MRO (Method Resolution Order) conflicts
- Entity field changes directly affecting Response schemas

## Alternatives Considered

### A. Keep Entity with explicit to_entity/from_entity (Phase 1 attempt)

Initially attempted in commit `bbfd2bf` (2025-07): separate DTO and Entity responsibilities by making conversions explicit.

```python
class BaseRequest(ApiConfig):
    def to_entity(self, entity_cls: Type[EntityType]) -> EntityType:
        return entity_cls(**self.model_dump())

class BaseResponse(ApiConfig):
    @classmethod
    def from_entity(cls, entity: Entity) -> ReturnType:
        return cls(**entity.model_dump())
```

Through actual usage, wrapping in Entity every time remained cumbersome, and Entity still held data without any business logic — the core problem was not solved, only made more verbose.

### B. Remove Entity, use DTO directly (chosen)

Since domain objects in this project have no complex business behavior, remove the Entity layer entirely and let DTOs directly handle data transfer between layers.

After research to relearn Entity's original role:

| Object | Role | Business Logic |
|--------|------|---------------|
| DTO | Data transfer between layers | None |
| Entity (DDD) | Domain behavior + identifier | **Yes** |
| Model | DB table mapping | None |

Entity has value only when there is business behavior. For CRUD-oriented domains, DTO is sufficient.

## Decision

**Removed Entity layer, using DTO directly** (issue #57, 2026-03)

**Current rules:**
- Using `to_entity()`, `from_entity()` methods is prohibited
- Multiple inheritance pattern `class Response(BaseResponse, Entity)` is prohibited
- Model objects must not be exposed outside the Repository
- Conversions are done inline: `model_dump()`, `model_validate()`

## Rationale

| Criteria | Mandatory Entity (before) | Direct DTO Transfer (current) |
|----------|--------------------------|-------------------------------|
| Conversion boilerplate | to/from_entity required in every handler | Not needed |
| Separation of concerns | Mixed through multiple inheritance | DTO and Model fully separated |
| Code complexity | Separate dto_utils.py required | Inline conversion is sufficient |
| Entity's value | Carried data without business logic | Introduce Entity when actually needed |

1. When Entity carries data without business behavior, it duplicates DTO — removal is rational
2. Multiple inheritance mixes concerns and makes change impact scope unpredictable
3. Inline conversion with `model_dump()` / `model_validate()` eliminates the need for separate methods or utilities

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Lessons Learned

- When adopting DDD concepts, understand the "purpose" before the "form" of a pattern
- Entity has value when there is business behavior. For CRUD-oriented domains, DTO is sufficient
- Introducing a pattern without conviction leads to recognizing the problem only after boilerplate has accumulated
- The inconvenience felt while actually writing code was the best signal for architecture review
