# Canonical Demo Walkthrough

Start with JWT auth, RBAC-gated admin, and a stub RAG query on SQLite + InMemory,
without external infrastructure. Later sections explain the in-process task path
and optional standalone workers and OTEL traces, which require extra dependencies
and services.

---

## Prerequisites

Python >=3.12.9, [uv](https://docs.astral.sh/uv/), Git, `make`, `curl`, and
`python3` on your PATH. Start in a fresh evaluation checkout.

```bash
git clone https://github.com/Mr-DooSun/fastapi-agent-blueprint.git
cd fastapi-agent-blueprint
```

---

## Step 1 — Boot the server

```bash
make quickstart
```

Expected: server on `http://127.0.0.1:8001`, SQLite schema auto-created.
`make quickstart` installs its dependencies and keeps this terminal occupied.
It syncs the admin extra and can remove other extras; reserve `make setup` for
the development/test step below.

```text
INFO  event="server_start" host="127.0.0.1" port=8001 env="quickstart"
```

---

## Step 2 — CRUD + JWT auth

Keep the server running. In a second terminal, from the same repository directory:

```bash
make demo
```

This exercises the `auth` and `user` domains end-to-end — customer registration,
demo-admin seeding and admin-realm login, user CRUD, token refresh, and logout.
The customer token alone cannot authorize user CRUD.

```text
→ Health check
{ "status": "ok" }

→ Register (creates user account + returns JWT token pair)
{ "success": true, "data": { "accessToken": "...", "refreshToken": "..." } }

→ Seed a demo admin → Admin-realm login
→ Create a second user (admin JWT-authenticated)
{ "success": true, "data": { "id": 2, "username": "bob", ... } }

→ List users (page=1, pageSize=10)
{ "data": [ { "id": 1, "username": "alice" }, { "id": 2, "username": "bob" } ],
  "pagination": { "currentPage": 1, "totalItems": 2, "hasNext": false } }

→ Update the user    → Delete the user
→ Refresh token      → Logout
→ Done. API docs: http://127.0.0.1:8001/docs
```

---

## Step 3 — RAG pipeline

In the second terminal, with the server still running:

```bash
make demo-rag
```

Seeds 3 documents, runs a retrieval query, and shows structured citations:
the default keyword embedder and templated answer agent are deterministic stubs,
so this step does not evaluate a real model's answer quality.

```text
→ Upload 3 documents (chunk → embed → upsert)
→ List documents         { "data": [ { "id": 1, "title": "..." }, ... ] }
→ Query: "What are the key points?"
→ Answer with citations  { "answer": "...", "citations": [ { "chunkId": "...", "score": 0.91 } ] }
```

---

## Step 4 — NiceGUI admin (JWT + RBAC)

Open `http://127.0.0.1:8001/admin` in a browser.

1. Log in with the bootstrap admin credentials (set via `ADMIN_BOOTSTRAP_*` env vars, or default `admin` / `admin` in quickstart mode).
2. Browse the **User** and **Docs** admin pages — AG Grid CRUD, field masking on sensitive columns.
3. Admin login is backed by the separate `admin_identity` realm (ADR 049), distinct from the customer `auth` domain; membership in `admin_identity` gates admin access.

---

## Step 5 — Background worker

The quickstart runs on the **InMemory broker** (`BROKER_TYPE=inmemory`), which executes Taskiq
tasks **synchronously inline inside the API server process** — there is no separate worker to
start (`InMemoryBroker.listen()` raises, so it cannot back a standalone `make worker`). The
`docs` domain dispatches a background ingestion task when a document exceeds the inline
threshold (20,000 characters). The three demo documents are 378–425 characters, so Step 3 took
the **inline** path (`DocumentService.should_ingest_sync`) and dispatched no task at all — it
did not exercise the worker. To see the background path, upload a document over 20,000
characters; on the InMemory broker that still runs in-process, just through the task.

To watch a **standalone worker** pull jobs across process boundaries, switch to a cross-process
broker. Start RabbitMQ, set `BROKER_TYPE=rabbitmq` + `RABBITMQ_URL` in your env file, then run
the server and worker in the same environment (the
[`examples/webhook_receiver/` README](../examples/webhook_receiver/README.md) walks through the
full recipe):

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
# _env/quickstart.env → BROKER_TYPE=rabbitmq, RABBITMQ_URL=amqp://guest:guest@localhost:5672/
uv sync --extra admin --extra rabbitmq
uv run python run_server_local.py --env quickstart   # terminal 1
uv run python run_worker_local.py --env quickstart    # terminal 2 — the standalone worker
```

The `user` domain registers a `user.test` task as a reference example — see [`src/user/interface/worker/tasks/user_test_task.py`](../src/user/interface/worker/tasks/user_test_task.py). Replace it with domain-specific background work (email dispatch, async enrichment, scheduled jobs) following the same Taskiq pattern.

Stop the prior server before restarting. Include all extras you need in each
`uv sync` command. If returning to the no-broker demo, stop your worker and restore
`BROKER_TYPE=inmemory` before restarting the server.

---

## Step 6 — OpenTelemetry traces (optional)

With a local Jaeger or Tempo instance, stop the current server, then run:

```bash
uv sync --extra admin --extra otel
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
uv run python run_server_local.py --env quickstart
```

Traces are emitted per-request and per-worker-task. See
[`docs/operations/observability-otel.md`](operations/observability-otel.md)
for the full Jaeger/Tempo/Phoenix recipe.
If you kept the RabbitMQ configuration from Step 5, also include `--extra rabbitmq`
in the sync command. Do not use `make quickstart` here: it would remove the OTEL extra.

---

## Step 7 — Tests

```bash
make setup       # install development dependencies + admin/AWS extras and commit hooks
make check-core  # fast local lint, format and core test checks
```

Run this after stopping the demo processes. These local checks do not require
external infrastructure. Full integration checks have additional prerequisites;
see [CONTRIBUTING.md](../CONTRIBUTING.md). `make setup` can remove optional extras
from the preceding steps; reinstall the complete set if you need those services again.

```bash
make test-pg    # optional: PostgreSQL variant
make test-dynamo  # optional: DynamoDB Local variant
```

---

## What just ran

| Layer | Exercised |
|---|---|
| HTTP API | JWT register/login/refresh/logout, CRUD, RAG upload + query |
| Background worker | Taskiq wired on the InMemory broker with the full middleware stack — `make demo-rag` stays under the 20,000-char inline threshold, so no task is dispatched (see Step 5) |
| Admin UI | NiceGUI with JWT login + RBAC admin gating |
| Domain isolation | user · auth · docs · ai_usage as independent DDD domains |
| Optional infra | OTEL traces (opt-in), embeddings + LLM via stub fallbacks |

---

## Next steps

- [Build your own domain](tutorial/first-domain.md) — guided walkthrough
- [AI-assisted scaffolding](ai-development.md) — `/new-domain` in Claude Code or Codex CLI
- [Adoption guide](adoption.md) — partial import into an existing FastAPI project
- [Frontend handoff](frontend-handoff.md) — OpenAPI contract, Orval codegen, JWT flow
