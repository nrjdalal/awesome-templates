# 029. Broker Abstraction with providers.Selector for Multi-Backend Selection

- Status: Accepted
- Date: 2026-04-09
- Related issues: #8, #58
- Related ADRs: [000](000-rabbitmq-to-celery.md), [001](001-celery-to-taskiq.md), [023](023-object-storage-unification.md)

## Summary

To support switching between SQS, RabbitMQ, and InMemory brokers without code changes, we adopted `providers.Selector` from dependency-injector — a DI-native pattern where each broker backend is an isolated provider with only its own parameters, selected at container initialization by a configuration value.

## Background

- **Trigger**: Three concurrent needs surfaced around the same time:
  1. **Actual RabbitMQ requirement** — a deployment environment needed RabbitMQ instead of SQS
  2. **OSS preparation** — open-sourcing the project required removing the SQS assumption so adopters could bring their own broker
  3. **Local development friction** — developers had to configure SQS credentials even when they didn't need a real message queue, just to start the application

- **Decision type**: Experience-based correction — the initial implementation used a factory function with mixed parameters. During code review, the parameter mixing problem was discovered and the approach was corrected to `providers.Selector`.

### Broker Evolution Timeline

This decision continues the broker evolution across the project's history:

| ADR | Change | Broker |
|-----|--------|--------|
| [000](000-rabbitmq-to-celery.md) | Direct RabbitMQ → Celery | RabbitMQ (via Celery) |
| [001](001-celery-to-taskiq.md) | Celery → Taskiq | SQS (hardcoded) |
| **029 (this)** | SQS-only → Multi-broker | SQS / RabbitMQ / InMemory (config-driven) |

Notably, RabbitMQ returns as a supported option — not as the primary broker, but as one of several selectable backends behind a unified interface.

## Problem

### 1. Hardcoded SQS Broker

`CoreContainer` directly instantiated `CustomSQSBroker` with SQS-specific parameters. Switching to another broker backend required modifying infrastructure code.

```python
# Before: SQS hardcoded in CoreContainer
broker = providers.Singleton(
    CustomSQSBroker,
    queue_url=settings.aws_sqs_url,
    aws_region=settings.aws_sqs_region,
    aws_access_key_id=settings.aws_sqs_access_key,
    aws_secret_access_key=settings.aws_sqs_secret_key,
)
```

### 2. Required Configuration Even When Unused

SQS credentials (`AWS_SQS_ACCESS_KEY`, `AWS_SQS_SECRET_KEY`, `AWS_SQS_URL`) were required fields in Settings. Applications that didn't use a message queue — or used a different broker — still had to provide dummy SQS values to pass validation.

### 3. Different Classes, Not Just Different Parameters

Unlike the database engine switch (same `Database` class, different DSN) or the S3/MinIO switch (same `ObjectStorageClient` class, different `endpoint_url`), the broker backends are **completely different classes** from different packages:

| Backend | Class | Package |
|---------|-------|---------|
| SQS | `CustomSQSBroker` (extends `SQSBroker`) | `taskiq-aws` |
| RabbitMQ | `AioPikaBroker` | `taskiq-aio-pika` |
| InMemory | `InMemoryBroker` | `taskiq` (core) |

Each has a different constructor signature. This makes the problem fundamentally different from previous infrastructure abstractions in the project.

## Alternatives Considered

### A. Factory Function with Mixed Parameters (tried and rejected)

The initial implementation used a single `create_broker()` factory function:

```python
def create_broker(
    broker_type: str | None,
    aws_sqs_url: str | None = None,      # SQS-only
    aws_sqs_region: str | None = None,    # SQS-only
    aws_sqs_access_key: str | None = None, # SQS-only
    aws_sqs_secret_key: str | None = None, # SQS-only
    rabbitmq_url: str | None = None,       # RabbitMQ-only
) -> AsyncBroker:
    ...
```

**Why rejected**: This was the only component in `CoreContainer` using a factory function — every other component uses direct class instantiation (`providers.Singleton(ClassName, ...)`). The mixed parameter signature violated the project's DI conventions and would grow with each new broker (adding `redis_url`, `nats_url`, etc.). The pattern was inconsistent and non-scalable.

### B. Protocol-Based Abstraction

Define a `BrokerProtocol` interface and implement it for each backend.

**Why rejected**: Taskiq's `AsyncBroker` is already an ABC that all broker implementations inherit from. Adding a project-specific Protocol would be double-indirection with no additional value. The project does not use Protocol abstractions for infrastructure components — Protocols are reserved for the domain layer (e.g., `BaseRepositoryProtocol`).

### C. Separate Factory Functions per Broker Type

Create `create_sqs_broker()`, `create_rabbitmq_broker()`, `create_inmemory_broker()` and select the right one.

