# 027. Flexible RDB Configuration with Multi-Engine Support

- Status: Accepted
- Date: 2026-04-08
- Related Issues: #7, #29
- Related ADRs: 008-deploy-env-separation.md (extension)

## Summary

To support multiple database engines (PostgreSQL, MySQL, SQLite) without code changes and tune connection pools per environment, we introduced a `DATABASE_ENGINE` setting with automatic driver mapping and environment-profiled pool defaults.

## Background

- **Trigger**: The project was hardcoded to PostgreSQL with a single connection configuration for all environments. Issue #7 requested multi-engine flexibility, and issue #29 flagged the need for per-environment DB separation. Additionally, the test suite required SQLite for lightweight in-memory testing, but the Database class constructor assumed PostgreSQL-style DSN parameters.
- **Decision type**: Upfront design — planned before adding new team members who may use different local database setups.

ADR 008 established pydantic-settings as the configuration management approach, but database-specific settings (engine type, driver selection, pool tuning) were not addressed. The Database class accepted raw DSN strings, and the Alembic migration environment was hardcoded to PostgreSQL.

## Problem

### 1. Single-Engine Lock-In

The Database class constructed DSNs assuming PostgreSQL format. Running the project with MySQL or SQLite required manual DSN construction and code modification.

### 2. One-Size-Fits-All Pool Configuration

Connection pool parameters (pool_size, max_overflow, echo) were identical across all environments. Local development ran with production-grade pool settings, and production had no timeout protections against long-running queries.

### 3. Test Environment Friction

Tests required patching the Database class's `__new__` method to inject SQLite, because the constructor had no clean way to switch engines. This hack bypassed normal initialization and made test failures harder to diagnose.

### 4. Alembic Migration Coupling

`alembic.ini` hardcoded the environment to `local`, requiring manual editing or environment variable overrides to run migrations in dev/stg/prod.

## Alternatives Considered

### A. Hardcoded DSN per Environment

Provide complete DSN strings (e.g., `DATABASE_URL=postgresql+asyncpg://...`) in each `.env` file.

- **Pros**: Maximum flexibility, no mapping logic needed
- **Cons**: Duplicates driver knowledge in every environment file. Team members must know the correct async/sync driver names. Typos in DSN strings cause cryptic connection errors. Cannot provide engine-aware pool defaults.
- **Why not**: Shifts configuration complexity to every team member and every environment file. With 4 environments x 2 DSNs (async + sync), that's 8 DSN strings to maintain correctly.

### B. ORM-Level Multi-Backend Abstraction

Use an ORM wrapper library (e.g., databases, encode/databases) that abstracts the backend.

- **Pros**: Clean API, hides driver details
- **Cons**: Adds another dependency. SQLAlchemy already supports multiple backends natively. The abstraction layer may lag behind SQLAlchemy features (e.g., server-side cursors, advisory locks).
- **Why not**: SQLAlchemy's engine/driver system is already the standard for multi-backend support. Adding another layer provides no benefit over configuring SQLAlchemy directly.

### C. Engine Auto-Detection from DSN (chosen approach, refined)

Declare `DATABASE_ENGINE` as a high-level setting (e.g., `postgresql`, `mysql`, `sqlite`) and auto-map to the correct async/sync driver pairs. Combine with environment-profiled pool defaults.

- **Pros**: Single setting controls the entire database stack. Engine-specific pool tuning and connect_args applied automatically. Clean test setup (set engine=sqlite, done).
- **Cons**: Limited to the engines explicitly mapped in the driver dictionaries. Adding a new engine requires updating the mapping.
- **Why chosen**: The mapping is a ~10-line dictionary, trivially extensible. The benefit of automatic driver selection and engine-aware configuration outweighs the small maintenance cost.

## Decision

### 1. DATABASE_ENGINE Setting with Automatic Driver Mapping

Added `DATABASE_ENGINE` to Settings (via `DATABASE_ENGINE` env var). The Database module maintains two driver dictionaries:

```python
ASYNC_DRIVERS = {"postgresql": "asyncpg", "mysql": "aiomysql", "sqlite": "aiosqlite"}
SYNC_DRIVERS  = {"postgresql": "psycopg",  "mysql": "pymysql",  "sqlite": ""}
```

DSN construction uses `_build_dsn(engine, driver, ...)` which handles engine-specific formats (e.g., SQLite's `sqlite:///` path-based DSN vs. host-based DSN for others).

### 2. Environment-Profiled Pool Defaults

`DatabaseConfig.from_env()` selects pool defaults based on environment:

| Setting | local/dev | stg/prod |
|---------|-----------|----------|
| echo | True | False |
| pool_size | 5 | 10 |
| max_overflow | 10 | 20 |

### 3. Engine-Specific Connect Args for Strict Environments

Production-like environments (stg, prod) receive engine-specific connect_args:

- **PostgreSQL**: `timeout=10`, `command_timeout=30`, `statement_timeout=30s`, `idle_in_transaction_session_timeout=5min`
- **MySQL**: `connect_timeout=10`, `read_timeout=30`, `write_timeout=30`
- **SQLite**: No connect_args (not used in production)

### 4. Env Var Overrides for Pool Tuning

`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_RECYCLE`, `DATABASE_ECHO` override profile defaults when set, allowing fine-tuning without changing code.

### 5. SQLite Compatibility

SQLite does not support connection pooling. The engine kwargs builder (`_engine_kwargs`) automatically excludes `pool_size`, `max_overflow`, and `pool_pre_ping` when the engine is SQLite.

### 6. Alembic Environment Variable Integration

Replaced `alembic.ini` hardcoded env with `ENV` environment variable resolution. `migrations/env.py` loads the corresponding `_env/{env}.env` file and uses `create_sync_dsn()` with the declared engine.

## Rationale

1. **Single source of truth**: `DATABASE_ENGINE` is the only setting a developer needs to change to switch databases. Driver selection, DSN format, pool defaults, and connect_args all derive from it.
2. **Defense-in-depth for production**: Statement timeouts and connection timeouts prevent runaway queries and connection leaks in stg/prod, while keeping local development fast and verbose.
3. **Clean test setup**: Tests set `database_engine=sqlite` with an in-memory database, eliminating the `__new__` patching hack. The standard constructor path is exercised in tests.
4. **Extensibility**: Adding a new engine (e.g., CockroachDB) requires only adding entries to the driver dictionaries and optionally adding connect_args — no structural changes needed.

### Trade-offs Accepted

- **Limited engine support**: Only PostgreSQL, MySQL, and SQLite are mapped. Other engines require explicit driver registration. Acceptable because these three cover >95% of use cases for this project's target audience.
- **Connect_args not configurable via env vars**: Engine-specific timeout values are hardcoded in `_build_connect_args()`. If per-deployment tuning is needed, this can be extended later. Currently, the values represent reasonable production defaults.
- **Sync driver for Alembic**: Alembic uses synchronous connections via `create_sync_dsn()`. This is a known Alembic limitation, not a design choice.

### Self-check
- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale and team situation?
- [x] Will a reader understand "why" 6 months from now without additional context?
- [x] Am I recording the decision process, or justifying a conclusion I already reached?
