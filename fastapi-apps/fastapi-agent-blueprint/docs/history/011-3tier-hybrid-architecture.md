# 011. Transition to 3-Tier Hybrid Architecture

- Status: Accepted
- Date: 2026-03-23
- Related Issues: #33
- Related ADRs: 004-dto-entity-responsibility.md (evolution), 006-ddd-layered-architecture.md (evolution)

## Summary

To eliminate 16 passthrough delegation methods per domain, we transitioned from a rigid 4-layer structure to a 3-tier hybrid where UseCase is optional and BaseService provides CRUD via inheritance.

## Background

- **Trigger**: After removing Entity in ADR 004, both UseCase and Service became pure delegation layers — 8 CRUD methods x 2 layers = 16 passthrough methods repeated per domain with no added value.
- **Decision type**: Experience-based correction — the overhead of mandatory UseCase was discovered through actual domain development.

The project was using a 4-layer structure (Router -> UseCase -> Service -> Repository).
After replacing Entity with DTO in ADR 004, both the UseCase and Service layers were only serving as delegation layers that "pass data through as-is."

```python
# UseCase -- delegates to Service only
class UserUseCase:
    async def create_data(self, entity: BaseModel) -> UserDTO:
        return await self.user_service.create_data(entity=entity)

# Service -- delegates to Repository only
class UserService:
    async def create_data(self, entity: BaseModel) -> UserDTO:
        return await self.user_repository.insert_data(entity=entity)
```

8 CRUD methods x 2 layers = 16 passthrough methods repeated per domain.

## Problem

### 1. UseCase Was a Copy of Service

6 out of 7 methods in UserUseCase consisted entirely of `self.user_service.method()` calls.
The only additional logic was pagination handling in `get_datas`.

### 2. Service Was Also a Copy of Repository

All 8 methods in UserService only called `self.user_repository.method()`.
BaseService had previously existed but was removed during the Entity-to-DTO refactoring, reverting to manual delegation.

### 3. Excessive Generic Parameters

In `BaseRepositoryProtocol[CreateDTO, ReturnDTO, UpdateDTO]`, CreateDTO and UpdateDTO
were always set to `BaseModel`, providing no practical type safety.

```python
# 2 out of 3 are always BaseModel -- meaningless
class UserRepositoryProtocol(BaseRepositoryProtocol[BaseModel, UserDTO, BaseModel]):
    pass
```

## Alternatives Considered

### A. Maintain Status Quo (4 layers)
- Manually maintain 16 UseCase/Service delegation boilerplate methods
- Copy the same boilerplate for every new domain
- Advantage: Clear layer separation. Disadvantage: Repetition of code with no practical value

### B. Remove UseCase Entirely (Router -> Service -> Repository)
- Absorb pagination logic into Service
- Disadvantage: Service becomes bloated when complex business logic is needed

### C. Hybrid (chosen)
- Simple CRUD: Router -> Service -> Repository (UseCase omitted)
- Complex logic: Router -> UseCase -> Service -> Repository (UseCase retained)
- Restore BaseService to eliminate Service boilerplate as well

## Decision

**Adopted 3-Tier Hybrid Architecture**

### Change 1: Generic Simplification (3 -> 1)

```python
# Before
BaseRepositoryProtocol[CreateDTO, ReturnDTO, UpdateDTO]  # 3
BaseRepository[CreateDTO, ReturnDTO, UpdateDTO]

# After
BaseRepositoryProtocol[ReturnDTO]  # 1 -- only what's meaningful
BaseRepository[ReturnDTO]
```

Since the write direction passes Request as-is, `BaseModel` is used directly as the parameter type.

### Change 2: Restored BaseService

```python
class BaseService(Generic[ReturnDTO]):
    def __init__(self, repository: BaseRepositoryProtocol[ReturnDTO]):
        self.repository = repository

    async def create_data(self, entity: BaseModel) -> ReturnDTO: ...
    async def get_datas(self, page, page_size) -> tuple[list[ReturnDTO], PaginationInfo]: ...
    # CRUD delegation + automatic pagination
```

Domain Services complete CRUD through inheritance alone:

