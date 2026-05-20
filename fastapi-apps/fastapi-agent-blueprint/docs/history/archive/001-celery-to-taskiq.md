# 001. Migration from Celery to Taskiq

- Status: Accepted
- Date: 2025-12-24
- Related issues: #16, #27, #56
- Related commits: `1f1db6b`, `314d09c`, `54d3477`

## Summary

To share async business logic between API and Worker without duplication, we replaced Celery with Taskiq — an asyncio-native task queue where task handlers are `async def`.

## Background

- **Trigger**: After adopting Celery ([000](000-rabbitmq-to-celery.md)), we discovered that sharing async business logic between API and Worker caused event loop conflicts — the core value of "code sharing without duplication" was unachievable with Celery's sync-only tasks.
- **Decision type**: Experience-based correction — the limitation was discovered through actual usage, not anticipated upfront.

We adopted Celery + SQS to reduce the complexity of direct RabbitMQ implementation.
(Adoption context: [000. Migration from RabbitMQ to Celery](000-rabbitmq-to-celery.md))

After adopting Celery, we discovered the potential to share business logic between the API and Worker.
We determined that simple CRUD logic such as looking up user information by user ID could be
reused across both API handlers and Worker tasks.

However, since the entire project stack was async-based, task functions needed to be async
to share business logic, and this caused event loop conflict issues.

- SQLAlchemy 2.0 async engine + asyncpg
- aiohttp-based HTTP client
- aioboto3 (S3)

Rather than attempting workarounds within Celery, we began exploring async-native alternatives
as soon as we recognized the async compatibility limitation.

## Problem

Celery tasks only support `sync def`, so calling async business logic required `asyncio.run()`.

```python
# Code from the Celery era (commit 314d09c)
@shared_task(name="{project-name}.user.test")
@inject
def consume_task(
    user_use_case: UserUseCase = Provide[UserContainer.user_use_case],
    **kwargs,
):
    entity = UserEntity.model_validate(kwargs)
    asyncio.run(user_use_case.process_user(entity=entity))  # Event loop conflict
```

### Root Cause of `asyncio.run()` Conflict

This is not a Celery version issue but a **structural limitation**.

**Prefork pool (default):**
- `asyncio.run()` creates and destroys a new event loop on every call
- SQLAlchemy async session pools, aiohttp clients, etc. are bound to a specific event loop
- New loop each time -> connection pool invalidation -> `RuntimeError: Task got Future attached to a different loop`

**Gevent/Eventlet pool:**
- `asyncio.run()` is called while an event loop is already running
- `RuntimeError: asyncio.run() cannot be called from a running event loop`

### Celery's Async Support Status (as of 2025-12)
- Celery 5.5.x: `async def` tasks **not supported**
- GitHub Issue [#6552](https://github.com/celery/celery/issues/6552): Milestone 5.7.0 (target 2026-06)
- Status: "Design Decision Needed" — architecture design unfinalized

## Alternatives Considered

### A. Background Event Loop Pattern
Maintain one persistent loop in a separate thread per worker process, calling via `run_coroutine_threadsafe()`.

- Connection pool reuse possible
- All async work runs in a single thread -> concurrency bottleneck
- Loop error handling and shutdown logic must be implemented manually
- Complex lifecycle management for DI container async providers

### B. celery-aio-pool
A library that replaces the Celery worker pool with an asyncio-based one.

- Minimal code changes, direct `async def` task support
- 0.1.0rc8 (2024-12) — RC stage, production risk
- Compatibility with SQS broker unverified

### C. worker_process_init Signal
Use a Celery signal to set up an event loop when a worker process starts.

- Solves the "new loop every time" problem of `asyncio.run()`
- `run_until_complete()` cannot be nested
- Unstable loop state after fork in prefork pool

### D. Taskiq (chosen)
A Python asyncio-native task queue. Task handlers are defined as `async def`.

- Async business logic can be called directly with await
- dependency-injector `@inject` + `Provide[]` pattern works identically to the API
- Supports SQS, Redis, RabbitMQ brokers
- Relatively new project with fewer references

## Decision

**Adopt Taskiq**

```python
# Code after Taskiq migration (commit 54d3477)
@broker.task(task_name="{project-name}.user.test")
@inject
async def consume_task(
    user_use_case: UserUseCase = Provide[UserContainer.user_use_case],
    **kwargs,
) -> None:
    entity = UserEntity.model_validate(kwargs)
    await user_use_case.process_user(entity=entity)
```

## Rationale

| Criteria | Celery 5.5 | Taskiq |
|----------|-----------|--------|
| Async business logic sharing | Impossible (bridge code required) | Seamless (direct await calls) |
| Event loop stability | Unstable | Stable |
| Operational ecosystem | Strong (10+ years, Flower) | Weak (new project) |
| DI integration | Unstable at sync/async boundary | Same pattern as API |
| Code duplication | Sync wrappers required | None |

1. The project's core value of "sharing async business logic between API and Worker without duplication" was unachievable with Celery
2. Since the entire stack is async, compatibility with a sync worker is fundamentally difficult
3. Celery workaround patterns function but add hidden complexity to the infrastructure layer, making debugging harder
4. Celery's operational stability advantages are real, but the complexity of async compatibility workarounds offsets those advantages

### Cases Where Celery Would Have Been Better
- Projects where business logic is sync
- Environments where monitoring tools like Flower are essential
- Large teams with extensive Celery operational experience

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
