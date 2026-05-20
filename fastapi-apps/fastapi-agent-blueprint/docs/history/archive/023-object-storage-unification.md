# 023. Object Storage Unification: MinIO to S3 via aioboto3

- Status: Accepted
- Date: 2025-10
- Related ADR: [009](../009-async-external-clients.md)(Async External Clients)

## Summary

To avoid maintaining separate storage abstractions for local and production environments, we unified object storage under a single S3-compatible interface using aioboto3 — where `endpoint_url` configuration switches between local MinIO and production AWS S3 without code changes.

## Background

- **Trigger**: The project initially used MinIO (synchronous client) for local file storage and had separate configuration for AWS S3 in production. ADR 009 mandated async clients, requiring the synchronous MinIO client to be replaced. Rather than replacing it with an async MinIO client, we evaluated whether a single S3-compatible interface could serve both environments.
- **Decision type**: Upfront design, building on ADR 009's async mandate — designing the storage layer to avoid environment-specific code paths.

MinIO implements the S3 API protocol. This means any S3 client can interact with MinIO if configured with the correct `endpoint_url`. This compatibility property was the key insight.

## Problem

### 1. Dual Client Maintenance

Two separate storage implementations (MinIO client for local, S3 client for production) doubled the testing surface and introduced divergent behavior risks.

### 2. Synchronous Blocking

The original MinIO client (`minio` package) was synchronous, blocking the async event loop during file operations — the same problem ADR 009 solved for HTTP clients.

### 3. Environment-Specific Code Paths

Code that behaves differently in local vs production environments is a source of "works on my machine" bugs.

## Alternatives Considered

### A. Async MinIO Client + S3 Client (Dual Implementation)

Replace synchronous MinIO with an async MinIO client and keep separate S3 client for production.

Rejected: MinIO implements S3 API — two clients for the same protocol is unnecessary. Maintaining two implementations increases the chance of behavioral divergence between environments.

### B. Abstract Storage Interface with Multiple Backends

Define a `StorageProtocol` with `MinIOStorage` and `S3Storage` implementations.

Rejected: Over-abstraction when both backends speak the same protocol. The abstraction provides no value when the underlying API is identical — only the endpoint URL differs.

### C. Mock Storage for Local Development

Use in-memory or filesystem-based mock storage locally, real S3 in production.

Rejected: Mock storage cannot verify S3-specific behaviors (presigned URLs, content types, bucket policies). Testing with a real S3-compatible server (MinIO) catches more issues.

## Decision

A two-class architecture using aioboto3:

**`ObjectStorageClient`** — manages the aioboto3 session and S3 client lifecycle:

```python
class ObjectStorageClient:
    def __init__(self, access_key, secret_access_key, region_name, endpoint_url=None):
        self.session = aioboto3.Session(...)
        self.endpoint_url = endpoint_url  # None for AWS S3, URL for MinIO

    @asynccontextmanager
    async def client(self):
        async with self.session.client("s3", endpoint_url=self.endpoint_url) as s3_client:
            yield s3_client
```

**`ObjectStorage`** — business-level operations (upload, download, delete, presigned URLs):

```python
class ObjectStorage:
    def __init__(self, storage_client: ObjectStorageClient, bucket_name: str):
        ...
```

**Environment switching** via configuration:
- **Local**: `endpoint_url=http://localhost:9000` (MinIO)
- **Production**: `endpoint_url=None` (defaults to AWS S3)

No code changes, no if/else, no environment checks — the same code path runs in all environments.

## Rationale

| Decision | Reason |
|----------|--------|
| aioboto3 over async MinIO client | aioboto3 speaks native S3 protocol. One client for both MinIO and AWS S3. No need for a MinIO-specific dependency |
| `endpoint_url` for environment switching | S3 API compatibility means the only difference between MinIO and AWS is the endpoint. Configuration, not code, handles the switch |
| Two-class separation (Client + Storage) | Client handles connection lifecycle (session, credentials, endpoint). Storage handles business operations (upload, download). Separation of concerns enables independent testing |
| Context manager for client access | S3 clients are resource-heavy. Context manager ensures proper cleanup after each operation, preventing connection leaks |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