```python
class UserService(BaseService[UserDTO]):
    def __init__(self, user_repository: UserRepositoryProtocol):
        super().__init__(repository=user_repository)
    # Add only custom methods
```

### Change 3: Optional UseCase Usage

```
Simple CRUD:   Router -> Service(inherits BaseService) -> Repository
Complex logic: Router -> UseCase(manually written) -> Service -> Repository
```

Criteria for adding a UseCase:
- When multiple Services need to be composed
- When the transaction boundary exceeds a single Service

### Change 4: Terminology Standardization

| Term | Role | Location |
|------|------|----------|
| Request/Response | API communication contract | `interface/server/schemas/` |
| DTO | Data transport between internal layers | `domain/dtos/` |
| Model | DB table mapping | `infrastructure/database/models/` |
| Entity | Not used | - |

## Rationale

| Criterion | 4-Layer (before) | 3-Tier Hybrid (current) |
|-----------|-----------------|-------------------------|
| Service boilerplate | 8 methods written manually | BaseService inheritance (0 lines) |
| UseCase boilerplate | 7 methods written manually | Created only when needed |
| Generic type safety | 2 out of 3 meaningless | Only 1 (ReturnDTO) is meaningful |
| Cost to add a domain | 2 files: UseCase + Service | 1 file: Service (5 lines) |
| Complex logic support | UseCase always present | UseCase added when needed |

1. In CRUD-heavy domains, UseCase is an unnecessary delegation layer -- removing passthrough improves code clarity
2. BaseService follows the same pattern as Spring Boot's CRUD Service and NestJS's TypeOrmCrudService
3. Keeping UseCase optional preserves extensibility for complex logic
4. Generic simplification makes type signatures reflect actual meaning

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Post-decision Update (2026-04-09): Restore CreateDTO/UpdateDTO to BaseService

### Condition Change

The original Generic simplification (3 → 1) was based on the premise that "CreateDTO and UpdateDTO were always set to BaseModel, providing no practical type safety." This was correct at the time — domain Services were pure delegation layers.

However, after introducing domain-specific business logic in Service overrides (e.g., password hashing in `UserService.create_data`), Services now access concrete fields like `entity.password`. This requires narrowing the parameter type from `BaseModel` to `CreateUserRequest`, which violates the Liskov Substitution Principle.

### What Changed

With 10+ domains planned, every domain Service would repeat the same LSP-violating pattern:

```python
# Before (LSP violation — BaseService says BaseModel, override says CreateUserRequest)
class BaseService(Generic[ReturnDTO]):
    async def create_data(self, entity: BaseModel) -> ReturnDTO: ...

class UserService(BaseService[UserDTO]):
    async def create_data(self, entity: CreateUserRequest) -> UserDTO: ...  # narrows BaseModel
```

### Correction

Restored `CreateDTO` and `UpdateDTO` TypeVars to **BaseService only** (Repository stays at 1 TypeVar — it only calls `model_dump()` and doesn't benefit from typed inputs):

```python
# After (LSP-compliant — override matches parent signature)
class BaseService(Generic[CreateDTO, UpdateDTO, ReturnDTO]):
    async def create_data(self, entity: CreateDTO) -> ReturnDTO: ...

class UserService(BaseService[CreateUserRequest, UpdateUserRequest, UserDTO]):
    async def create_data(self, entity: CreateUserRequest) -> UserDTO: ...  # matches parent
```

### Why Not Repository Too?

BaseRepositoryProtocol and BaseRepository remain `Generic[ReturnDTO]` with `entity: BaseModel`:
- Repository methods only call `entity.model_dump(exclude_none=True)` — no field-specific access
- `CreateDTO` is bounded by `BaseModel`, so passing it to `entity: BaseModel` is type-safe
- Keeps Repository layer simple; the original ADR 011 rationale still holds at this layer

## Lessons Learned

- More layers do not mean better architecture. Each layer must be validated for providing practical value
- "Let's build it in advance in case we need it later" violates YAGNI. Add it when the need arises
- CRUD automation through base classes is a proven pattern in enterprise frameworks (Spring, NestJS, Django)
- Architecture decisions have preconditions. When preconditions change (e.g., Services gain domain logic), revisit the decision rather than working around it
