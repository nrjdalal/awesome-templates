# 009. Standardizing Async External Clients

- Status: Accepted
- Date: 2025-10-15 ~ 2025-10-21
- Related Issues: #37, #43
- Related PRs: #39, #40, #44
- Related Commits: `199f9c2`, `fbf2a3c`, `d70ee0e`

## Summary

To prevent synchronous I/O from blocking the async event loop, we replaced httpx (sync) and minio with aiohttp and aioboto3 — unifying the entire stack as async.

## Background

- **Trigger**: Synchronous HTTP and S3 clients were blocking the event loop inside `async def` handlers, preventing other requests from being processed during I/O waits.
- **Decision type**: Experience-based correction — the event loop blocking was observed as concurrent requests increased.

The entire project stack is async-based:
- FastAPI router handlers use `async def`
- SQLAlchemy 2.0 async engine + asyncpg
- dependency-injector async providers

However, synchronous clients were being used for external service calls:
- HTTP calls: httpx (synchronous mode)
- S3 file storage: minio (synchronous client)

## Problem

### Synchronous Clients Blocking the Event Loop

FastAPI runs `async def` handlers on the asyncio event loop.
When synchronous HTTP/S3 calls are made within these handlers, the event loop
is blocked until the call completes, preventing other requests from being processed.

```
Request A: [handler start] ... [sync HTTP call <- blocking] ... [response]
Request B:                     [waiting <--------------------] ... [handler start]
```

With async clients, the event loop can process other requests during I/O waits:

```
Request A: [handler start] ... [await HTTP call] ........ [response]
Request B:                     [handler start] ... [await other work] ... [response]
```

This difference becomes a performance bottleneck as concurrent requests increase.

## Decision

### 1. Introduced aiohttp-Based HTTP Client (#37)

An aiohttp-based async HTTP client was implemented in `src/_core/infrastructure/http/http_client.py`.

A Gateway pattern was also introduced to abstract external API calls:
- Before: `http_repository` -- a name that was confused with DB repositories
- After: `gateway` -- a name that matches the role of handling communication with external systems

```
src/_core/infrastructure/
├── http/
│   └── http_client.py          # aiohttp wrapper (session management, retries)
└── gateways/
    └── example_gateway.py      # Per-external-API gateway
```

### 2. Switched to aioboto3-Based S3 Client (#43)

Replaced the minio synchronous client with the aioboto3 async client.

```
# Before: minio (synchronous)
src/_core/domain/services/s3_service.py  # Synchronous S3 calls

# After: aioboto3 (asynchronous)
src/_core/infrastructure/storage/
├── s3_client.py       # aioboto3 session management
└── s3_storage.py      # Async file upload/download/delete
src/_core/domain/services/file_storage_service.py  # Storage abstraction
```

## Alternatives Considered

### HTTP Client

#### A. httpx (AsyncClient)
- Recommended by FastAPI official docs for testing
- Supports async via `httpx.AsyncClient`
- Identical sync/async interface makes transition easy
- HTTP/2 support, requests-compatible interface
- Overhead from dual sync/async design reduces pure async performance

#### B. aiohttp (chosen)
- The de facto standard for Python async HTTP (the oldest and most proven library)
- Mature connection pool management
- **Superior pure async performance compared to httpx** -- designed exclusively for async from the start
- Also supports WebSocket clients
- No HTTP/2 support (not needed currently)

| Criterion | httpx | aiohttp |
|-----------|-------|---------|
| Async performance | Overhead from dual sync/async design | Async-only design, higher throughput |
| Connection pool | Supported | More mature implementation |
| HTTP/2 | Supported | Not supported |
| Interface | requests-compatible | Custom API |
| Ecosystem | Primarily used in FastAPI testing | Most widely used production async HTTP client |

This project's entire stack is async, and the HTTP client needs high concurrency for production workloads. Since HTTP/2 is not immediately needed, performance takes priority, so aiohttp was chosen.

### S3 Client

#### A. Keep minio (sync)
- Already integrated and working
- Designed for self-hosted MinIO servers, not AWS-native
- Synchronous — blocks the event loop in async handlers

#### B. aioboto3 (chosen)
- AWS-native async client
- Unifies with other AWS services (SQS, etc.)
- Non-blocking I/O consistent with the rest of the stack

## Rationale

| Criterion | Synchronous Clients (before) | Async Clients (current) |
|-----------|------------------------------|-------------------------|
| Event loop | Blocking | Non-blocking |
| Concurrency | Cannot process other requests during I/O wait | Can process other requests during I/O wait |
| Stack consistency | Sync calls mixed within async handlers | Entire stack unified as async |
| S3 tool | minio (sync, designed for self-hosted servers) | aioboto3 (async, AWS native) |

1. Synchronous I/O calls in async FastAPI block the event loop, degrading concurrent processing performance
2. Unifying the entire stack as async reduces the likelihood of event-loop-related bugs
3. The minio to aioboto3 transition enables unifying clients with other AWS services like AWS SQS

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
