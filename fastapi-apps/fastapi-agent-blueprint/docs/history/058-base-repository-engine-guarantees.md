# 058. What `BaseRepository` Guarantees Regardless of `DATABASE_ENGINE`

- Status: Accepted
- Date: 2026-08-05
- Issue: [#325](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/325)
- Related: [ADR 011](011-3tier-hybrid-architecture.md) (3-tier hybrid architecture), [ADR 056](056-zero-downtime-migration-safety.md) (migration safety), [ADR 057](057-audit-actor-correlation-only.md) (the sibling "silent failure" decision)

## Summary

`BaseRepository` guarantees the **same observable behaviour on PostgreSQL, MySQL
and SQLite**. Where a dialect difference would change what a caller sees, the base
class normalises it. Where a request cannot be honoured, the base class fails
closed with a curated 4xx rather than silently returning something else.

## Background

### Trigger

Five defects in one base class that six domains and nine `examples/` inherit, so
each shipped N times. The audit's framing is the point: **"what does
`BaseRepository` guarantee regardless of `DATABASE_ENGINE`?" had no answer**, which
is why the answers diverged — `ai_usage_repository` had hand-fixed the pagination
one locally instead of in the base.

### The engine split that made one of them invisible

```
mysql       prefer_eager=False insert_returning=False
aiomysql    prefer_eager=False insert_returning=False
postgresql  prefer_eager=True  insert_returning=True
sqlite      prefer_eager=True  insert_returning=True
```

`insert_data` (singular) did `commit()` then `refresh()`. `insert_datas` (bulk) did
`add_all` → `flush` → `commit` and then `model_validate(..., from_attributes=True)`
with **no refresh**. On dialects that support RETURNING, SQLAlchemy's
`eager_defaults="auto"` fetches `server_default` columns during the INSERT, so it
happened to work. Where `insert_returning` is False, `created_at`/`updated_at` were
never loaded, the synchronous attribute access inside `model_validate` triggered a
lazy refresh with no greenlet, and `Database.session()`'s catch-all converted
`MissingGreenlet` into `DatabaseException(500, DB_INTERNAL_ERROR)`.

The rows are **already committed** when that fires, so the client sees a failure
for a write that succeeded and retries into duplicate-key errors. 16 model files
carry `server_default=func.now()`.

CI ran SQLite and `make test-pg` runs PostgreSQL, so no test could see it.

## Problem

Three properties were unstated, and therefore unheld:

1. Does the same write expressed two ways return the same DTO?
2. Is a paged read stable across pages?
3. When a request cannot be honoured, does the caller learn, or get something else?

## Alternatives Considered

### A. Normalise in the base class — chosen

### B. Demote MySQL to best-effort in `docs/compatibility.md` — rejected

Narrower to implement, but `README.md` advertises three engines and
`KNOWN_ENGINES` accepts three. Choosing this would mean removing MySQL from both,
which is a larger user-visible change than fixing the three-line gap.

### C. `eager_defaults=True` on every model — rejected

Would fix F3 without an explicit refresh, but pushes the obligation onto every
adopter's model instead of the base class they inherit, and silently changes
INSERT shape on dialects that do support RETURNING.

### D. Fail loudly instead of a deterministic page order — rejected

`select_datas*` could require an explicit sort. Rejected because it breaks every
existing caller and, more importantly, an adopter who never reads this ADR gets
correct behaviour by default under A and a runtime error under D.

## Decision

**D1 — Bulk and singular insert return the same thing.** `insert_datas` loads
server-side defaults with **one** `populate_existing` SELECT over the flushed ids,
**before** commit, and builds the DTOs before commit too.

Two shapes were rejected during review. A per-instance `session.refresh()` loop is
`INSERT × N + SELECT × N` — on the public batch endpoint (100 items) that is 100
sequential round-trips, and `refresh()` issues a SELECT even on dialects that
support RETURNING, so it is not "nearly free" anywhere. Doing it *after* commit is
worse than slow: a refresh that fails then returns a 500 for rows already written,
which is precisely the failure this decision exists to remove. Building the DTOs
before commit closes that window; the reload is chunked so a batch large enough to
exceed a driver's bind-parameter limit fails on the insert rather than on the
reload.

**D2 — Offset pagination is deterministically ordered, always.** The primary key
descending is appended as a tiebreaker to *every* paged query, including one that
carries an explicit `QueryFilter.sort_field`.

"An explicit sort wins" means the caller's column is the **primary** sort key, not
the only one. The first version of this fix skipped the tiebreaker whenever a sort
was supplied, which put tie order back in the engine's hands — so paging over a
non-unique column (`created_at`, `status`, `full_name`) could still repeat or skip
rows, the exact defect being removed. The tiebreaker is omitted only when the
caller already sorted by the primary key, so the same column is never ordered in
both directions.

**This is API-visible** — the default order of every unsorted list endpoint changes
from engine-dependent to newest-first, recorded in the CHANGELOG.

**D3 — Search fails closed.** A search naming no usable text column raises a
curated 400 (`DB_SEARCH_FIELD_UNUSABLE`) instead of adding no WHERE clause and
returning the whole table with `total_items` set to the full count. A usable field
is still honoured when a sibling is not — dropping the unusable half is what
failed open, but rejecting a request where *some* field works would be
over-correction; the skipped names go to structlog.

**D4 — One field resolver.** `_column_for_field` is the only path from a field
name to a column, and it raises a curated 400 (`DB_UNKNOWN_FIELD`). The sort path
previously used bare `hasattr` + `getattr` and called `.desc()` on whatever came
back, so a method or class attribute produced an opaque 500.

**D5 — No dead relationship hook.** The `related_entities` branch is removed. It
passed a *list* to `AsyncSession.refresh`, which takes one instance; the repo
declares no `relationship()` and nothing defines the attribute, so it was dead —
and wrong the moment it was not. The `joinedload`/`selectinload` hook that
project-dna §0 mandates for N+1 mitigation does not exist and is **not** added
here; a dead branch that resembles it was worse than its absence.

## Verification, and its limit

D1 is pinned by forcing `insert_returning=False` and
`insert_executemany_returning=False` on a SQLite engine, which reproduces the
non-RETURNING code path without a MySQL instance.

**The limitation is deliberate and should be stated plainly: no real MySQL runs in
CI.** A MySQL matrix leg was considered as part of this work and declined to keep
the CI matrix at two engines. So the guarantee is enforced against the *dialect
flag that decides the behaviour*, not against MySQL itself. Anything that depends
on MySQL beyond that flag — collation, `ONLY_FULL_GROUP_BY`, index length limits —
is unverified here. Adding the leg later is the natural way to close that gap, and
nothing in this ADR depends on it staying absent.

## Consequences

- **ADR058-G1** — Any new `BaseRepository` method that reads back a row it just
  wrote must load server-side defaults explicitly. Do not rely on
  `eager_defaults="auto"`: it is a dialect capability, not a contract.
- **ADR058-G2** — Any offset-paginated query must carry a deterministic order.
  New paginated methods inherit `_stable_order()`; do not add a paged read that
  relies on engine default order.
- **ADR058-G3** — A request the repository cannot honour fails closed with a
  curated 4xx. Silently returning a wider result set than asked for is a defect
  regardless of how convenient it is. This inherits to filters, bounds and sorts
  alike, and is the same rule ADR 057 applied to audit writes and #328 applied to
  vector filters.
- **ADR058-G4** — Field-name-to-column resolution goes through
  `_column_for_field`. A second resolver is how the sort path diverged.
- **ADR058-G5** — `sortable_fields` on `BaseAdminPage` is declared, populated by
  two domain configs, and **read by nothing**. It is a decoy allowlist. Either
  wire it into `_column_for_field`'s caller or delete it; do not assume it
  constrains anything today. Left as-is here to keep this PR to the base class.

## Post-decision Update

_To be filled in after the first adopter runs this on MySQL — specifically whether
D1's explicit refresh is sufficient or whether other dialect differences surface._
