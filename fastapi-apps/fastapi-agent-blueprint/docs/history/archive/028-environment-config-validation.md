# 028. Environment-Aware Configuration Validation

- Status: Accepted
- Date: 2026-04-08
- Related Issues: #53
- Related PRs: #54
- Related ADRs: 008-deploy-env-separation.md (extension)

## Summary

To prevent misconfigured deployments from reaching production, we added a `@model_validator` to the Settings class that rejects unsafe default values in strict environments (stg/prod), detects partial service configurations, and converts network policy from hardcoded properties to environment-configurable fields.

## Background

- **Trigger**: During production preparation, we discovered that the Settings class accepted dangerous default values (e.g., `admin_password=admin`, `database_host=localhost`) without any warning or error — even when `env=prod`. A developer could deploy to production with placeholder credentials simply by forgetting to set environment variables.
- **Decision type**: Experience-based correction — identified during pre-production review, before an actual incident.

ADR 008 introduced pydantic-settings for type-safe configuration, but it only validated types (string, int, bool), not semantic safety. A well-typed but semantically unsafe configuration (e.g., `database_password="postgres"` in production) passed validation silently.

## Problem

### 1. Unsafe Defaults Accepted in Production

Default values intended for local development (e.g., `admin_password=admin`, `database_host=localhost`) were accepted in all environments. There was no mechanism to distinguish "developer forgot to set this" from "developer intentionally chose this value."

### 2. Partial Service Configurations

S3 and MinIO require multiple coordinated fields (access_key, secret_key, bucket_name, etc.). Setting some fields but not others produced cryptic runtime errors instead of clear startup failures.

### 3. Hardcoded Network Policy

`allowed_hosts` and `allow_origins` were computed as `@property` methods with hardcoded values. Changing CORS or host policies required code changes and redeployment, rather than environment variable adjustment.

## Alternatives Considered

### A. External Validation Tool (e.g., pydantic-settings-vault, config linter)

Run a separate validation step before deployment (CI/CD pipeline check or pre-deploy script).

- **Pros**: Decoupled from application code. Can validate across multiple services.
- **Cons**: Validation happens outside the application — a direct `python main.py` or container start bypasses it. Adds CI/CD dependency and another tool to maintain.
- **Why not**: Configuration safety must be enforced at the application boundary, not as an optional pipeline step. If the app starts, it must be safe.

### B. Silent Defaults with Logging Warnings

Accept defaults in all environments but log warnings for potentially unsafe values.

- **Pros**: Non-breaking. Existing deployments continue to work.
- **Cons**: Warnings are easily missed in log streams. A running production service with `admin_password=admin` is a security incident regardless of log warnings.
- **Why not**: Security-critical misconfigurations should fail loudly, not log quietly. We use warnings only for non-critical defaults (e.g., `task_name_prefix`).

### C. Fail-Fast with `@model_validator` (chosen)

Validate semantic safety inside the Settings class itself, raising `ValueError` at startup when dangerous conditions are detected.

- **Pros**: Enforced on every startup path (server, worker, admin, tests). No external tooling dependency. Clear error messages listing all violations at once.
- **Cons**: Adds validation logic to the Settings class. May need updates as new fields are added.
- **Why chosen**: The application itself is the only reliable enforcement point. pydantic's `@model_validator` runs after all fields are resolved (including env var binding), making it the ideal place for cross-field semantic validation.

## Decision

### 1. Strict Environment Validation

Added `@model_validator(mode="after")` to Settings that:

- **Rejects unsafe defaults in stg/prod**: Checks `admin_password`, `admin_storage_secret`, `database_password`, `database_host` against known unsafe defaults. Raises `ValueError` listing all violations.
- **Validates known values**: Checks `env` against `KNOWN_ENVS` and `database_engine` against `KNOWN_ENGINES`.
- **Warns on placeholder values**: Non-critical defaults (e.g., `task_name_prefix=my-project`) emit `warnings.warn()` instead of raising errors.

### 2. Partial Configuration Detection

Validates that S3 and MinIO field groups are either fully configured or fully absent:

```python
s3_set = {k for k, v in s3_fields.items() if v is not None}
if s3_set and s3_set != set(s3_fields):
    errors.append(f"[S3] Partial configuration: ... set but ... missing")
```

This catches the common mistake of setting `S3_ACCESS_KEY` but forgetting `S3_BUCKET_NAME`.

### 3. Network Policy as Environment Fields

Converted `allowed_hosts` and `allow_origins` from `@property` methods to `list[str]` fields with `validation_alias`:

```python
allowed_hosts: list[str] = Field(default=["localhost", "127.0.0.1"], validation_alias="ALLOWED_HOSTS")
allow_origins: list[str] = Field(default=["*"], validation_alias="ALLOW_ORIGINS")
```

Network policies are now configurable via `ALLOWED_HOSTS` and `ALLOW_ORIGINS` environment variables without code changes.

## Rationale

1. **Defense-in-depth**: Even if deployment scripts or CI/CD miss a configuration error, the application itself refuses to start with unsafe settings. This is the last line of defense before a misconfigured service accepts traffic.
2. **All-at-once error reporting**: The validator collects all errors before raising, so developers see every issue in a single startup failure — not a fix-one-restart-find-next cycle.
3. **Graduated severity**: Critical misconfigurations (unsafe passwords in prod) raise errors. Non-critical defaults (placeholder task prefix) emit warnings. This prevents alert fatigue while maintaining strict safety boundaries.
4. **Network policy flexibility**: Converting to fields follows the same pattern as all other configurable settings (ADR 008). Operations teams can adjust CORS and host allowlists per environment without developer involvement.

### Trade-offs Accepted

- **Unsafe default list requires maintenance**: When new sensitive fields are added, the `_UNSAFE_DEFAULTS` dictionary must be updated manually. Forgetting to add a new field means it won't be validated. Mitigated by code review convention.
- **No runtime re-validation**: Validation runs only at startup. If environment variables change at runtime (unlikely in container deployments), the running process won't detect it. Acceptable because container-based deployments recreate the process on configuration changes.
- **local/dev environments are permissive**: Unsafe defaults are only rejected in stg/prod. A developer running locally with `env=local` won't see errors for placeholder values. This is intentional — developer convenience in local outweighs strict safety.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
