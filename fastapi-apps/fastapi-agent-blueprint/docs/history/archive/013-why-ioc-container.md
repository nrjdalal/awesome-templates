# 013. Why IoC Container Over Inheritance

- Status: Accepted
- Date: 2026-03-23
- Related Issues: #21
- Related ADRs: ../007-di-container-and-app-separation.md (supplementary)

## Summary

To achieve layer separation, testability, and Server/Worker code sharing, we introduced an IoC Container (`dependency-injector`) instead of relying on inheritance, direct instantiation, or FastAPI's `Depends()`.

## Background

- **Trigger**: FastAPI's built-in `Depends()` only works at the Router level — it cannot inject dependencies into Worker tasks, making Server/Worker business logic sharing impossible without a framework-independent DI mechanism.
- **Decision type**: Upfront design — the IoC Container was introduced to support the architectural goal of enterprise-scale extensibility (10+ domains) and Server/Worker code sharing.

The simplest way to manage dependencies in Python is inheritance:

```python
class UserService:
    def __init__(self):
        self.repository = UserRepository()  # Direct instantiation
```

Or using inheritance to embed the Repository:

```python
class BaseService(UserRepository):  # Include Repository functionality via inheritance
    pass
```

FastAPI also has a built-in `Depends()` that enables simple DI.
So why was a separate IoC Container library (`dependency-injector`) introduced?

## Problem

Managing dependencies between layers (Router -> Service -> Repository) requires a mechanism that supports:
- Testability (mock replacement without real DB)
- Resource sharing (singleton connection pools)
- Multi-interface reuse (same Service in both Server and Worker)

The existing Python approaches each fall short of these requirements.

## Alternatives Considered

### A. Inheritance

```python
class UserService(UserRepository):
    pass
```

When Service **inherits** from Repository:
- Service gains **all methods** of Repository (unintended DB access exposure)
- Changes to the Repository implementation break Service (inheritance chain propagation)
- What if Service needs to use multiple Repositories? Python supports multiple inheritance, but there is a risk of MRO conflicts

**Inheritance is an "is-a" relationship**. Service is not a Repository; it **uses** a Repository ("has-a").

### B. Direct Instantiation

```python
class UserService:
    def __init__(self):
        self.repository = UserRepository(database=Database())  # Hardcoded
```

- Cannot replace with MockRepository in tests (cannot test without DB)
- Creates a new Database instance every time (cannot reuse connection pool)
- Changing the Repository implementation requires modifying Service code

### C. FastAPI Depends()

```python
@router.post("/user")
async def create_user(
    service: UserService = Depends(get_user_service)
):
    ...
```

FastAPI's `Depends()` **only works at the Router level**:
- Cannot use `Depends()` in Worker tasks
- Hard to express inter-Service dependencies (Service A uses Service B)
- No singleton guarantee (new instance possible per request)

### D. IoC Container via dependency-injector (chosen)

- Service depends only on Protocol (interface), not the implementation
- Container declares wiring: which implementation backs which Protocol
- Singleton provider ensures expensive resources (DB pool, HTTP client) are created once
- Same `@inject` + `Provide[]` pattern works in both Server Routers and Worker Tasks

## Decision

**Introduced IoC Container via the dependency-injector library**

### Constructor Injection

```python
# Service depends only on Protocol (interface)
class UserService(BaseService[UserDTO]):
    def __init__(self, user_repository: UserRepositoryProtocol):
        super().__init__(repository=user_repository)
```

- Service only knows about `UserRepositoryProtocol`, not the implementation
- The actual implementation wiring is the Container's responsibility

### Container Handles Assembly

```python
class UserContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    user_repository = providers.Singleton(
        UserRepository,
        database=core_container.database,  # DB shared as singleton
    )

    user_service = providers.Factory(
        UserService,
        user_repository=user_repository,  # Implementation wired here
    )
```

### Server and Worker Reuse the Same Container

```python
# Server Router -- injected from Container via @inject
@inject
async def create_user(
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
): ...

# Worker Task -- same pattern
@inject
async def consume_task(
    user_service: UserService = Provide[UserContainer.user_service],
): ...
```

## Rationale

| Criterion | Inheritance | Direct Instantiation | FastAPI Depends | IoC Container |
|-----------|-----------|---------------------|----------------|---------------|
| Coupling | High (is-a) | High (hardcoded) | Medium | **Low** (interface only) |
| Testing | Hard to mock | Cannot mock | Mockable | **Easy to mock** |
| Worker support | - | - | Not possible | **Possible** |
| Singleton guarantee | - | Not possible | Not possible | **Singleton provider** |
| Layer separation | Violated | Violated | Router only | **All layers** |

