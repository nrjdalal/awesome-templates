# Containers

How the image is built, what `docker compose up` gives you, and what to change
before this reaches a real environment.

Until #332 none of this was documented and neither entry point worked: the
image could not build as shipped, and `docker compose config` exited 1 on a
clean clone.

## Quick start

```bash
docker compose up -d --build
curl http://127.0.0.1:8080/health
docker compose logs -f server worker scheduler
docker compose down -v
```

No files to copy first, no credentials to supply. The stack runs at `ENV=local`
on the inline defaults in `docker-compose.yml`.

## What the stack contains

| Service | Role |
|---|---|
| `postgres` | PostgreSQL 16. The image has no SQLite driver — `aiosqlite` is a dev dependency, so SQLite is a test/quickstart engine only. |
| `rabbitmq` | Broker. `BROKER_TYPE=inmemory` runs tasks inline in the producer and `InMemoryBroker.listen()` raises, so a standalone worker needs a real one. |
| `migrate` | Runs `alembic upgrade head` to completion, then exits. Every app service waits on `service_completed_successfully`, so the three of them never race to create the same tables. |
| `server` | uvicorn on container port 8000, published on **host 8080**. |
| `worker` | `taskiq worker` — consumes what the app and the scheduler enqueue. |
| `scheduler` | `taskiq scheduler` — enqueues on cron labels only. Run exactly one; two would double-enqueue. |

### Why host port 8080

Port 8000 belongs to `dynamodb-local` in this repo — `docker-compose.local.yml`
publishes it there, `_env/*.example` points `DYNAMODB_ENDPOINT_URL` at it, and
the DynamoDB integration tests probe `http://localhost:8000` to decide whether
to skip. Publishing the server there makes those tests find FastAPI instead of
DynamoDB, so they stop skipping and fail with a 404 from `DescribeTable`. 8001
is the `run_*_local.py` port. Postgres and RabbitMQ are deliberately not
published at all, so this file and `docker-compose.local.yml` can coexist.

## The image

`_docker/docker.Dockerfile` is a two-stage build shared by all three app
processes; they differ only in the command compose gives them.

- **builder** — installs `build-essential` and runs `uv sync --no-dev --frozen`
  into `/app/.venv`. The toolchain stays here.
- **runtime** — copies the venv, `src/`, `migrations/` and `alembic.ini`, drops
  to a non-root `app` user (uid 1001), and declares a `HEALTHCHECK` that calls
  `/health` with the interpreter (the slim base ships no `curl`).

### Configuration is never baked in

The old image did `COPY _env/${ENV}.env /app/.env` with `ARG ENV=prod`. Only
`*.env.example` files are committed and `_env/*.env` is gitignored, so it did
not build; adding the file to make it build wrote credentials into a layer that
`docker history` prints. Configuration now comes from the process environment.

Compose supplies it through two `env_file` entries:

```yaml
env_file:
  - _docker/compose.defaults.env      # committed reference defaults
  - path: _env/prod.env               # your overlay
    required: false
```

Entries later in the list win, and a missing optional file is a clean no-op —
so the absence of `_env/prod.env` is not an error and its presence really does
override the defaults.

The defaults deliberately live in a committed env file rather than a compose
`environment:` block. `environment:` takes precedence over **every**
`env_file:` entry, so an inline block would silently pin `ENV=local`, keep
stg/prod boot validation switched off, and make the wildcard hosts and
placeholder credentials impossible to replace. Confirm either way with
`docker compose config`.

### Build arguments

| Arg | Default | Why |
|---|---|---|
| `EXTRAS` | `--extra sqs --extra rabbitmq` | `Settings` requires an explicit `BROKER_TYPE` in stg/prod and both supported values need a package a core-only sync omits (`sqs` → `taskiq-aws`, `rabbitmq` → `taskiq-aio-pika`). |

To include the NiceGUI admin dashboard, which mounts onto the server process:

```bash
docker compose build --build-arg EXTRAS="--extra sqs --extra rabbitmq --extra admin"
```

Without it the server boots normally and logs `admin_mount_skipped`.

## Migrations

`alembic upgrade head` runs in its own service. Two things had to change before
it could work in a container:

- `migrations/` and `alembic.ini` were never copied into the image.
- `migrations/env.py` hard-failed when `_env/{ENV}.env` was missing. It now
  falls back to the process environment and only requires the file when
  `DATABASE_ENGINE` is unset.

Revision identifiers must stay **32 characters or shorter**.
`alembic_version.version_num` is `String(32)`, hardcoded in
`DefaultImpl.version_table_impl` with no configuration hook, so a longer id
fails on PostgreSQL and MySQL while passing silently on SQLite. Three shipped
revisions were over the limit and were renamed in #332;
`tests/unit/tools/test_migration_revision_ids.py` now enforces it.

### Upgrading a database created before #332

Because SQLite does not enforce VARCHAR length, a v0.9.0 install that ran
migrations on SQLite can be holding one of the old long ids — as can any
database whose operator widened the column by hand. PostgreSQL and MySQL cannot:
they rejected those values, which is the bug #332 fixed. An affected database
meets this on the next upgrade:

```
Can't locate revision identified by '0009_admin_identity_realm_separation'
```

Run the rewrite once before `alembic upgrade`. It only ever replaces the three
known ids, is a no-op on a current or fresh database, and is idempotent:

```bash
uv run python tools/migrate_legacy_revision_ids.py --env local --dry-run
uv run python tools/migrate_legacy_revision_ids.py --env local
```

## Before a real deployment

The defaults in `docker-compose.yml` are a runnable reference, not a production
posture. At minimum:

- Supply `_env/prod.env` and set `ENV=stg` or `ENV=prod`. Boot validation then
  rejects every placeholder credential in this file — that is the intended
  behaviour, not an obstacle to work around. See
  [`../reference.md`](../reference.md) for the full settings surface.
- Point `DATABASE_*` at managed infrastructure and drop the `postgres` and
  `rabbitmq` services, or replace RabbitMQ with `BROKER_TYPE=sqs`.
- Replace `ALLOWED_HOSTS` / `ALLOW_ORIGINS` — `["*"]` is a local convenience.
- Set `ADMIN_STORAGE_SECRET` and the `JWT_*` / `ADMIN_JWT_*` secrets. The admin
  realm's secret must differ from the customer realm's; a validator rejects
  realm collapse.
- Run `migrate` as a pre-deploy job rather than a compose dependency, and read
  [`rdb-migrations.md`](rdb-migrations.md) for the expand-contract playbook
  before a rollout that cannot take downtime.
