# Error Notification Runbook — Slack / Discord Webhooks

This document covers how to enable and operate the error-notification webhook
feature ([#17](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/17)):
Slack or Discord alerts fired from the FastAPI global exception handlers and
from Taskiq worker task failures
([#310](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/310)).

Like every non-DB infrastructure in this blueprint it is **optional** — unset
means `NoopNotificationClient` and the zero-config quickstart boots unchanged
([ADR 042](../history/042-optional-infrastructure-di-pattern.md)).

> Webhook URLs are **credentials**. Possession alone authorizes posting to the
> channel, and there is no separate identifier to revoke — leaking one means
> rotating the webhook itself. Keep real values in gitignored env files only;
> every URL in this document is a non-deployable placeholder.

## What gets alerted

Four call sites dispatch. Three are HTTP, in
[`src/_core/exceptions/exception_handlers.py`](../../src/_core/exceptions/exception_handlers.py);
the fourth is the worker middleware covered in
[Worker task failures](#worker-task-failures):

| Source | Status used for gating | Message sent to the channel |
|---|---|---|
| `custom_exception_handler` — any `BaseCustomException` | `exc.status_code` | `str(exc)` → `"{status} [{ERROR_CODE}]: {message}"` |
| `generic_exception_handler` — mapped LLM/provider error | the mapped status | same `"{status} [{ERROR_CODE}]: {message}"` format |
| `generic_exception_handler` — unhandled exception | hard-coded `500` | `f"{type(exc).__name__}: {exc}"` |
| `TaskFailureNotificationMiddleware` — terminal task failure | `exc.status_code` for `BaseCustomException`, otherwise `500` | `f"Task '{task_name}' failed: {type(exc).__name__}: {exc}"` |

A delivered HTTP alert therefore looks like this in the channel:

```text
500 [DB_INTERNAL_ERROR]: Internal database error
```

## What does NOT get alerted

This is the part that surprises operators. Coverage is **narrower than "all
errors"** — it is the two dispatching FastAPI handlers above plus the worker
middleware described in [Worker task failures](#worker-task-failures).

| Surface | Why no alert |
|---|---|
| Request validation failures (422) | `validation_exception_handler` never dispatches — regardless of threshold |
| `raise HTTPException(...)`, incl. `status_code=500` | `http_exception_handler` never dispatches — a 500 raised this way is silent |
| **NiceGUI admin page / callback exceptions** | `handle_uncaught_admin_exception` is log-only **by decision**, not by omission — see below |
| Anything below the alerting floor | gated in `ErrorNotifier._should_notify`. The floor is `NOTIFICATION_SEVERITY_THRESHOLD`, or `min(severity, NOTIFICATION_WARNING_THRESHOLD)` once [channel routing](#severity-based-channel-routing) is enabled |

The first two are pinned by negative tests
(`tests/unit/_core/exceptions/test_exception_handlers_notification.py`), so they
are guarantees rather than current behaviour.

**Why admin exceptions stay silent.** An admin error that reaches
`AdminErrorHandler` already surfaces to the operator — a toast, or a redirect to
`/admin/error` with the correlation id. Alerting would page someone about a
failure a human is actively looking at. The same handler does also fire outside
a client/slot context (a post-success `refresh`, a timer), where nothing reaches
the UI; those are left to the log aggregator deliberately rather than justifying
a second alerting path. Decided in
[#310](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/310) and
recorded in `AGENTS.md` § Optional Infrastructure Toggles.

## Worker task failures

Taskiq task failures **do** alert, through
`TaskFailureNotificationMiddleware`
([`src/_core/infrastructure/notification/taskiq_middleware.py`](../../src/_core/infrastructure/notification/taskiq_middleware.py)),
registered in [`src/_apps/worker/bootstrap.py`](../../src/_apps/worker/bootstrap.py).
No extra configuration — the same `NOTIFICATION_*` variables apply.

A task has no HTTP request and no status code, so three things differ from the
HTTP path:

| | Behaviour |
|---|---|
| **Severity** | Synthesised. A `BaseCustomException` keeps its own `status_code`; anything else counts as **500**. So the same alerting floor applies. Without routing, raising `NOTIFICATION_SEVERITY_THRESHOLD` above 500 silences ordinary task failures too. With routing the floor is `min(severity, warning)` and the tier depends on both boundaries: a synthetic 500 is **critical** while `NOTIFICATION_SEVERITY_THRESHOLD <= 500`; it lands in the **warning** tier only when the severity threshold is above 500 *and* `NOTIFICATION_WARNING_THRESHOLD` is at or below **500** — raise both above 500 (e.g. `600` / `550`) and the failure clears neither band, so it alerts nowhere |
| **Cooldown key** | `{task_name}:{error_code}`, not the bare `error_code` used on the HTTP path. Without the task prefix one repeatedly-failing task would suppress every other task's alert for the whole window. With [channel routing](#severity-based-channel-routing) enabled the two scopings compose, giving `{tier}:{task_name}:{error_code}` |
| **Timing** | One alert per incident, on the **terminal** failure. Permanent errors (`BaseCustomException`, `ValueError`, `TypeError`, Pydantic `ValidationError`) are never retried and alert immediately; retryable ones alert only after the final attempt fails |

The message format is:

```text
Task 'src.docs.tasks.reindex' failed: ConnectionResetError: [Errno 54] Connection reset by peer
```

Two consequences worth planning for:

- **A transient failure is reported late.** With the default 3 attempts and
  exponential backoff, the alert lands after the retries are exhausted — tens of
  seconds, not instantly. That is the trade for not alerting three times per
  incident. The `taskiq_task_failed` log line still fires on *every* attempt, so
  the log aggregator remains the low-latency signal.
- **The worker is a separate process**, so it keeps its own cooldown windows,
  independent of the server's — see
  [the per-process caveat](#cooldown--and-its-per-process-caveat).

> **Payload caution.** The alert embeds `str(exception)`, and a task's exception
> text can carry its arguments — a task taking an email or an account id may put
> that value into a third-party chat channel. This is the same un-redacted-text
> property the HTTP path has, but task payloads are internal data that never
> passed through a Response-level `exclude`, so review what your tasks raise
> before enabling this in production.

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

Configuration is validated as a **complete group at boot** rather than surfacing
at first-error dispatch — the moment the system is already failing. Five
conditions fail startup:

- an unknown `NOTIFICATION_PROVIDER`;
- a provider whose matching `*_WEBHOOK_URL` is missing;
- `NOTIFICATION_WARNING_THRESHOLD` at or above `NOTIFICATION_SEVERITY_THRESHOLD`;
- a per-tier `*_WEBHOOK_URL` without `NOTIFICATION_PROVIDER`;
- a per-tier `*_WEBHOOK_URL` without `NOTIFICATION_WARNING_THRESHOLD` — that
  setting is what wires the router, so the URLs would otherwise be silently
  ignored.

The last three are tagged `[Notification/Routing]` in the failure message.

## Configuration reference

| Env var | Default | What it does |
|---|---|---|
| `NOTIFICATION_PROVIDER` | unset | `slack` or `discord`. Unset → notifications disabled |
| `SLACK_WEBHOOK_URL` | unset | Required when provider is `slack` |
| `DISCORD_WEBHOOK_URL` | unset | Required when provider is `discord` |
| `NOTIFICATION_SEVERITY_THRESHOLD` | `500` | Status code at or above which an alert is sent. `500` = server errors only. Without routing this is also the alerting floor; with routing it becomes the **critical-tier boundary** and the floor drops to the warning threshold |
| `NOTIFICATION_COOLDOWN_SECONDS` | `60` | Per-process quiet window between repeat alerts. Keyed by `error_code`; `{tier}:{error_code}` under routing, and task-scoped on the worker |
| `NOTIFICATION_WARNING_THRESHOLD` | unset | **The routing switch.** Set it below `NOTIFICATION_SEVERITY_THRESHOLD` to also alert on a lower band and send that band to the warning channel. Unset → no routing at all |
| `NOTIFICATION_CRITICAL_WEBHOOK_URL` | unset | Target for the critical tier. Falls back to the single provider webhook. Requires `NOTIFICATION_WARNING_THRESHOLD` |
| `NOTIFICATION_WARNING_WEBHOOK_URL` | unset | Target for the warning tier. Falls back to the single provider webhook. Requires `NOTIFICATION_WARNING_THRESHOLD` |

## Behaviour details

### Severity threshold

Gating compares the response status against the threshold, so the default `500`
means 4xx client errors never alert.

**Do not lower `NOTIFICATION_SEVERITY_THRESHOLD` to a 4xx value in a deployed
environment.** It is the *critical* boundary, so lowering it reclassifies routine
client errors as incidents and sends them to whichever channel your on-call
watches: with `NOTIFICATION_SEVERITY_THRESHOLD=401`, three ordinary
unauthenticated requests — a wrong password, an expired token, a missing token —
produce three critical alerts. It remains a useful *local test* setting (see
[Verify locally](#verify-locally)).

**If you do want 4xx visibility, that is what channel routing is for.** Set
`NOTIFICATION_WARNING_THRESHOLD=400` and leave the severity threshold at `500`:
the 4xx band then alerts into a separate low-noise channel while genuine 5xx
incidents keep their own. See
[Severity-based channel routing](#severity-based-channel-routing).

### Severity-based channel routing

Optional, off by default (#286). `NOTIFICATION_WARNING_THRESHOLD` is the only
switch — set it below `NOTIFICATION_SEVERITY_THRESHOLD` and two things change:

- **The alerting floor drops** to `min(severity, warning)`, so a band that never
  alerted before now does.
- **Each band gets its own target.** `>= NOTIFICATION_SEVERITY_THRESHOLD` goes to
  `NOTIFICATION_CRITICAL_WEBHOOK_URL`; the band between the two thresholds goes
  to `NOTIFICATION_WARNING_WEBHOOK_URL`. Either override left unset falls back to
  the single provider webhook, so a partial mapping degrades to a shared channel
  rather than dropping a tier.

```text
NOTIFICATION_SEVERITY_THRESHOLD=500   NOTIFICATION_WARNING_THRESHOLD=400

  399 →  no alert
  404 →  warning channel
  499 →  warning channel
  500 →  critical channel
  503 →  critical channel
```

The per-tier URLs are **not** switches. Setting one without
`NOTIFICATION_WARNING_THRESHOLD` fails at boot (#315) — without the threshold no
router is wired at all, so both URLs would be silently ignored while every alert
went to the single provider webhook.

**The cooldown key becomes tier-scoped** in this mode. That is not cosmetic:
`BaseCustomException` takes `status_code` and `error_code` as per-instance
arguments, so a 404 and a 500 can share an `error_code` with no subclass
involved. On a bare key the 404 would consume the 500's quiet window and swallow
the incident alert. Tier-prefixing keeps the two windows separate; on the worker
path the two scopings compose to `{tier}:{task_name}:{error_code}`.

Unset, every one of these reduces to the #17 single-target behaviour: no router,
floor at `NOTIFICATION_SEVERITY_THRESHOLD`, bare `error_code` key.

### Cooldown — and its per-process caveat

`ErrorNotifier` keeps an in-memory dict keyed by a **cooldown key**
([`error_notifier.py`](../../src/_core/infrastructure/notification/error_notifier.py)),
so within the cooldown window a repeated key is suppressed while a *different*
key alerts immediately. The key is the bare `error_code` by default; the worker
path prefixes the task name (#310), and channel routing prefixes the severity
tier (#286), so the widest form is `{tier}:{task_name}:{error_code}`.

That dict lives in **one process**. `ErrorNotifier` is a container Singleton,
which makes it per-process, not per-deployment:

```text
4 uvicorn workers x 3 replicas = 12 independent cooldown windows
→ up to 12 alerts per window for the same cooldown key, not 1
```

Count your Taskiq worker processes too — each one holds its own `ErrorNotifier`
and its own window, separate from every server process.

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
- **Give the warning channel the same treatment as the critical one.** Opening a
  warning band with `NOTIFICATION_WARNING_THRESHOLD` normally admits only curated
  `BaseCustomException` text — `__str__` renders `status_code`, `error_code` and
  `message`, and deliberately omits `details`. Both un-redacted paths
  (`generic_exception_handler`, and the worker's synthetic status for a
  non-`BaseCustomException`) are scored **500**, so on the default
  `NOTIFICATION_SEVERITY_THRESHOLD=500` they resolve *critical* and never reach
  the warning channel. **That stops being true if you raise the severity
  threshold above 500** — with `severity=600, warning=400`, a 500 falls into the
  warning band and the un-redacted text goes there. Either keep the severity
  threshold at or below 500, or treat the warning channel as receiving the same
  data class as the critical one: same restriction, environment scoping, and
  retention/access review.
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

### Two-sink variant — proving channel routing

The recipe above lowers `NOTIFICATION_SEVERITY_THRESHOLD` because it predates
#286. To exercise routing instead, run a **second** sink on port `9098` (same
script, different port) and keep the severity threshold at its default:

```bash
NOTIFICATION_PROVIDER=slack \
SLACK_WEBHOOK_URL=http://127.0.0.1:9099/base \
NOTIFICATION_WARNING_THRESHOLD=401 \
NOTIFICATION_CRITICAL_WEBHOOK_URL=http://127.0.0.1:9099/alerts \
NOTIFICATION_WARNING_WEBHOOK_URL=http://127.0.0.1:9098/monitoring \
uv run python run_server_local.py --env quickstart
```

The 401 from step 3 now arrives on port `9098` (warning), while a 5xx arrives on
`9099` (critical) — and the base URL receives nothing. This is also the cheapest
regression probe for two behaviours worth keeping honest:

- **Drop `NOTIFICATION_WARNING_THRESHOLD`** from the block above and the server
  refuses to boot, rather than silently routing everything to `/base` (#315).
- **Tier-scoped cooldown.** Raise a `BaseCustomException(status_code=404)` and a
  `BaseCustomException(status_code=500)` back to back; both use the default
  `error_code` of `CUSTOM_ERROR`, and both must deliver — the 4xx must not
  consume the 5xx's cooldown window.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Boot fails: `[Notification/Slack] ... slack_webhook_url missing` | provider set without its URL | set the matching `*_WEBHOOK_URL`, or unset the provider |
| Boot fails: `Unknown notification provider` | typo in `NOTIFICATION_PROVIDER` | use `slack` or `discord` |
| Boot fails: `[Notification/Routing] ... must be less than NOTIFICATION_SEVERITY_THRESHOLD` | warning threshold at or above the severity threshold — the bands would overlap | lower `NOTIFICATION_WARNING_THRESHOLD`, or raise the severity threshold |
| Boot fails: `[Notification/Routing] ... require NOTIFICATION_PROVIDER` | per-tier URL set with no provider — the URLs select a channel *within* a provider, not a transport | set `NOTIFICATION_PROVIDER` |
| Boot fails: `[Notification/Routing] ... require NOTIFICATION_WARNING_THRESHOLD` | per-tier URL set without the routing switch, so no router would be wired and both URLs would be ignored | set `NOTIFICATION_WARNING_THRESHOLD` below the severity threshold, or remove the per-tier URLs |
| No alerts, `notification_client_disabled` in logs | provider unset → Noop client | set `NOTIFICATION_PROVIDER` + the matching URL |
| No alerts, no notification logs at all | errors are below the threshold, or the failing surface does not dispatch | check [What does NOT get alerted](#what-does-not-get-alerted) |
| A `raise HTTPException(status_code=500)` produces no alert | `http_exception_handler` does not dispatch | raise a `BaseCustomException` subclass instead |
| `error_notification_send_failed` with `exc_type` only | the webhook POST failed — status and URL are deliberately not logged | `curl` the webhook URL directly to see the real response |
| Worker task failed, no alert yet | retryable failures alert only after the final attempt | wait out the retries, or check `taskiq_task_failed` in the log for per-attempt detail |
| Worker task failed, never any alert | the failure is below the alerting floor — a `BaseCustomException` with a 4xx `status_code` | set `NOTIFICATION_WARNING_THRESHOLD` below that status so it alerts into the warning channel (preferred), or raise a 5xx-status exception. Lowering `NOTIFICATION_SEVERITY_THRESHOLD` also works but reclassifies the failure as critical |
| Admin page error, no alert | admin exceptions are log-only by decision | expected — see [What does NOT get alerted](#what-does-not-get-alerted) |
| Same error alerted N times within the cooldown | N processes, N cooldown windows | see [the per-process caveat](#cooldown--and-its-per-process-caveat) |
| Alert delivered but nothing in the logs | a successful send logs nothing by design | confirm in the channel, not the log |

`error_notification_send_failed` is intentionally sparse: `aiohttp`'s error
message embeds the request URL, so logging the exception would write the webhook
credential into the log stream. Only the exception class name is recorded.

## Related

- [#17](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/17) /
  [PR #304](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/304) — the
  feature
- [#310](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/310) —
  extended dispatch to worker task failures and recorded operator-facing admin
  failures as an explicit non-goal
- [#286](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/286) /
  [PR #313](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/313) —
  [severity-based channel routing](#severity-based-channel-routing) (critical →
  `#alerts`, warnings → `#monitoring`)
- [#315](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/315) —
  made a per-tier webhook URL without `NOTIFICATION_WARNING_THRESHOLD` a boot
  failure instead of a silently ignored setting
- [ADR 042](../history/042-optional-infrastructure-di-pattern.md) — the
  Protocol + Selector pattern behind the optional/disabled split
- `docs/ai/shared/security-checklist.md` §13 — the reviewer-facing counterpart to
  this runbook
