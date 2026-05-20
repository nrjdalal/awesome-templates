# 017. Exception Handling Strategy: Native Handler over Middleware

- Status: Accepted
- Date: 2025-09 ~ 2026-03
- Related issue: #32
- Related ADR: [003](003-response-request-pattern.md)(Response/Request Pattern), [008](archive/008-deploy-env-separation.md)(Environment Configuration)

## Summary

To unify exception handling and avoid the pitfalls of Starlette's `BaseHTTPMiddleware`, we migrated from a custom `ExceptionMiddleware` to FastAPI's native `app.add_exception_handler()` with four typed handlers — while keeping environment-aware trace suppression.

## Background

- **Trigger**: The original `ExceptionMiddleware` (Starlette `BaseHTTPMiddleware`) was handling all exceptions in a single `dispatch()` method with cascading `if/elif` branches. As exception types grew (validation errors, HTTP errors, custom business errors, database errors), the middleware became a monolith that mixed error classification with response formatting.
- **Decision type**: Experience-based correction — the middleware approach was the initial implementation, and its limitations became apparent as the exception hierarchy grew.

The evolution went through several stages:

1. **Stage 1** (2025-09): Custom `ExceptionMiddleware` with `try/except` in `dispatch()` — handled all errors in one place
2. **Stage 2** (2025-10): Added `DatabaseException` to separate DB errors from generic exceptions, removed `HttpException` wrapper (redundant with Starlette's `HTTPException`)
3. **Stage 3** (2025-10): Added environment-aware traceback suppression (`settings.is_dev` controls whether stack traces appear in responses)
4. **Stage 4** (2026-03): Replaced the middleware entirely with `app.add_exception_handler()` — four dedicated handlers for four exception types

## Problem

### 1. Single Responsibility Violation

The `ExceptionMiddleware.dispatch()` method was responsible for catching, classifying, and formatting all exceptions. Adding a new exception type required modifying this single method, increasing coupling.

### 2. BaseHTTPMiddleware Limitations

Starlette's `BaseHTTPMiddleware` wraps the entire request/response cycle. When used for exception handling:
- Exceptions from other middleware could be double-wrapped
- StreamingResponse and WebSocket connections behave unexpectedly
- The middleware runs for every request, even when no exception occurs

### 3. Inconsistent with FastAPI's Design

FastAPI provides `add_exception_handler()` specifically for mapping exception types to handlers. Using middleware for this purpose bypasses FastAPI's built-in exception routing, making the codebase harder to understand for developers familiar with the framework.

## Alternatives Considered

### A. Keep ExceptionMiddleware with Better Organization

Refactor the middleware to use a handler registry pattern internally.

Rejected: This would re-implement what FastAPI already provides natively. The middleware wrapper overhead and `BaseHTTPMiddleware` limitations would remain.

### B. Use Exception Handler Middleware (Starlette built-in)

Starlette has a built-in `ExceptionMiddleware` that routes exceptions to handlers. FastAPI's `add_exception_handler()` wraps this internally.

Rejected as a direct approach: Using `app.add_exception_handler()` is the idiomatic FastAPI way to achieve the same result with a cleaner API.

### C. Dependency Injection for Error Handling

Use FastAPI's dependency system to inject error handlers.

Rejected: Exception handlers are cross-cutting concerns that apply globally, not per-route. Dependency injection would require repeating the handler in every router.

## Decision

Register four typed exception handlers via `app.add_exception_handler()` in `bootstrap.py`:

```python
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(BaseCustomException, custom_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
```

Each handler is a standalone async function in `_core/exceptions/exception_handlers.py`:

| Handler | Exception Type | Purpose |
|---------|---------------|---------|
| `validation_exception_handler` | `RequestValidationError` | Pydantic validation failures → 422 with field-level details |
| `http_exception_handler` | `StarletteHTTPException` | Standard HTTP errors (404, 403, etc.) |
| `custom_exception_handler` | `BaseCustomException` | Business logic errors with structured error codes |
| `generic_exception_handler` | `Exception` | Catch-all with environment-aware trace suppression |

All handlers return a consistent `ErrorResponse` format (defined in ADR 003).

The generic handler uses `settings.is_dev` to control trace exposure:
- **Development**: includes full stack trace in `error_details.trace`
- **Production**: returns only "Internal server error" with no internal details

## Rationale

| Decision | Reason |
|----------|--------|
| Four dedicated handlers | Each exception type has distinct response formatting needs. One handler per type is easier to test, modify, and understand |
| `app.add_exception_handler()` over middleware | FastAPI's native mechanism — no `BaseHTTPMiddleware` overhead, no double-wrapping risk, framework-endorsed pattern |
| `BaseCustomException` hierarchy | Domain-specific exceptions (e.g., `DatabaseException`, `ExternalServiceException`) extend this base, inheriting `status_code`, `message`, `error_code`, and `details` |
| Environment-aware trace in generic handler only | Validation, HTTP, and custom exceptions have predictable formats. Only unexpected exceptions need trace information for debugging |
| Handlers in `_core/exceptions/` | Cross-cutting concern shared by all apps (Server, Worker, Admin) — belongs in core infrastructure |

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
