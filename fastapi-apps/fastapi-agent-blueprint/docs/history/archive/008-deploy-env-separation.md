# 008. Deployment Environment Separation and Configuration Management

- Status: Accepted
- Date: 2025-09-15
- Related Issues: #26, #38
- Related PRs: #30
- Related Commits: `abe8a6f`, `21fd076`

## Summary

To prevent security-sensitive information (Swagger docs, stack traces) from being exposed in production, we introduced pydantic-settings based per-environment configuration, replacing the existing config.yml approach.

## Background

- **Trigger**: While preparing for production deployment, Swagger UI and detailed error stack traces were discovered to be publicly accessible — a security issue requiring per-environment behavior control.
- **Decision type**: Upfront design — addressed proactively during production preparation, before any actual exposure incident.

As the project prepared for production deployment, settings that needed to behave differently per environment emerged.
In particular, there was a security issue where Swagger docs and error messages were exposed as-is in production.

## Problem

### 1. Swagger Documentation Exposed in Production

Without distinguishing between development and production environments, Swagger UI (`/docs-swagger`) and ReDoc (`/docs-redoc`) were always exposed.
When API documentation is publicly accessible in production, internal information such as endpoint structure, parameters, and response formats is revealed.

### 2. Indiscriminate Error Message Exposure

When errors occurred, stack traces and detailed error information were returned to clients regardless of environment,
creating a security issue where internal implementation details were exposed in production.

### 3. Configuration File Management Approach

Configuration was previously managed via `config.yml`,
which required a separate YAML parser and could not benefit from IDE auto-completion or type validation.

## Alternatives Considered

### A. Keep config.yml
- Already in use, familiar to the team
- Requires separate PyYAML parser
- No type validation, no IDE auto-completion, no automatic env variable binding

### B. .env files + python-dotenv
- Simple key=value format, widely used
- No type validation — all values are strings
- Requires manual parsing and type conversion
- Does not integrate with Pydantic's validation ecosystem

### C. pydantic-settings (chosen)
- Automatic type conversion and validation
- IDE auto-completion and type hints
- Automatic environment variable binding (12-Factor App)
- Same `.py` file format as the rest of the codebase — managed with the same tools (linter, type checker)

## Decision

### Introduced pydantic-settings Based Environment Configuration

Removed `config.yml` and created a `Settings` class using `pydantic-settings`.

```python
# src/_core/config.py (commit abe8a6f)
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: str = "local"
    # Control docs URL per environment
    # local/dev: Swagger UI exposed
    # prod: None (hidden)
```

### Per-Environment API Documentation Control

```python
# src/app.py
settings = Settings()
app = FastAPI(
    docs_url="/docs-swagger" if settings.env != "prod" else None,
    redoc_url="/docs-redoc" if settings.env != "prod" else None,
)
```

### Per-Environment Error Message Control

The ExceptionMiddleware was modified to determine whether to include error traces based on the environment.

## Rationale

| Criterion | config.yml | pydantic-settings |
|-----------|-----------|-------------------|
| Type validation | None (strings) | Automatic type conversion/validation |
| IDE support | None | Auto-completion, type hints |
| Env variable binding | Requires separate code | Automatic binding |
| Parser dependency | PyYAML required | Not needed (built into Pydantic) |
| Management format | `.yml` file | `.py` file (same as code) |

1. **Security was the primary motivation**: Per-environment control of docs exposure and error message exposure in production
2. Managing settings as `.py` files enables management with the same tools as code (IDE, linter, type checker)
3. `pydantic-settings` automatically binds environment variables, aligning with the 12-Factor App principles

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
