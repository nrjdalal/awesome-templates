# Error Notification Runbook — Slack / Discord Webhooks

This document covers how to enable and operate the error-notification webhook
feature ([#17](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/17)):
Slack or Discord alerts fired from the FastAPI global exception handlers.

Like every non-DB infrastructure in this blueprint it is **optional** — unset
means `NoopNotificationClient` and the zero-config quickstart boots unchanged
([ADR 042](../history/042-optional-infrastructure-di-pattern.md)).

> Webhook URLs are **credentials**. Possession alone authorizes posting to the
> channel, and there is no separate identifier to revoke — leaking one means
> rotating the webhook itself. Keep real values in gitignored env files only;
> every URL in this document is a non-deployable placeholder.

## What gets alerted

Three call sites dispatch, all in
[`src/_core/exceptions/exception_handlers.py`](../../src/_core/exceptions/exception_handlers.py):

| Source | Status used for gating | Message sent to the channel |
|---|---|---|
| `custom_exception_handler` — any `BaseCustomException` | `exc.status_code` | `str(exc)` → `"{status} [{ERROR_CODE}]: {message}"` |
| `generic_exception_handler` — mapped LLM/provider error | the mapped status | same `"{status} [{ERROR_CODE}]: {message}"` format |
| `generic_exception_handler` — unhandled exception | hard-coded `500` | `f"{type(exc).__name__}: {exc}"` |

A delivered alert therefore looks like this in the channel:

```text
500 [DB_INTERNAL_ERROR]: Internal database error
```

## What does NOT get alerted

This is the part that surprises operators. Coverage is **narrower than "all
errors"** — it is specifically the two dispatching FastAPI handlers above.

| Surface | Why no alert |
|---|---|
| Request validation failures (422) | `validation_exception_handler` never dispatches — regardless of threshold |
| `raise HTTPException(...)`, incl. `status_code=500` | `http_exception_handler` never dispatches — a 500 raised this way is silent |
| **Taskiq worker task failures** | the worker installs logging + retry middleware only ([`src/_apps/worker/bootstrap.py`](../../src/_apps/worker/bootstrap.py)) — no notifier is wired |
| **NiceGUI admin page / callback exceptions** | `handle_uncaught_admin_exception` is log-only by design ([`src/_core/infrastructure/admin/error_handler.py`](../../src/_core/infrastructure/admin/error_handler.py)) |
| Anything below `NOTIFICATION_SEVERITY_THRESHOLD` | gated in `ErrorNotifier._should_notify` |

If background job failures matter to you, alerting on them is a **separate
integration** — the exception handlers are HTTP-request-scoped and never run in
the worker process. Treat the log aggregator as the primary signal for worker
and admin failures. Whether the worker should dispatch too is open in
[#310](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/310).

## Setup

### 1. Create the webhook

- **Slack** — create an app, enable *Incoming Webhooks*, add a webhook to the
  target channel. Slack's docs: <https://api.slack.com/messaging/webhooks>
- **Discord** — channel *Settings → Integrations → Webhooks → New Webhook*, then
  *Copy Webhook URL*. Discord's docs:
  <https://support.discord.com/hc/en-us/articles/228383668>

The two adapters differ only in payload key and success response, which is why
neither response body is JSON-parsed:

| Provider | Payload | Success response |
|---|---|---|
| Slack | `{"text": "..."}` | `200` with a plain-text `ok` body |
| Discord | `{"content": "..."}` | `204 No Content` (empty body) |

### 2. Point the blueprint at it

```bash
# Slack
NOTIFICATION_PROVIDER=slack \
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/... \
uv run python run_server_local.py --env local

# Discord
NOTIFICATION_PROVIDER=discord \
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... \
uv run python run_server_local.py --env local
```

Commented blocks are already in `_env/local.env.example` and
`_env/quickstart.env.example` — uncomment and fill in the real value in your
gitignored `_env/*.env`.

Configuration is validated as a **complete group at boot**: an unknown provider,
or a provider whose matching `*_WEBHOOK_URL` is missing, fails startup rather
than surfacing at first-error dispatch — the moment the system is already
failing.

## Configuration reference

| Env var | Default | What it does |
|---|---|---|
| `NOTIFICATION_PROVIDER` | unset | `slack` or `discord`. Unset → notifications disabled |
| `SLACK_WEBHOOK_URL` | unset | Required when provider is `slack` |
| `DISCORD_WEBHOOK_URL` | unset | Required when provider is `discord` |
| `NOTIFICATION_SEVERITY_THRESHOLD` | `500` | Minimum status code that alerts. `500` = server errors only |
| `NOTIFICATION_COOLDOWN_SECONDS` | `60` | Per-process, per-`error_code` quiet window between repeat alerts |

## Behaviour details

### Severity threshold

Gating compares the response status against the threshold, so the default `500`
means 4xx client errors never alert.

**Do not lower this to a 4xx value in a deployed environment.** Routine client
errors are alert-worthy to nobody: with `NOTIFICATION_SEVERITY_THRESHOLD=401`,
three ordinary unauthenticated requests — a wrong password, an expired token, a
missing token — produce three alerts. It is a useful *local test* setting (see
[Verify locally](#verify-locally)) and a channel-flooding mistake in production.

### Cooldown — and its per-process caveat

`ErrorNotifier` keeps an in-memory dict keyed by `error_code`
([`error_notifier.py`](../../src/_core/infrastructure/notification/error_notifier.py)),
so within the cooldown window a repeated `error_code` is suppressed while a
*different* `error_code` alerts immediately.

That dict lives in **one process**. `ErrorNotifier` is a container Singleton,
which makes it per-process, not per-deployment:

```text
4 uvicorn workers x 3 replicas = 12 independent cooldown windows
→ up to 12 alerts per window for the same error_code, not 1
```

Size the cooldown against your process count, not against your alert tolerance.
There is no shared store (Redis, DB) behind this — cross-process deduplication
would be a new feature, not a config change.

### Fire-and-forget dispatch

`maybe_dispatch` never awaits the webhook call — it schedules an
`asyncio.create_task` and returns, so a slow or hanging webhook endpoint adds
**zero latency** to the request path, and a dispatch failure can never turn into
a second error for the caller.

The trade-off is that delivery is best-effort: there is no retry and no queue. A
webhook that is down during an incident simply loses those alerts. The HTTP
timeout comes from the shared `HttpClient` — total 10s outside prod, 30s in prod
([`http_client.py`](../../src/_core/infrastructure/http/http_client.py)).

## Disabled path

With no `NOTIFICATION_PROVIDER`, the container resolves
`NoopNotificationClient` and `ErrorNotifier` still runs and still gates.

Two log lines mark this state
([`noop_notification_client.py`](../../src/_core/infrastructure/notification/noop_notification_client.py)):

| Event | Level | When |
|---|---|---|
| `notification_client_disabled` | `warning` | once per process, at the **first dispatch attempt** |
| `notification_suppressed` | `info` | every suppressed alert, with the full `message` field |

The `notification_client_disabled` warning is **lazy, not a startup line** — the
client is a lazily-resolved Singleton, so a freshly booted server logs nothing
until its first error at or above the threshold. Grepping the boot log for it
proves nothing.

Note the second line: while disabled, the alert text is written into your log
stream at `INFO`. That is normally redundant with the exception log, but it does
mean lowering the threshold on a disabled deployment adds `INFO` noise for every
gated error.

## Production caveat: the payload is un-redacted exception text

**Nothing sanitizes the message before it leaves the process.** Which text goes
out depends on which handler catches the error, and the difference matters:

| Exception kind | Message sent | Data-exposure risk |
|---|---|---|
| `BaseCustomException` subclass | `str(exc)` renders only status, `error_code`, and the curated `message` — `details` is **not** rendered | low: the message is text you wrote |
| Anything else (reaches `generic_exception_handler`) | `f"{type(exc).__name__}: {exc}"` — the exception's own `__str__`, verbatim | **high: whatever the library chose to put in its message** |

The second row is the one to plan around, because library `__str__`
implementations routinely include the offending values:

```text
IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed: user.email
[SQL: INSERT INTO user (email, ...) VALUES (?, ...)]
[parameters: ('alice@example.com', ...)]
```

```text
ValidationError: 1 validation error for M
age
  Input should be a valid integer, unable to parse string as an integer
  [type=int_parsing, input_value='alice@example.com', input_type=str]
```

Standard RDB access does **not** take that path: `Database.session()` wraps
driver errors into curated `DatabaseException`s — a unique-constraint violation
becomes `400 [DB_INTEGRITY_ERROR]: Data integrity error`, which is below the
default threshold and carries no SQL. The raw path opens where an exception
escapes un-wrapped: code that manages its own session (`ai_usage_repository`
re-raises a bare `IntegrityError` on a genuine insert conflict), an internal
Pydantic validation failure, or any unmapped third-party SDK error.

So a rare, unhandled failure can carry a customer's email address into a chat
channel — a destination that typically has a **broader audience and different
retention** than your log aggregator, and that sits outside whatever
data-processing agreement covers your logging vendor. Treat the notification
channel as a system that receives production data.

Mitigations that need no code change:

- **Keep the default threshold (`500`).** Curated domain exceptions cluster in
  4xx; the un-redacted risk is concentrated in unhandled 500s, and lowering the
  threshold adds volume without adding signal.
- **Restrict the channel.** A private channel with need-to-know membership, not a
  broad `#engineering`.
- **Scope by environment.** Enable it in stg first and see what real payloads look
  like in your own domain before enabling prod.
- **Treat the channel as in-scope for data handling.** Include it in retention and
  access reviews alongside the log aggregator.

If that is not enough for your compliance posture, the remaining options are to
leave notifications disabled and alert from the log aggregator instead, or to
introduce a redaction/allowlist message format — a code change, not covered here.

## Verify locally

You do not need a Slack or Discord account to prove the pipeline works. Point
the webhook URL at a local sink — any HTTP server that accepts a POST.

```bash
# 1. Terminal A — a sink that prints whatever it receives
python3 - <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        print("RECEIVED", self.rfile.read(n).decode(), flush=True)
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 9099), H).serve_forever()
PY
```

```bash
# 2. Terminal B — quickstart, pointed at the sink, threshold lowered to 401
#    so an ordinary failed login is enough to trigger a dispatch
NOTIFICATION_PROVIDER=slack \
SLACK_WEBHOOK_URL=http://127.0.0.1:9099/hook \
NOTIFICATION_SEVERITY_THRESHOLD=401 \
uv run python run_server_local.py --env quickstart
```

```bash
# 3. Terminal C — trigger a 401
curl -s -X POST http://127.0.0.1:8001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"nobody","password":"wrong-password"}'
```

Terminal A prints the exact payload the blueprint would have sent to Slack:

```text
RECEIVED {"text": "401 [INVALID_CREDENTIALS]: Invalid credentials"}
```

Two further probes worth running while you are set up:

- **Repeat step 3 immediately.** No second delivery — the `INVALID_CREDENTIALS`
  cooldown is active. Then `curl http://127.0.0.1:8001/v1/auth/me` with no token:
  a *different* `error_code` (`UNAUTHORIZED`) delivers straight away.
- **Send a malformed body** (omit `username`). The 422 is not delivered, even
  though `422 >= 401` — confirming validation errors never alert.

To validate a real webhook URL instead, swap `SLACK_WEBHOOK_URL` for the real
value in step 2 and watch the channel. Revert the threshold to `500` afterwards.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Boot fails: `[Notification/Slack] ... slack_webhook_url missing` | provider set without its URL | set the matching `*_WEBHOOK_URL`, or unset the provider |
| Boot fails: `Unknown notification provider` | typo in `NOTIFICATION_PROVIDER` | use `slack` or `discord` |
| No alerts, `notification_client_disabled` in logs | provider unset → Noop client | set `NOTIFICATION_PROVIDER` + the matching URL |
| No alerts, no notification logs at all | errors are below the threshold, or the failing surface does not dispatch | check [What does NOT get alerted](#what-does-not-get-alerted) |
| A `raise HTTPException(status_code=500)` produces no alert | `http_exception_handler` does not dispatch | raise a `BaseCustomException` subclass instead |
| `error_notification_send_failed` with `exc_type` only | the webhook POST failed — status and URL are deliberately not logged | `curl` the webhook URL directly to see the real response |
| Worker task failed, no alert | the worker never dispatches | expected — alert from the log aggregator |
| Same error alerted N times within the cooldown | N processes, N cooldown windows | see [the per-process caveat](#cooldown--and-its-per-process-caveat) |
| Alert delivered but nothing in the logs | a successful send logs nothing by design | confirm in the channel, not the log |

`error_notification_send_failed` is intentionally sparse: `aiohttp`'s error
message embeds the request URL, so logging the exception would write the webhook
credential into the log stream. Only the exception class name is recorded.

## Related

- [#17](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/17) /
  [PR #304](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/304) — the
  feature
- [#286](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/286) —
  channel routing by severity (critical → `#alerts`, warnings → `#monitoring`),
  a follow-up
- [#310](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/310) —
  whether worker task failures and admin exceptions should alert, a follow-up
- [ADR 042](../history/042-optional-infrastructure-di-pattern.md) — the
  Protocol + Selector pattern behind the optional/disabled split
- `docs/ai/shared/security-checklist.md` §13 — the reviewer-facing counterpart to
  this runbook
