# Canonical Demo Walkthrough

This walkthrough runs the complete platform in a single session: JWT auth,
RBAC-gated admin, background worker, RAG query, and OTEL traces.
All steps work against SQLite + InMemory broker — no external infra needed.

---

## Prerequisites

```bash
git clone https://github.com/Mr-DooSun/fastapi-agent-blueprint.git
cd fastapi-agent-blueprint
make setup   # one-time: venv + deps via uv
```

---

## Step 1 — Boot the server

```bash
make quickstart
```

Expected: server on `http://127.0.0.1:8001`, SQLite schema auto-created.

```text
INFO  event="server_start" host="127.0.0.1" port=8001 env="quickstart"
```

---

## Step 2 — CRUD + JWT auth

In a second terminal:

```bash
make demo
```

This exercises the `auth` and `user` domains end-to-end — register, JWT token issuance, authenticated CRUD, token refresh, and logout:

```text
→ Health check
{ "status": "ok" }

→ Register (creates user account + returns JWT token pair)
{ "success": true, "data": { "accessToken": "...", "refreshToken": "..." } }

→ Create a second user (JWT-authenticated)
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

```bash
make demo-rag
```

Seeds 3 documents, runs a retrieval query, and shows structured citations:

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

In a third terminal:

```bash
make worker
```

Expected: worker connects to the InMemory broker and subscribes to task queues:

```text
INFO  event="worker_start" broker="inmemory"
INFO  event="worker_ready" queues=["fastapi-agent-blueprint.user.test", "fastapi-agent-blueprint.docs.ingest"]
```

The `docs` domain dispatches a background ingestion task when a document is too large for inline processing (threshold: 20,000 characters). Upload a large document while the worker is running and you will see:

```text
INFO  event="task_received" task_name="fastapi-agent-blueprint.docs.ingest" document_id=1
INFO  event="task_completed" task_name="fastapi-agent-blueprint.docs.ingest" duration_ms=45
```

The `user` domain registers a `user.test` task as a reference example — see [`src/user/interface/worker/tasks/user_test_task.py`](../src/user/interface/worker/tasks/user_test_task.py). Replace it with domain-specific background work (email dispatch, async enrichment, scheduled jobs) following the same Taskiq pattern.

---

## Step 6 — OpenTelemetry traces (optional)

If you have a local Jaeger or Tempo instance:

```bash
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
make quickstart
```

Traces are emitted per-request and per-worker-task. See
[`docs/operations/observability-otel.md`](operations/observability-otel.md)
for the full Jaeger/Tempo/Phoenix recipe.

---

## Step 7 — Tests

```bash
pytest tests/ -v
```

Expected: all tests pass against SQLite in-memory. No external infra required.

```bash
make test-pg    # optional: PostgreSQL variant
make test-dynamo  # optional: DynamoDB Local variant
```

---

## What just ran

| Layer | Exercised |
|---|---|
| HTTP API | JWT register/login/refresh/logout, CRUD, RAG upload + query |
| Background worker | Task dispatch via Taskiq InMemory broker |
| Admin UI | NiceGUI with JWT login + RBAC admin gating |
| Domain isolation | user · auth · docs · ai_usage as independent DDD domains |
| Optional infra | OTEL traces (opt-in), embeddings + LLM via stub fallbacks |

---

## Next steps

- [Build your own domain](tutorial/first-domain.md) — 10-minute guided walkthrough
- [AI-assisted scaffolding](ai-development.md) — `/new-domain` in Claude Code or Codex CLI
- [Adoption guide](adoption.md) — partial import into an existing FastAPI project
- [Frontend handoff](frontend-handoff.md) — OpenAPI contract, Orval codegen, JWT flow
