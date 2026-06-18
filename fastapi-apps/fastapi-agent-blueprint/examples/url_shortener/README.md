# URL Shortener Example

A focused CRUD + worker example that demonstrates one domain service shared by
two interfaces. The HTTP router creates, reads, and deletes links by short code;
the Taskiq cleanup worker calls the same `LinkService` to delete expired rows.

> **Note:** Reference code only. Not auto-wired from `examples/`. To run it,
> copy this folder into `src/url_shortener/` so domain auto-discovery picks
> it up on server and worker startup.

## What It Teaches

- A small CRUD domain shaped like [`examples/todo/`](../todo/).
- A Taskiq task that reuses domain logic instead of duplicating cleanup rules.
- The zero-config worker path with `BROKER_TYPE=inmemory`.

Compare with [`src/user/interface/worker/`](../../src/user/interface/worker/)
for the minimal worker task pattern and
[`src/docs/interface/worker/`](../../src/docs/interface/worker/) for a router
that enqueues work with `.kiq(...)`.

## Install The Example

```bash
cp -r examples/url_shortener src/url_shortener
rm -f ./quickstart.db
make quickstart
```

`discover_domains()` expects `src/url_shortener/infrastructure/di/url_shortener_container.py`
and picks up the domain on server and worker startup.

## Endpoints

- `POST /v1/link` — Create a link
- `GET /v1/link/{short_code}` — Get a link by short code
- `DELETE /v1/link/{short_code}` — Delete a link by short code

## Try It With Curl

`expiresAt` values in the examples below are naive UTC datetimes (no timezone
offset). Match that format when creating links locally.

Create a link that expires in the future:

```bash
curl -sS -X POST http://127.0.0.1:8001/v1/link \
  -H "Content-Type: application/json" \
  -d '{
    "shortCode": "docs",
    "targetUrl": "https://fastapi.tiangolo.com/",
    "expiresAt": "2099-01-01T00:00:00"
  }'
```

Fetch it:

```bash
curl -sS http://127.0.0.1:8001/v1/link/docs
```

Delete it:

```bash
curl -sS -X DELETE http://127.0.0.1:8001/v1/link/docs
```

## Enqueue Cleanup With InMemory Broker

`make quickstart` loads `_env/quickstart.env`, which sets:

```env
BROKER_TYPE=inmemory
```

With the in-memory broker, `.kiq()` runs the task **inline in the calling
process** — there is no separate worker to start. The caller therefore has to
bootstrap the same DI wiring the server/worker normally sets up, so the task's
`@inject` dependency (`UrlShortenerContainer.link_service`) can resolve. To run
a real standalone worker across process boundaries instead, switch to a
cross-process broker such as RabbitMQ — see
[`examples/webhook_receiver/`](../webhook_receiver/README.md).

Create one already-expired link and one that never expires (so you can see the
task delete only the expired one):

```bash
curl -sS -X POST http://127.0.0.1:8001/v1/link \
  -H "Content-Type: application/json" \
  -d '{
    "shortCode": "expired",
    "targetUrl": "https://example.com/expired",
    "expiresAt": "2000-01-01T00:00:00"
  }'

curl -sS -X POST http://127.0.0.1:8001/v1/link \
  -H "Content-Type: application/json" \
  -d '{
    "shortCode": "keep",
    "targetUrl": "https://example.com/keep"
  }'
```

Then enqueue the cleanup task. The snippet mirrors the worker bootstrap:
instantiate the domain container on the shared `CoreContainer`, wire the task
module, then `kiq()` and await the result.

```bash
uv run python - <<'PY'
import asyncio

from dotenv import load_dotenv

# Load the same env the server booted with, so this snippet points at the
# same quickstart.db and BROKER_TYPE=inmemory.
load_dotenv("_env/quickstart.env", override=True)

# Import AFTER load_dotenv so CoreContainer reads the quickstart settings.
from src._apps.worker.broker import container as core_container
from src.url_shortener.infrastructure.di.url_shortener_container import (
    UrlShortenerContainer,
)
from src.url_shortener.interface.worker.tasks.cleanup_expired_links_task import (
    cleanup_expired_links_task,
)


async def main() -> None:
    # Mirror the worker bootstrap: build the domain container on the shared
    # CoreContainer and wire the task module so @inject can resolve
    # Provide[UrlShortenerContainer.link_service].
    url_shortener_container = UrlShortenerContainer(core_container=core_container)
    url_shortener_container.wire(
        modules=["src.url_shortener.interface.worker.tasks.cleanup_expired_links_task"]
    )

    # InMemory broker executes the task inline in THIS process.
    result = await cleanup_expired_links_task.kiq()
    task_result = await result.wait_result()
    task_result.raise_for_error()  # wait_result() alone won't re-raise task errors
    print(f"cleanup task deleted {task_result.return_value} expired link(s)")


asyncio.run(main())
PY
```

You should see:

```
cleanup task deleted 1 expired link(s)
```

The expired link is now gone while the permanent one is untouched — confirm it
still resolves:

```bash
curl -sS http://127.0.0.1:8001/v1/link/keep
```
