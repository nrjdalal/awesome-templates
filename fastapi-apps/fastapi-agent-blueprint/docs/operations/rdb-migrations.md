# RDB Migration Runbook

This project now uses Alembic for PostgreSQL schema changes.

## First Alembic Rollout

Revision `0001_baseline_current_rdb` represents the RDB schema that existed
before the first migration history was introduced. It creates the existing
`document` and `user` tables for fresh databases.

If an environment already has those tables because it was bootstrapped with
SQLAlchemy `create_all`, do not run `alembic upgrade head` directly. Stamp the
baseline first, then apply later migrations:

```bash
uv run alembic stamp 0001_baseline_current_rdb
uv run alembic upgrade head
```

For a fresh database with no existing RDB tables, run the normal upgrade:

```bash
uv run alembic upgrade head
```

## Rollback Note

Do not run `alembic downgrade base` in an environment that was stamped at the
baseline to preserve pre-existing tables. The baseline revision is a schema
baseline, not a data migration.
