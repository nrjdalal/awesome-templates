# 024. Session Lifecycle Management: Context Manager over Factory

- Status: Accepted
- Date: 2025-08 ~ 2025-10
- Related ADR: [011](../011-3tier-hybrid-architecture.md)(3-Tier Hybrid Architecture), [013](013-why-ioc-container.md)(IoC Container)

## Summary

To make database session lifecycle explicit and prevent leaked sessions, we chose a context-manager-per-repository-method pattern (`async with self.database.session()`) over request-scoped sessions or session factories — each repository operation owns its complete session lifecycle including commit, rollback, and close.

## Background

- **Trigger**: Early implementations used a session factory that created sessions without explicit lifecycle management. Sessions were sometimes not properly closed, causing connection pool exhaustion under load. The factory pattern also made it unclear when commits and rollbacks happened.
- **Decision type**: Experience-based correction — session leaks in testing revealed that implicit lifecycle management was unreliable.

The project went through three stages:
1. **Session factory** — `session_factory()` returned a session, caller responsible for close
2. **Factory removal** — removed factory, switched to explicit context manager
3. **Database class encapsulation** — `Database.session()` as async context manager with automatic rollback and close

## Problem

### 1. Session Leaks

When callers forgot to close sessions (especially in error paths), connections remained open. With a limited connection pool, this caused timeouts and hangs.

### 2. Ambiguous Transaction Boundaries

With a factory pattern, it was unclear who was responsible for `commit()` and `rollback()`. Some callers committed, others didn't — leading to data inconsistencies.

### 3. Error Handling Gaps

Exceptions during database operations could leave sessions in a dirty state. Without automatic rollback on error, partial writes could persist.

## Alternatives Considered

### A. Request-Scoped Session (FastAPI Depends)

Use FastAPI's dependency injection to create one session per HTTP request:

```python
async def get_session():
    async with async_session() as session:
        yield session
```

Rejected: Couples the session lifecycle to the HTTP request boundary. Worker tasks (Taskiq) and admin operations don't have HTTP requests. The project has three apps (Server, Worker, Admin) that need identical session management — tying it to FastAPI's Depends() makes it Server-only.

### B. Scoped Session (SQLAlchemy scoped_session)

Use SQLAlchemy's `scoped_session` for automatic session management per async context.

Rejected: `scoped_session` with asyncio requires careful task-local storage configuration. It's an implicit mechanism that obscures when sessions start and end. Explicit context managers are easier to reason about and debug.

### C. Unit of Work Pattern

Implement a Unit of Work that groups multiple repository operations into a single session.

Rejected for now: The current architecture's session-per-method approach is simpler and works well for most CRUD operations. When complex cross-repository transactions are needed, the UseCase layer (ADR 011) can coordinate them. A full Unit of Work pattern can be introduced later if the need arises.

## Decision

The `Database` class provides an async context manager that encapsulates the full session lifecycle:

```python
class Database:
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        session = None
        try:
            session = self.async_session_factory()
            yield session
        except IntegrityError:
            if session: await session.rollback()
            raise DatabaseException(...)
        except Exception as e:
            if session: await session.rollback()
            raise DatabaseException(...)
        finally:
            if session: await session.close()
```

Each `BaseRepository` method creates its own session:

```python
async def insert_data(self, entity: BaseModel) -> ReturnDTO:
    async with self.database.session() as session:
        data = self.model(**entity.model_dump(exclude_none=True))
        session.add(data)
        await session.commit()
        await session.refresh(data)
        return self.return_entity.model_validate(data, from_attributes=True)
```

**Key characteristics:**
- **Session-per-method**: each repository method owns a complete transaction
- **Automatic rollback**: `IntegrityError` and generic exceptions trigger rollback before re-raising
- **Guaranteed close**: `finally` block ensures session is always closed, even on unexpected errors
- **DatabaseException wrapping**: Raw SQLAlchemy exceptions are wrapped in domain-specific exceptions, preventing infrastructure details from leaking to upper layers

**Implication for cross-method transactions:**
When multiple repository methods need to run in a single transaction, the UseCase layer (ADR 011) is the designated coordination point. This is one of the criteria for introducing a UseCase — "cross-transaction boundaries" as stated in AGENTS.md.

## Rationale

| Decision | Reason |
|----------|--------|
| Context manager over factory | Explicit lifecycle (create → use → commit/rollback → close) in a single `async with` block. Cannot forget to close |
| Session-per-method over request-scoped | Works identically across Server (HTTP), Worker (Taskiq), and Admin (SQLAdmin). No framework coupling |
| Automatic rollback on error | Prevents dirty sessions from persisting. Exceptions always leave the database in a clean state |
| DatabaseException wrapping | Infrastructure details (SQLAlchemy `IntegrityError`) don't leak to the domain layer. Consistent error format |
| `expire_on_commit=False` | Allows accessing ORM attributes after commit without triggering lazy loads — important for the `model_validate()` conversion to DTO |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
