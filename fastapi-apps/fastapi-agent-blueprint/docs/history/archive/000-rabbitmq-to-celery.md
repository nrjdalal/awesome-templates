# 000. Migration from RabbitMQ to Celery

- Status: Superseded by [001](001-celery-to-taskiq.md)
- Date: 2025-09-10
- Related issue: #16
- Related commit: `1f1db6b`

## Summary

To reduce the infrastructure boilerplate of direct RabbitMQ consumer implementation, we adopted Celery + SQS as a higher-level task queue abstraction.

## Background

- **Trigger**: More development time was being spent on infrastructure code (connection management, serialization, retry logic) than on business logic. The custom RabbitMQ consumer required managing too many low-level concerns manually.
- **Decision type**: Experience-based correction — the overhead of raw RabbitMQ was felt through accumulated boilerplate.

We were using a custom RabbitMQ consumer implementation for asynchronous task processing.
The basic architecture involved publishing messages and having consumers receive and process them.

## Problem

Directly implementing RabbitMQ consumers required managing many concerns:
- Manual management of consumer, exchange, and queue configuration
- Connection/channel lifecycle management
- Manual message serialization/deserialization
- Boilerplate code for retries, error handling, etc.

The structure led to spending more time on infrastructure code than on business logic.

## Alternatives Considered

### A. Keep raw RabbitMQ (improve custom consumer)
- Continue managing consumer, exchange, queue, connection/channel lifecycle, serialization, and retry logic manually
- Full control over the messaging layer
- Infrastructure code continues to dominate development time
- Every new task type requires repeating the same boilerplate

### B. Adopt Celery + SQS (chosen)
- Decorator-based task definition (`@task`) mirrors FastAPI's `@router` pattern
- Automatic message serialization, retry management, and task discovery
- SQS as broker leverages existing AWS infrastructure — no separate RabbitMQ server needed
- Trades low-level control for higher-level abstraction

## Decision

**Adopt Celery + SQS**

## Rationale

### 1. Decorator-Based Structure Similar to FastAPI

Celery's `@task` decorator + `autodiscover_tasks()` pattern is similar to FastAPI's `@router` + `include_router()` structure.

```python
# FastAPI — router registration
@router.post("/user")
async def create_user(...):
    ...

app.include_router(router=user_router.router, prefix="/v1")

# Celery — task registration
@shared_task(name="{project-name}.user.test")
def consume_task(**kwargs):
    ...

app.autodiscover_tasks(["src.user.interface.consumer.tasks"])
```

This maintained consistency with the existing project's architecture pattern (define handlers with decorators, register routing in bootstrap).

### 2. SQS Broker Support

Since we were already using AWS infrastructure, we could leverage SQS as a broker without needing to manage a separate RabbitMQ server. Celery reliably supported SQS as a broker through kombu.

### 3. Improved Abstraction Level

Compared to direct consumer implementation, Celery provided the following abstractions:
- Automatic message serialization/deserialization
- Configuration-based retry and timeout management
- Automated task discovery

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?

## Follow-up

After adopting Celery, we discovered the potential to share business logic between the API and Worker.
For example, we determined that simple CRUD logic like looking up user information by user ID could be reused across both API handlers and Worker tasks.

However, since all business logic in the project was written as `async def`,
calling it from Celery's sync tasks required `asyncio.run()`,
which caused event loop conflict issues.

This was identified as a structural limitation of Celery, leading to the migration to Taskiq.
-> [001. Migration from Celery to Taskiq](001-celery-to-taskiq.md)
