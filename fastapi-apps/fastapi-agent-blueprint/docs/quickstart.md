# Quickstart — run the backend locally

Zero external infrastructure. No Docker. No Postgres. No cloud credentials.
Start with the backend, then explore the [AI collaboration workflow](../README.md#ai-collaboration-harness).

## Prerequisites

- Python `>=3.12.9`
- [`uv`](https://docs.astral.sh/uv/) (package manager)
- Git and `make`; the demos also require `curl` and `python3` on your PATH

## Run it

```bash
git clone https://github.com/Mr-DooSun/fastapi-agent-blueprint.git
cd fastapi-agent-blueprint
make quickstart    # installs dependencies, then runs the server in this terminal
```

Use a fresh checkout for evaluation. `quickstart` syncs the admin extra and can
remove other installed extras. `make setup` is for development dependencies
(including admin + AWS) and commit hooks; it is not a prerequisite for this demo.

The server comes up on `http://127.0.0.1:8001`:

| Endpoint | URL |
|----------|-----|
| API docs (selector) | http://127.0.0.1:8001/docs — Stoplight Elements / Scalar recommended |
| OpenAPI spec        | http://127.0.0.1:8001/openapi-download.json (attachment) |
| Swagger UI          | http://127.0.0.1:8001/docs-swagger |
| ReDoc               | http://127.0.0.1:8001/docs-redoc |
| Admin UI            | http://127.0.0.1:8001/admin (admin / admin) |
| Health              | http://127.0.0.1:8001/health |

For sharing the API with frontend developers, see
[`docs/frontend-handoff.md`](frontend-handoff.md).

## Exercise the API

Keep the server running. In a second terminal, from the same repository directory:

```bash
make demo
make demo-rag
```

This exercises the `auth` and `user` domains: health check → register (customer
JWT token pair) → seed a demo admin → admin login (a separate token realm) →
create user → list → update → delete → refresh token → logout.

The admin step is not decoration. `/v1/user*` is gated on `require_admin`
against the **admin** realm (#199/#218), which the customer token cannot
satisfy — and neither can the quickstart bootstrap admin, which is setup-only.
[`scripts/seed_demo_admin.py`](../scripts/seed_demo_admin.py) creates one real
admin the way the NiceGUI setup wizard would; it refuses to run in `stg`/`prod`.

Raw script: [`scripts/demo.sh`](../scripts/demo.sh).

`make demo-rag` exercises upload → chunk → embed → retrieve → answer with
citations. The default embedder uses keyword matching and the answer agent
returns a templated response: these are deterministic stubs, not external model
calls. Both scripts check response success and exit with failure on a failed request.

## What does `quickstart` actually configure?

`make quickstart` loads [`_env/quickstart.env`](../_env/quickstart.env.example)
(auto-copied from the committed template on first run).

| Setting | Value |
|---------|-------|
| `ENV` | `quickstart` |
| `DATABASE_ENGINE` | `sqlite` → `./quickstart.db` |
| `BROKER_TYPE` | `inmemory` (no queue server needed) |
| `STORAGE_TYPE` | _(unset — object storage disabled)_ |
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | _(unset — RAG uses deterministic stubs)_ |
| `ADMIN_BOOTSTRAP_USERNAME` / `ADMIN_BOOTSTRAP_PASSWORD` | `admin` / `admin` |

On startup the server auto-creates the SQLite schema from `Base.metadata`
(see [`src/_apps/server/bootstrap.py`](../src/_apps/server/bootstrap.py)) —
no migrations required.

**This path is for evaluation only.** `ADMIN_BOOTSTRAP_PASSWORD=admin` and
the shared `ADMIN_STORAGE_SECRET` will not pass the `stg`/`prod` safety check
in [`src/_core/config.py`](../src/_core/config.py). NiceGUI admin login uses
the DB-backed auth domain after the bootstrap user is created or promoted.

## Next steps

- **Real local development** — stop the quickstart server, run `make setup`
  to install development dependencies and commit hooks, then follow the
  [PostgreSQL setup](reference.md#local-development-with-postgresql).
- **Add a domain** — see [AGENTS.md](../AGENTS.md) and
  [docs/ai-development.md](ai-development.md), or invoke the
  `/new-domain` skill if you use Claude Code / Codex.
- **Enable real model calls** — stop the server, install the required provider
  extras (for example, `uv sync --extra admin --extra pydantic-ai` for the base
  AI integration), and set `LLM_PROVIDER` + `LLM_MODEL`,
  `EMBEDDING_PROVIDER` + `EMBEDDING_MODEL`, and matching credentials in
  `_env/quickstart.env`. Restart with
  `uv run python run_server_local.py --env quickstart` so `make quickstart`
  does not remove the extra you just installed. See the
  [extras reference](reference.md#optional-dependency-extras) for provider-specific
  extras and include every extra you want to retain in the sync command.

## Troubleshooting

- **Port 8001 already in use** — kill the previous server:
  `pkill -f run_server_local.py`
- **Fresh schema** — delete the SQLite file: `rm -f ./quickstart.db`, then
  re-run `make quickstart`
- **Regenerate the env file** — delete `_env/quickstart.env` and run
  `make quickstart` again