**Why rejected**: The individual functions are clean, but `CoreContainer` still needs a mechanism to select which function to call. `dependency_injector`'s `DeclarativeContainer` does not support conditional provider registration (`if/else` at class definition time). This pushes the selection logic back into a dispatcher function — arriving at the same mixed-parameter problem as Alternative A.

## Decision

### 1. providers.Selector for Broker Selection

`providers.Selector` is a first-class `dependency_injector` feature designed for exactly this use case — selecting between different providers based on a configuration value.

```python
broker = providers.Selector(
    lambda: (settings.broker_type or "inmemory").lower().strip(),
    sqs=providers.Singleton(
        create_sqs_broker,
        queue_url=settings.aws_sqs_url,
        aws_region=settings.aws_sqs_region,
        aws_access_key_id=settings.aws_sqs_access_key,
        aws_secret_access_key=settings.aws_sqs_secret_key,
    ),
    rabbitmq=providers.Singleton(
        create_rabbitmq_broker,
        url=settings.rabbitmq_url,
    ),
    inmemory=providers.Singleton(InMemoryBroker),
)
```

Each broker backend is an isolated `Singleton` provider with only its own parameters. No mixing. Adding a new backend (e.g., Redis) means adding one keyword argument — no existing providers are modified.

### 2. Optional Dependencies with Lazy Imports

Broker-specific packages are optional dependencies:

```toml
[project.optional-dependencies]
sqs = ["taskiq-aws>=0.4.0"]
rabbitmq = ["taskiq-aio-pika>=0.4.0"]
```

Each broker's factory wrapper uses lazy imports with clear error messages:

```python
def create_sqs_broker(...) -> AsyncBroker:
    try:
        from taskiq_aws import SQSBroker
        ...
    except ImportError:
        raise ImportError("taskiq-aws is required. Install with: uv sync --extra sqs")
```

This means a project using only InMemory broker needs zero broker-specific dependencies.

### 3. Strict Environment Enforcement

`BROKER_TYPE` is optional in local/dev (defaults to InMemory), but **required** in stg/prod — preventing accidental deployment with an in-process broker.

## Rationale

### Infrastructure Selection Decision Framework

This decision, combined with [ADR 023](023-object-storage-unification.md), establishes a clear framework for future infrastructure abstractions:

| Condition | Pattern | Example |
|-----------|---------|---------|
| Same class, different parameters | Parameter switching (endpoint_url, engine) | S3/MinIO (023), PostgreSQL/MySQL/SQLite (027) |
| **Different classes, different signatures** | **`providers.Selector`** | **SQS/RabbitMQ/InMemory (this ADR)** |

When evaluating future abstractions (e.g., #58 Storage type switching), this framework provides the decision criteria: if the backends share a class, use parameter-based configuration; if they require different classes, use `providers.Selector`.

### Why Not a Factory?

The factory approach works in isolation, but in the context of `dependency_injector`'s `DeclarativeContainer`, it creates an inconsistency:

| Component | CoreContainer Pattern |
|-----------|----------------------|
| Database | `providers.Singleton(Database, ...)` |
| HttpClient | `providers.Singleton(HttpClient, ...)` |
| S3 Client | `providers.Singleton(ObjectStorageClient, ...)` |
| DynamoDB | `providers.Singleton(DynamoDBClient, ...)` |
| Broker (factory) | `providers.Singleton(create_broker, mixed_params...)` |
| **Broker (Selector)** | **`providers.Selector(lambda, sqs=..., rabbitmq=..., inmemory=...)`** |

The Selector pattern keeps each sub-provider consistent with the established `Singleton(ClassName, class_params)` convention. The only new concept is the Selector wrapper itself.

### Selector Behavior Verified

- **Lazy instantiation**: Only the selected broker's Singleton is instantiated; unselected providers remain dormant
- **Singleton semantics preserved**: Repeated calls return the same instance (verified in tests)
- **Transparent to consumers**: `container.broker()` returns an `AsyncBroker` instance identically to the previous Singleton approach. No changes to `TaskiqManager`, `@broker.task()` decorators, or domain task code

### Trade-offs Accepted

- **New DI pattern**: `providers.Selector` is not used elsewhere in the project. Team members need to learn one additional pattern. Mitigated by the pattern being a documented `dependency_injector` feature with clear semantics.
- **Lazy import complexity**: Both `create_sqs_broker()` and `create_rabbitmq_broker()` define classes inside functions to avoid top-level imports of optional packages. This is less readable than top-level class definitions, but necessary for the optional dependency strategy.
- **No runtime broker switching**: The selector evaluates once at container creation. Changing `BROKER_TYPE` requires an application restart. This is acceptable because broker selection is an infrastructure decision, not a runtime concern.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
