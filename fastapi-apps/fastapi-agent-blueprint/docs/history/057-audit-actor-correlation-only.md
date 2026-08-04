# 057. Admin Audit Actor — Correlation-Only, No Foreign Key

- Status: Accepted
- Date: 2026-08-04
- Issue: [#348](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/348)
- Supersedes: the `admin_audit_log.admin_user_id` constraint introduced in migration `0007`
- Related: [ADR 049](049-admin-identity-realm-separation.md) (realm separation), [ADR 042](042-optional-infrastructure-di-pattern.md) (optional infra), [ADR 056](056-zero-downtime-migration-safety.md) (migration safety)

## Summary

`admin_audit_log.admin_user_id` is a plain nullable integer holding an
`admin_identity.id`, with **no foreign key**. Referential expectations moved from
the DDL to the read path and to CI. The swallowed audit-write failure it was
hiding became loud in the same change.

## Background

### Trigger

Enabling the PostgreSQL CI matrix leg for [#333](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/333)
failed two audit tests immediately:

```
asyncpg.exceptions.ForeignKeyViolationError: insert or update on table "admin_audit_log"
violates foreign key constraint "admin_audit_log_admin_user_id_fkey"
DETAIL:  Key (admin_user_id)=(1) is not present in table "user".
```

Migration `0007` created the column as
`FOREIGN KEY (admin_user_id) REFERENCES "user" (id) ON DELETE SET NULL`. Since
ADR 049 / #218 the value written at runtime is an `admin_identity.id`:
`AdminAuthUseCase._admin_session_for` sets `user_id=admin.id` from an
`AdminIdentityDTO`, and `AdminAuditLogger` reads it back from the NiceGUI
session.

### Why it went unnoticed for two releases

Two independent silences compounded:

- **SQLite does not enforce foreign keys** unless `PRAGMA foreign_keys=ON`, which
  nothing in `src/` or `tests/` sets. CI only ever ran SQLite (#333).
- **`AuditLogger.log` swallowed the violation.** The fallback logged at
  `warning` with `action`, `domain`, `result` and `error_type` only, and its own
  comment claimed the dropped event was "reconstructable from these
  non-sensitive fields" — while omitting the actor and the target. Nothing
  alerted.

### Production impact before this ADR

Only the two login-failure paths pass `admin_user_id=None`; every authenticated
action carries a non-null `admin_identity.id`. On PostgreSQL and MySQL that means
**rejected logins were recorded and successful admin actions were not**. An
operator reading `admin_audit_log` saw a list of failed logins and no indication
that anything was missing — which reads as a complete trail in which no admin
ever did anything.

## Problem

Three distinct properties were in conflict:

1. An audit trail must record what happened, and must not lose events.
2. The actor id must not be able to mean two different things.
3. `_core` must not depend on a bounded context's schema.

The `0007` constraint satisfied none of them.

## Alternatives Considered

### A. Repoint the constraint at `admin_identity.id` — rejected

The obvious fix, and the one the repo owner's instinct favoured. Rejected on two
verified grounds.

**It can certify a falsehood.** Migration `0009` copies admins with
`SELECT id, username, ... FROM "user" WHERE role = 'admin'` — *preserving ids* —
and then advances only `admin_identity`'s sequence:

```sql
SELECT setval(pg_get_serial_sequence('admin_identity', 'id'),
              COALESCE((SELECT MAX(id) FROM admin_identity), 1))
```

`user`'s sequence is untouched, so the two id spaces overlap. A constraint
against either table can be **satisfied by the wrong row**, recording that a
customer performed an admin action. This is not hypothetical: the first version
of `test_audit_actor_fk.py` had to pin `_PROBE_ADMIN_ID = 900_001` because an
earlier test's `user` row satisfied the constraint and turned an expected failure
into an XPASS.

**It breaks a documented extension point.** `project-dna.md` §17 IC-218-7
sanctions pointing "the `admin_identity` repository at a separate database URL —
no core change required". Cross-database foreign keys do not exist on PostgreSQL
or MySQL, and `admin_audit_log` is owned by `_core`.

It would also be the only `_core`-owned foreign key in the tree, and the only
cross-realm one — establishing a precedent for future `_core` cross-cutting
tables (outbox, notification ledger, job history) to copy.

### B. Keep a constraint and stop deleting actors (tombstones) — rejected for now

The textbook relational answer: an audit log should reference an immutable actor
dimension. Repoint to `admin_identity.id` with `ON DELETE NO ACTION` and convert
`AdminAccountUseCase.delete_account` from a physical delete to a `deleted_at`
tombstone.

This is the strongest form of the "keep integrity" position and is **not
dismissed** — it is out of scope. It requires a soft-delete column, filtering in
`delete_account`, `count_accounts_permission_holders`, credential verification,
`has_real_admin` and the `/admin/accounts` UI, plus redesigning the bootstrap
admin's hard delete on every fresh install. And it does not solve A's id-space
overlap or the IC-218-7 conflict.

### C. `ON DELETE RESTRICT` on the existing target — rejected

Every admin action is audited, so no admin with any history could ever be
deleted. That breaks the accounts page and the setup flow.

### D. Drop the constraint, move integrity to the read path — chosen

## Decision

**D1.** `admin_audit_log.admin_user_id` carries no foreign key. It is a nullable
`Integer` with a schema `comment=` stating: `admin_identity.id` of the actor,
realm-scoped, correlation-only, never join to `user`, `admin_username` is the
durable reference.

**D2.** `admin_username` remains the durable actor reference, as the model
already claimed. Nothing dereferences `admin_user_id`: the repository selects it
raw, filters use `admin_username`/`action`/`domain`/`result`/`created_at`, and
the audit-log page displays `admin_username`.

**D3.** Referential expectations are asserted on the **read** side, in
`tests/unit/_core/infrastructure/admin/audit/test_audit_actor_fk.py`: a stored
actor id resolves through the `admin_identity` repository — the access path §17
IC-218-1 mandates — and does not collide with a `user` row. A read cannot reject,
and therefore cannot lose, an audit event.

**D4.** The audit-write failure path stays non-raising but stops being silent. It
logs at `error` with `admin_username`, `admin_user_id` and `record_id` (still
excluding `before_state` / `after_state` / `failure_reason`, which may carry
unvetted detail), names a constraint rejection distinctly
(`audit_write_rejected_by_constraint`), and dispatches through `ErrorNotifier`
at severity 500 so a persistent failure pages an operator.

**D5.** Existing data is left as found. Pre-#218 rows on PostgreSQL/MySQL already
had `admin_user_id` nulled by `0009`'s `DELETE FROM "user" WHERE role = 'admin'`
cascading through the `SET NULL` created in `0007`; the same rows on SQLite still
hold the old customer ids. Backfilling would mean guessing which id space a value
came from.

## Consequences

- **ADR057-G1** — No `_core`-owned table may declare a foreign key into a
  bounded context's table. Cross-context references are correlation-only and are
  reconciled through the owning domain's repository or protocol (§17 IC-218-1).
  This inherits to any future `_core` cross-cutting table: outbox, notification
  ledger, job history.
- **ADR057-G2** — An audit-write failure must never be logged below `error`, and
  must carry actor and target. Any future change to `AuditLogger`'s failure path
  inherits this; `test_audit_write_failure_visibility.py` enforces it.
- **ADR057-G3** — `user.id` and `admin_identity.id` overlap as a consequence of
  `0009`'s id-preserving copy. Treat the two as separate, non-comparable id
  spaces. Any code that resolves an admin-realm id must go through
  `admin_identity`; any constraint or join that mixes them is a defect regardless
  of whether it currently passes.
- **ADR057-G4** — Option B (immutable actor dimension via tombstones) remains
  the preferred long-term shape if admin deletion semantics are ever revisited.
  Whoever does that work should re-evaluate D1, and must resolve G3 first —
  a constraint over overlapping id spaces is unsafe even with tombstones.
- A dangling `admin_user_id` is now possible: deleting an admin leaves the id in
  past audit rows. That is the intended behaviour for an append-only trail, and
  is why D3 asserts resolution rather than existence.

## Post-decision Update

_To be filled in after the first deployment that exercises D4 — specifically
whether the `ErrorNotifier` dispatch produces useful signal or noise under a
sustained audit-write failure._