1. **Protocol + Container = DIP Realized**: The Domain layer does not know about Infrastructure, and the Container wires implementations at runtime. This is the core mechanism that enables the "no Infrastructure imports in Domain" rule.

2. **Resource Management via Singleton**: Expensive resources like Database connection pools, HTTP clients, and SQS brokers are created once with `providers.Singleton` and shared across the entire app.

3. **Server/Worker Code Sharing**: The same Service/Repository is used in both Server Routers and Worker Tasks with the identical pattern (`@inject` + `Provide[]`). This is not possible with FastAPI `Depends()` alone for Workers.

4. **Test Isolation**: Overriding the Container allows testing with MockRepository without a real DB. This pattern is actively used in the current unit tests.

## Compensating Layered Architecture's Scalability Limitations with IoC Container

A well-known weakness of layered architecture is **scalability**:
- Adding a new domain requires creating files in each layer and manually registering them
- Inter-domain dependencies lead to imports that cross layer boundaries
- Fixed layers make flexible composition difficult

The IoC Container solves these problems:

### 1. Domain Auto-Discovery

```python
# src/_core/infrastructure/discovery.py
def discover_domains():
    # Auto-detects src/{name}/infrastructure/di/{name}_container.py
    # -> Dynamically registers in DynamicContainer
```

When adding a new domain, there is **no need to modify** `_apps/server/container.py` or `bootstrap.py`.
As long as the Container follows the convention, it is automatically registered.

### 2. Inter-Domain Dependencies Resolved at the Container Level

```python
# When quiz_container needs to use chat_service
class QuizContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    # Inject another domain's Repository via Protocol
    chat_repository = providers.Singleton(
        ChatRepository,
        database=core_container.database,
    )

    quiz_service = providers.Factory(
        QuizService,
        quiz_repository=quiz_repository,
        chat_repository=chat_repository,  # Container handles the wiring
    )
```

Domain code depends only on Protocols, and **the actual wiring is the Container's responsibility**.
Inter-domain dependencies can be resolved without cross-layer imports.

### 3. Flexible Composition Per Interface

The same domain Containers can be composed in Server/Worker/Admin by **selecting only what's needed**:

```
Server: CoreContainer + UserContainer + QuizContainer (all)
Worker: CoreContainer + QuizContainer (quiz async processing only)
Admin:  CoreContainer + UserContainer (user management only)
```

The "rigid structure" limitation of layered architecture is overcome through the Container's **declarative composition**.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Supplementary: Why Protocol over ABC for Cross-Domain DIP

The project uses `typing.Protocol` (structural subtyping) instead of `abc.ABC` (nominal subtyping) for dependency inversion between layers:

```python
# domain/protocols/user_repository_protocol.py
class UserRepositoryProtocol(BaseRepositoryProtocol[UserDTO], Protocol):
    ...
```

**Why Protocol over ABC?**

| Criterion | `abc.ABC` | `typing.Protocol` |
|-----------|-----------|-------------------|
| Subtyping | Nominal — must explicitly inherit | Structural — any class with matching methods qualifies |
| Import direction | Implementation must import the ABC | Implementation does not need to import Protocol |
| Domain layer purity | ABC definition in Domain, but implementation in Infrastructure must `import` it — creating a reverse dependency | Protocol in Domain is never imported by Infrastructure. Container wires them at runtime |
| Duck typing alignment | Requires explicit `register()` or inheritance | Natural fit for Python's duck typing philosophy |

The key benefit is **import direction**: with ABC, `UserRepository(UserRepositoryABC)` in the Infrastructure layer must import from the Domain layer, creating a dependency from Infrastructure → Domain. With Protocol, `UserRepository` simply implements the same method signatures — no import needed. The Container handles the wiring, keeping the dependency graph clean: Domain ← Infrastructure (via Container), never Domain → Infrastructure.

This is why the pre-commit hook (`no-domain-infra-import`) can enforce "no Infrastructure imports in Domain" without exceptions for interface imports — Protocol-based DIP requires no such imports.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Complete separation between layers | Requires learning dependency-injector |
| Testability | Container declaration boilerplate |
| Resource lifecycle management | Tracing through Container during debugging |
| Server/Worker code sharing | Requires familiarity with `@inject` decorator pattern |

For small-scale projects with only simple CRUD, FastAPI `Depends()` is sufficient.
This project introduced an IoC Container because it was designed with the premise of
**enterprise-scale extensibility** (10+ domains, 5+ team members) and
**Server/Worker business logic sharing**.
