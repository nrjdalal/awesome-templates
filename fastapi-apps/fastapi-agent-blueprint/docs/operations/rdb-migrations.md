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

## Zero-Downtime Migrations

> Background: [ADR 056](../history/056-zero-downtime-migration-safety.md).
> The advisory checker `tools/check_migration_safety.py` flags the unsafe
> patterns in this section automatically at revision-review time (and via a
> non-blocking pre-commit hook). Treat it as a reminder, not a gate — the
> tables below are the reasoning behind each warning.

When the service is deployed with no downtime (rolling / blue-green), a
migration runs **while the previous app version is still serving traffic**. A
safe migration therefore has two independent properties:

1. **It does not hold a long lock.** A statement that takes an `ACCESS
   EXCLUSIVE` lock (or rewrites the whole table) stalls reads/writes for the
   duration — a stall is downtime.
2. **It keeps the old app version working.** Dropping or renaming a column that
   the still-running old version reads breaks that version mid-deploy.

Frequent migrations are fine. Migrations that violate either property are not.

### The expand-contract pattern

Any change that would break property 2 (drop, rename, type change, tightening a
constraint) is split across **separate deploys** so the app and schema are
always mutually compatible:

1. **Expand** — add the new shape additively (nullable column, new table,
   `CONCURRENTLY` index). The old app version is untouched and keeps working.
2. **Backfill + dual-run** — copy data into the new shape in batches (not one
   big `UPDATE`), and ship an app version that writes both shapes and reads the
   new one with a fallback to the old.
3. **Contract** — once no running app version references the old shape, a later
   migration removes it.

Example — renaming `user.full_name` to `user.display_name` with no downtime:

```text
Deploy 1 (expand):   add nullable `display_name`; app writes both, reads full_name
Deploy 2 (backfill): batch-copy full_name -> display_name; app reads display_name
Deploy 3 (contract): drop `full_name`
```

A single `alter_column(new_column_name=...)` collapses all three into one step
and breaks Deploy-0 traffic. Split it.

### Safe vs unsafe DDL by engine

PostgreSQL is the first-class production target; MySQL/SQLite differences are
annotated. SQLite is the dev/quickstart engine here and is **not** a
zero-downtime target — its `ALTER` support is limited and most changes rebuild
the table, so validate schema changes against the production engine.

| Operation | PostgreSQL | MySQL 8.0 (InnoDB) | Safe alternative |
|---|---|---|---|
| Add nullable column, no default | ✅ metadata only | ✅ `INSTANT` | — |
| Add column with **constant** default | ✅ safe on PG 11+ (fast default) | ✅ `INSTANT` (8.0.12+) | pre-11 / volatile default rewrites the table |
| Add `NOT NULL` column, no default | ❌ fails on existing rows | ❌ | add nullable → backfill → `SET NOT NULL` (validated) |
| Add `NOT NULL` column with constant default | ⚠️ PG 11+ only; volatile/​pre-11 = full rewrite + `ACCESS EXCLUSIVE` | ⚠️ mostly `INSTANT`, else rebuild | prefer nullable + backfill for large tables |
| Create index (blocking) | ❌ `SHARE` lock blocks writes | ⚠️ `INPLACE`, allows DML but can be slow | `CREATE INDEX CONCURRENTLY` (PG); Alembic: `op.create_index(..., postgresql_concurrently=True)` in a non-transactional revision |
| Drop column | ⚠️ fast, but breaks old app version | ⚠️ `INSTANT` 8.0.29+, else rebuild | expand-contract (drop only after no version reads it) |
| Rename column / table | ❌ breaks app compatibility window | ❌ same | expand-contract (add new → dual-write → drop old) |
| Change column type | ❌ table rewrite + `ACCESS EXCLUSIVE` | ⚠️ often `COPY` (blocking) | add new-typed column → backfill → swap → drop |
| `SET NOT NULL` on existing column | ⚠️ full table scan (PG 12+ skips it if a validated `CHECK` exists) | ⚠️ rebuild | add `CHECK (col IS NOT NULL) NOT VALID` → `VALIDATE` → `SET NOT NULL` |
| Add foreign key / check constraint | ⚠️ validation takes a lock | ⚠️ rebuild/validate | `ADD CONSTRAINT ... NOT VALID` then `VALIDATE CONSTRAINT` (separate step) — FK/CHECK only |
| Add unique constraint | ⚠️ builds a unique index under lock (`NOT VALID` does **not** apply to UNIQUE) | ⚠️ rebuild | `CREATE UNIQUE INDEX CONCURRENTLY` then `ALTER TABLE ... ADD CONSTRAINT ... USING INDEX` |
| Create table / drop empty table | ✅ safe (no existing rows) | ✅ safe | — |

`CREATE INDEX CONCURRENTLY` cannot run inside a transaction, so the Alembic
revision must disable the per-migration transaction and can leave an **invalid
index** if it fails partway — re-drop and retry rather than reusing it.

MySQL's `INSTANT`/`INPLACE` eligibility is **conditional** — it depends on the
exact 8.0 minor version, the column position, and table features, and there is
a per-table cap on `INSTANT` changes. If the requested algorithm is not
supported the server can fall back to a blocking `COPY`. Request it explicitly
(`ALGORITHM=INSTANT`/`INPLACE, LOCK=NONE`) so the engine errors instead of
silently copying, and redesign the change if it is rejected.

### Backfilling

- Backfill in **bounded batches** (`WHERE id BETWEEN ...`), not a single
  `UPDATE` over the whole table — one big statement holds locks and floods
  replication.
- Keep heavy backfills **out of the Alembic revision** when the table is large;
  run them as a separate batched job so a slow backfill never blocks the
  schema-migration deploy.

### Rollback

- **Expand** steps are additive and roll back cleanly.
- **Contract** steps (drops) are effectively irreversible without data loss —
  prefer forward-fix over `downgrade` for a contract that already shipped.
- Always keep `downgrade()` correct for expand/backfill steps so a bad deploy
  can be reversed before the contract stage.
