# Locust Performance Testing — Operations Recipe

This document covers the repo's Locust harness: how to run it against the
zero-config quickstart server, how to read the output, and how to enable the
optional admin CRUD scenario.

This is a ready-to-adapt harness for a blueprint, not benchmarking
infrastructure. Any numbers it produces are illustrative for the local
quickstart setup (SQLite + InMemory broker on one machine) — treat them as a
smoke reference, not production guarantees. Adopters should rerun the harness
against their own infrastructure. It is intentionally **not** wired into CI.

Never point the harness at a shared or production environment: the customer
scenario registers accounts and the admin scenario creates and deletes users.

## What you get

`tests/perf/locustfile.py` defines three scenarios:

| Scenario | User class | Requires | What it measures |
|---|---|---|---|
| Customer auth flow | `CustomerAuthUser` | nothing | `POST /v1/auth/register` (once per virtual user), `GET /v1/auth/me`, `POST /v1/auth/refresh`, and `POST /v1/auth/logout` on stop — all on the customer JWT realm |
| Concurrent health reads | `HealthCheckUser` | nothing | `GET /health` (no-op app baseline) and `GET /health/db` (connection-pool acquisition + a real `SELECT 1`; 503 when the DB is down) |
| Admin CRUD flow | `AdminCrudUser` | `LOCUST_ADMIN_*` env vars | `POST /v1/admin/login`, paginated `GET /v1/users`, and a create → read → update → delete cycle on `/v1/user` |

`/health` and `/health/db` are tracked as separate stat rows on purpose — the
first isolates app/HTTP responsiveness, the second adds a database roundtrip.
The per-ID CRUD requests are grouped under one `/v1/user/[id]` row so each
generated ID does not create its own statistics line.

## Run it

```bash
make quickstart      # terminal 1 — zero-config server on 127.0.0.1:8001
make perf-test       # terminal 2 — 30s headless run, summary printed on exit
```

Without admin credentials the run covers the customer + health scenarios and
logs one line noting that the admin scenario is disabled. That default run is
the supported zero-setup path.

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PERF_HOST` | `http://127.0.0.1:8001` | Target base URL |
| `PERF_USERS` | `10` | Peak number of concurrent virtual users |
| `PERF_SPAWN_RATE` | `2` | Users started per second until the peak |
| `PERF_RUN_TIME` | `30s` | Total run duration (`30s`, `2m`, …) |

```bash
make perf-test PERF_USERS=50 PERF_SPAWN_RATE=5 PERF_RUN_TIME=2m
```

For Locust's web UI, charts, or CSV output, invoke Locust directly —
`uv run locust -f tests/perf/locustfile.py --host http://127.0.0.1:8001`
(then open http://localhost:8089).

## Enabling the admin CRUD scenario

All `/v1/user` routes are admin-only (#199) and require a token from the
separate admin JWT realm (#218). Two things follow:

- A **customer** token cannot run the CRUD scenario — the admin verifier
  rejects it with `401 INVALID_TOKEN`.
- The quickstart bootstrap account (`admin`/`admin`) is **setup-only**: the
  token API (`POST /v1/admin/login`) rejects bootstrap and temp-password
  admins with `401`.

So the scenario needs a real (non-bootstrap) admin, provisioned once through
the browser dashboard:

1. With the quickstart server running, open http://127.0.0.1:8001/admin and
   log in with the bootstrap credentials (`admin`/`admin` unless changed in
   `_env/quickstart.env`). You are redirected to the one-time setup page.
2. Create the first real admin account. Copy the generated temporary password
   — it is shown exactly once, and the bootstrap account is deleted.
3. Log in again with the temporary password and complete the forced password
   change.

Then export the credentials and rerun:

```bash
export LOCUST_ADMIN_USERNAME=<your-admin-username>
export LOCUST_ADMIN_PASSWORD=<your-admin-password>
make perf-test
```

Credential behavior:

- **Both unset** — the admin user class is never spawned; the run stays
  zero-setup and useful.
- **Set but wrong** — the `/v1/admin/login` failure is recorded loudly in
  Locust's failure table and that virtual user stops. It never silently
  downgrades.
- Credentials are read from the environment only — never hardcode them, and
  they are not logged.

The CRUD cycle deletes the users it creates; a hard abort mid-cycle can leave
a stray `crud…` user behind in the local quickstart database (delete it via
the admin dashboard or remove `quickstart.db`).

## Reading the output

A headless run prints a stats table while running and a final summary:

```
Type  Name                 # reqs  # fails  |  Avg  Min  Max  Med  |  req/s  failures/s
GET   /health                 312     0(0.00%)     3    1   18    2      10.4    0.00
GET   /v1/auth/me             208     0(0.00%)     9    4   61    7       6.9    0.00
...
Response time percentiles (approximated)
Type  Name             50%  66%  75%  80%  90%  95%  98%  99%  ...
```

What to look at:

- **# reqs / req/s** — total volume and sustained throughput per endpoint.
- **# fails** — anything above 0% needs an explanation before the numbers
  mean anything (auth failures, 5xx, connection errors all land here).
- **Med (p50)** — typical latency; compare `/health` vs `/health/db` vs
  authenticated endpoints to see where time is spent.
- **p95 / p99** (percentiles block) — tail latency; the first thing to watch
  when raising `PERF_USERS`.

The `Aggregated` row summarizes everything; per-endpoint rows are usually
more actionable.

`make perf-test` exits non-zero when any request failed during the run, so a
clean exit code doubles as a quick pass/fail signal.

## Illustrative local baseline

One measured default run (customer + health scenarios; admin scenario
inactive), recorded to show the expected shape of the output — not a
performance guarantee of any kind:

| Field | Value |
|---|---|
| Date | 2026-07-15 |
| Machine / OS | Apple M3 Pro, 18 GB — macOS (Darwin 24.6.0) |
| Python / project version | Python 3.13.8 / v0.8.4 (Locust 2.43.0) |
| Server | `make quickstart` (SQLite + InMemory broker, single process) |
| Profile | `PERF_USERS=10`, `PERF_SPAWN_RATE=2`, `PERF_RUN_TIME=30s` |
| Total requests / failures | 327 / 0 (0.00%) |
| Aggregated RPS | 10.9 |
| Aggregated p50 / p95 / p99 | 3 ms / 25 ms / 220 ms |

Per-endpoint medians from the same run: `/health` 2 ms, `/health/db` 4 ms,
`/v1/auth/me` 4 ms, `/v1/auth/refresh` 13 ms, `/v1/auth/logout` 20 ms,
`/v1/auth/register` 220 ms (bcrypt password hashing dominates registration —
it runs once per virtual user, and its tail is what pushes the aggregated p99
up). Throughput here is bounded by the scenario think-times (`wait_time`),
not by the server.

## Limitations

- Local quickstart topology only (SQLite, single process, same machine as the
  load generator) — the load generator and server compete for CPU.
- Admin access tokens expire after 15 minutes by default
  (`ADMIN_JWT_ACCESS_TOKEN_MINUTES`) and the harness does not refresh them —
  keep admin-enabled runs under that limit or expect `401` rows near the end.
  The customer scenario self-heals via its refresh task.
- Illustrative, not authoritative: no thresholds, no regression gating, no CI.
- The customer scenario grows the local database (one account per virtual
  user per run); reset with `rm quickstart.db` when it matters.
- Worker/broker load (Taskiq scenarios) is out of scope.
