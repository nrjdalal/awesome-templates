# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.11.0] - 2026-08-13

### Added

- **The type check now covers the whole repository.** `[tool.pyright] include` went
  from an allow-list of five packages to `src`, `tools`, `scripts`, `examples`,
  `.agents`, the three harness hook directories and the three root runners — 684
  files at 0 errors, from a starting 91. `uv run pyright` reproduces the blocking
  CI job exactly. `reportUnnecessaryTypeIgnoreComment` is on, so a suppression that
  stops being needed becomes an error rather than permanent debt; the 21 that remain
  are pinned by file and count in `tests/unit/tools/test_pyright_scope.py`
  ([#381](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/381),
  [#387](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/387))

- **`types-aioboto3` and `types-aiobotocore-s3vectors` join the `aws` extra.**
  Without the first, `aioboto3.Session.client()` resolved to an untypeable
  placeholder and every `async with … .client()` block was unchecked; without the
  second, the four S3 Vectors API calls had never been type-checked at all. Both are
  type stubs — no runtime behaviour changes
  ([#381](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/381))

- **`BaseRepository.count_datas_by_day` / `BaseService.count_datas_by_day`** — rows
  per calendar day at or after a bound, returning the new frozen
  `DailyCount` VO. Two dialect differences are absorbed in the base class per the
  ADR 058 guarantee, and both were measured rather than assumed: `cast(column,
  Date)` **fails on SQLite** (`TypeError: fromisoformat: argument must be str`),
  which is the quickstart default, so `func.date` is used; and `func.date`
  returns `str` on SQLite but `datetime.date` on PostgreSQL, so callers get
  `datetime.date` on every engine. A missing or non-temporal column raises a
  curated `400 DB_TIME_FIELD_UNUSABLE` rather than an empty list that would read
  as "no data". Days with no rows are absent, not zero-filled — gap-filling is a
  caller policy. MySQL still rests on documentation rather than a test, per ADR
  058's stated limit
  ([#368](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/368))

### Changed

- **The pre-commit `mypy` hook is removed; pyright is the only type checker.** The
  hook could not type-check anything: two harness copies of `completion_gate.py` map
  to one top-level module name, so mypy aborted during module resolution, reported
  that single error and inspected no source at all. Because it was `stages: [manual]`
  nothing ever ran it, so one error and zero findings read as coverage for two
  releases. Repairing it would still have been shallow — its only
  `additional_dependencies` were `types-requests` and `pydantic`, so under
  `--ignore-missing-imports` every fastapi / sqlalchemy / nicegui type resolved to
  `Any`. 96 orphaned `# type: ignore` comments were deleted as part of this and none
  was replaced by a pyright suppression. **For forks:** drop `mypy` from any local
  workflow that invoked the manual stage and use `uv run pyright`
  ([#375](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/375))

- **The admin dashboard is two columns.** The sections were full-width and stacked,
  which at 1920px meant a 1588×260 plot holding one bar, an infrastructure table
  giving 488px each to `active` and `sqlite`, and three stat tiles huddled in 294px.
  Main content and an aside now split `col-12 col-md-8` / `col-12 col-md-4`,
  collapsing to one column below `md`; content height drops 1186 → 771px (onboarding
  1148 → 640px). The infrastructure panel is a compact status list rather than an AG
  Grid — `c.data_grid` is the list-page builder and brought `selection="single"` with
  it, i.e. row-selection radios on a panel with no row action. **For forks:**
  `c.stat_card` now carries a minimum width (`--admin-stat-card-min-width`, 150px) so
  a row of tiles lines up, and `.admin-status-dot` with two state hues is new
  ([#380](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/380))

- **BREAKING (admin UI) — the dashboard answers different questions.** It now
  reports which optional infrastructure is live, stubbed or absent; agent-call
  volume with a failure rate over 7 days; and new records per day. The
  audit-derived sections are **removed**, and so is the collection behind them:
  `/admin/audit-log` is a strict superset with filtering and pagination, so the
  landing page was reading audit data to render a worse copy of a page that
  already existed — one fewer audit read per load. A fresh install, where every
  count is 0, now gets a distinct onboarding view naming the next action instead
  of a page of zeros. Failure counts are derived as `total - ok` rather than
  summed over the known failure states, so a `UsageStatus` value added later
  cannot be silently counted as success; `failure_rate` is `None` rather than
  `0.0` when there were no calls
  ([#368](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/368))

- **BREAKING — admin restyled to a single neutral-mono theme.** A desaturated
  Tailwind **zinc** ramp carries the UI, a *single* blue accent (`#2563eb`)
  marks interactive/active state, and three status hues (`#16a34a` / `#dc2626` /
  `#d97706`) are reserved for outcomes. Shape drops from `20px` cards and pill
  buttons to `8px` / `6px`; elevation gives way to hairline borders; the login
  gradient becomes a flat surface; AG Grid rows tighten from `44px` to `36px`
  and separate by border instead of zebra striping. `theme.py` now holds
  **three** token dicts — `_BRAND_TOKENS` (Quasar `--q-*`, emitted under `body`),
  `_ROOT_TOKENS`, `_DARK_TOKENS` — and rebranding a fork is usually just
  `AdminColors.PRIMARY`
  ([#365](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/365))

- **BREAKING — the bundled Wanted Sans webfont is removed** in favour of a
  system font stack with Hangul fallbacks. That also removes
  `src/_apps/admin/static/` (a 1.29 MB `woff2` + its `OFL.txt`) and the
  `app.add_static_files("/admin-static", ...)` mount in
  `src/_apps/admin/bootstrap.py`, which existed only to serve that font. The
  emitted admin CSS now contains no `@font-face` and no `url(` at all, so the
  panel makes no third-party request on load
  ([#365](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/365))

### Fixed

- **`make scheduler` had never run the scheduler.** `run_scheduler_local.py` called
  taskiq's `run_scheduler(args)` without awaiting it — the file says it mirrors
  `run_worker_local.py`, and it did so literally, but `run_worker` is sync while
  `run_scheduler` is a coroutine function. The process emitted
  `coroutine 'run_scheduler' was never awaited` and exited 0 having scheduled
  nothing, so `audit_cleanup_task` (`0 3 * * *`, the audit-log retention `DELETE`)
  never fired from the path the docs point at. Now wrapped in `asyncio.run`, exactly
  as taskiq's own `SchedulerCMD.exec` does, and pinned by
  `tests/unit/test_local_runners.py`. **If you relied on `make scheduler` for audit
  retention, that job has not been running** — the same `@broker.task` is still
  reachable from external cron or a k8s `CronJob`
  ([#375](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/375))

- **A failed worker start exited 0.** `run_worker_local.py` discarded the status code
  `run_worker` returns, so a supervisor could not tell a crashed worker from a clean
  shutdown. Propagated now
  ([#375](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/375))

- **`ObjectStorage.list_files` raised `KeyError` on a keyless object.** `Key` is
  optional in the `list_objects_v2` response model and the code subscripted it
  directly. Such entries are now skipped: this method's contract is "keys you can
  address", and an empty string handed to `download_file` or `delete_file` is worse
  than a shorter list
  ([#381](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/381))

- **`make test-pg` failed against a database that already held the schema.**
  `Base.metadata` was populated only by whatever models the selected tests happened
  to import, so the fixture's `drop_all` could try to drop `user` before
  `refresh_token` and PostgreSQL refused — every test then errored at *setup*, which
  reads as a broken change rather than partial metadata. `tests/conftest.py` now
  calls `load_models()` at import time; SQLite hid it by enforcing no FKs and
  starting from a fresh in-memory database
  ([#374](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/374))

- **The dashboard's activity grid reserved viewport height and left a ~200px
  empty box.** #365 made this worse rather than causing it: shortening rows from
  44px to 36px while the container height stayed fixed grew the void. Adds
  `c.data_grid(auto_height=True)`, which derives the height from the row count —
  for **caller-bounded** grids only. Deliberately **not** AG Grid's
  `domLayout: "autoHeight"`, which is broken in the NiceGUI embed: the inner
  wrapper grows to 339px while the outer element keeps Quasar's 256px, so the
  grid paints over the following section. A test fails if `domLayout` is ever
  emitted again
  ([#368](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/368))

- **The dashboard's Quick Actions section duplicated the sidebar below the fold.**
  One nav card per domain — the same destinations the left drawer lists —
  rendered ~1300px down the page. Removed; with the grid fix the dashboard went
  from 1439px to 1094px
  ([#368](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/368))

- **The admin login screen's failure message was a toast.** `ui.notify` fades, so a
  few seconds after a rejected attempt the screen showed no reason for it and the
  operator was left re-reading a form that looked fine. It now writes into a
  persistent slot above the fields, cleared at the start of the next attempt.
  `Enter` also did nothing in the username field — only the password field was
  wired — which mattered once autofocus moved to username. All three rejection
  causes still collapse to one message on purpose, so the form cannot be used to
  probe which admin usernames exist. The identity block is recomposed from three
  stacked elements (a 3rem icon, the brand name, a letterspaced `ADMIN`) into one
  row plus `Administrator sign-in`, and the card's contents are left-aligned
  ([#368](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/368))

- **The new infrastructure panel was visible to any authenticated admin.**
  `require_auth_allowlisted()` authenticates the dashboard without checking page
  permissions, so an admin holding zero grants could read the deployment's
  configuration posture — and "Error notification: stub" tells such a holder that
  failures raise no alert. Now gated on the `accounts` permission, with the
  onboarding stub hints behind the same gate because they restate the same rows in
  prose. `security-checklist.md` §2 gains the rule that was missing: the previous
  equivalent principle lived only in a code comment, which is why removing it
  broke nothing
  ([#368](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/368))


- **The Quasar `--q-*` brand palette had never applied.** NiceGUI writes its own
  brand palette as an **inline style on `<body>`** (`--q-primary: #5898d4`, teal
  secondary, purple accent, cyan info). An inline declaration outranks every
  stylesheet rule regardless of selector specificity, so `theme.py` declaring
  `--q-*` in `:root` — as it did from #193 through #235 — was inert: `html`
  carried the project value, `body` re-declared NiceGUI's, and every descendant
  inherited NiceGUI's. Measured on the live page as `rootVar #2563eb` /
  `bodyVar #5898d4`. In practice every button, badge and `text-primary` label
  rendered NiceGUI's defaults *beside* the `--admin-*` greys — a third palette on
  screen, and the larger reason the admin colours never looked coherent. The
  brand group is now emitted under `body` with `!important`, which does outrank a
  normal inline declaration, keeping the inject-once-app-wide model with no
  per-page `ui.colors()` call. `--q-dark` / `--q-dark-page` are set as well so
  Quasar's own dark menus, dialogs and selects land on the zinc ladder instead of
  `#1d1d1d` / `#121212`
  ([#365](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/365))

- **AG Grid did not use the theme's surface tokens.** The grid body kept the
  quartz palette's own surface while every other panel used `--admin-surface`,
  so in dark mode the grid floated as a lighter slab. Worse, pinning *only*
  `--ag-odd-row-background-color` to switch striping off made striping reappear
  **inverted** — odd rows darker than the quartz base. Grid background, header
  and border now come from the same tokens; a test asserts they are present
  together, because the half-configured state is the bug
  ([#365](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/365))

- **Muting inactive admin nav icons applied to nothing.** `.admin-drawer
  .q-icon` is a two-class selector and outranked the single-class
  `.admin-text-muted` helper. Restated at higher specificity, and dark
  `--admin-drawer-text` moved off `--admin-text-muted`'s value — equal values
  make the mute a silent no-op, now pinned by a test. The admin header also no
  longer renders the operator's own username in the accent colour (NiceGUI puts
  `text-primary` on the inner `.q-btn__content` span, which the `.q-btn` rule
  never reached) and drops its `elevated` shadow, which competed with the
  hairline border
  ([#365](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/365))

### Upgrading

- **`--admin-login-gradient` is renamed `--admin-login-bg`.** The value is a flat
  colour now, so the old name lied. No compatibility alias, following #235's
  removal of `ADMIN_THEME_PALETTE`. Update any fork CSS that referenced it.
- **Every `AdminColors` value changed** (`PRIMARY` `#3182f6` → `#2563eb`, and so
  on). If a fork hardcoded these, re-derive from the new ramp. Note that with the
  `--q-*` fix these values now actually reach Quasar-coloured controls, so a fork
  that tuned its look *around* NiceGUI's defaults will see buttons and badges
  change colour even where it did not edit tokens.
- **`AdminMetrics.GRID_ROW_HEIGHT` is `36`** (was `44`). Override in a fork if
  taller rows are wanted.
- **`src/_apps/admin/static/` and the `/admin-static` route are gone.** A fork
  serving its own admin assets from that prefix must restore
  `app.add_static_files("/admin-static", ...)` in `src/_apps/admin/bootstrap.py`.
- **`c.stat_card` now has a minimum width** (`--admin-stat-card-min-width`, 150px) and
  `.admin-status-dot` is a new class with two state hues. A fork that laid out its own
  tile rows may need to adjust.
- **The `mypy` pre-commit hook no longer exists.** Any fork workflow that ran
  `pre-commit run --hook-stage manual mypy` should call `uv run pyright` instead;
  local `# type: ignore` comments that only mypy needed will now be reported as
  unnecessary, because `reportUnnecessaryTypeIgnoreComment` is an error.
- **`make scheduler` starts working.** If a deployment concluded that the scheduler
  process was unnecessary because running it appeared to be a no-op, that conclusion
  was based on the bug — `audit_cleanup_task` will begin pruning at `0 3 * * *` once
  the process runs, bounded by `AUDIT_LOG_RETENTION_DAYS`. Check that value before
  starting it against a database whose audit history you want to keep.

```bash
# Nothing to run — no env vars, settings, or schema changed. Restart the server.
# To keep a custom webfont, restore the static mount and add the @font-face rule
# back to theme.py, then relax test_font_is_a_system_stack_with_no_webfont.

# Contributors: the type check is blocking and reproducible locally.
uv run pyright
```

## [0.10.1] - 2026-08-06

### Added

- **CI `demo-smoke` job** — boots `make quickstart` and runs `make demo` +
  `make demo-rag` against it on every PR, then re-runs both to cover the
  warm-database paths (login fallback, demo-admin reseed). v0.10.0 fixed both
  demo scripts but nothing in CI executed them, so the claim that they work was
  itself unverified.

- **`make demo-gif`** — regenerates `docs/assets/cast/demo.gif` from
  `demo.tape`. Re-recording was previously an undocumented two-tool ritual, so
  nobody repeated it and the GIF went stale for months. The target also enforces
  a size budget: a bare `vhs` run produces ~1.7MB, over the
  `check-added-large-files` ceiling, so it palette-re-encodes down to ~900KB and
  fails loudly rather than silently committing an oversized asset.

### Fixed

- **Demo scripts no longer report success against a broken API.** `make
  demo-rag` printed a `401` for every `/v1/docs/*` call and still exited `0`;
  `make demo` did the same from `GET /v1/users` onward. Printing a response was
  never the same as checking it, and that is why the auth breakage in both
  scripts stayed invisible for two months. Every call that expects a success
  envelope now goes through a `check` helper that aborts on the first response
  whose envelope is not `success: true`, naming the request that failed.
  `python3` is now declared as a hard dependency at the top of both scripts
  rather than failing later as "Could not obtain access token".

### Changed

- **`demo.gif` re-recorded** for the admin-realm flow (seed demo admin →
  `POST /v1/admin/login` → user CRUD). The previous recording showed a customer
  token creating a user via `POST /v1/user` — an outcome the API stopped
  producing when #199/#218 moved those routes to the admin realm, and one that
  contradicted `scripts/demo.sh` itself. Register output is now truncated to
  100 columns: two full JWTs told the reader nothing and roughly doubled the
  file.

## [0.10.0] - 2026-08-05

Error-notification webhooks land as the first post-v0.9.0 feature, and then a
project-wide audit ([#336](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/336))
found 39 defects across 14 clusters and closed all of them. Several were silent
failures that no test could see because CI only ran SQLite; that gap is closed
too. **Read `Upgrading` — two changes are API-visible and one removes public
symbols.**

### Added

- **Error-notification webhooks.** Optional Slack/Discord alerts fired from the
  global exception handlers, behind the ADR 042 Protocol + Selector pattern:
  `NOTIFICATION_PROVIDER` plus a matching webhook URL enables it, unset falls back
  to `NoopNotificationClient`. `ErrorNotifier` gates on
  `NOTIFICATION_SEVERITY_THRESHOLD` (default 500) and a per-process, per-`error_code`
  `NOTIFICATION_COOLDOWN_SECONDS` (default 60), and dispatches fire-and-forget so a
  slow webhook never enters the request path. Send failures are logged
  `exc_type`-only — a webhook URL is a bearer credential and must never reach the
  log stream. First external contribution to `src/` after v0.9.0
  ([#17](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/17)).
- **Worker task failures alert too.** `TaskFailureNotificationMiddleware` extends
  dispatch to Taskiq task failures. No new env vars. Severity is synthesised (a
  `BaseCustomException` keeps its `status_code`, anything else is 500) so the
  existing threshold still applies, and the cooldown key is scoped
  `{task_name}:{error_code}` so one noisy task cannot mute every other task.
  Alerts fire once per incident on the terminal failure — permanent errors
  immediately, retryable ones after the last attempt
  ([#310](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/310)).
- **Severity channel routing.** `NOTIFICATION_WARNING_THRESHOLD` is the sole
  switch: setting it lowers the alerting floor to `min(severity, warning)` and
  routes that band to a second webhook.
  `NOTIFICATION_CRITICAL_WEBHOOK_URL` / `NOTIFICATION_WARNING_WEBHOOK_URL` are
  per-tier overrides that each fall back to the single provider webhook
  ([#286](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/286)).
- **Request bodies are bounded before the app parses them.**
  `MAX_REQUEST_BODY_BYTES` (default 10 MiB, `0` disables) enforced by
  `BodySizeLimitMiddleware` on both the `Content-Length` path and the chunked path
  that carries none. Collection fields also gained explicit `max_length` bounds
  ([#322](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/322)).
- **`VECTOR_STORE_TYPE` is a real setting with boot validation.** `inmemory`
  (default) or `s3vectors`; an unknown value is rejected, and `s3vectors` without
  the complete `S3VECTORS_*` group is rejected rather than handing the docs domain
  a store with `s3vector_client=None`
  ([#328](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/328)).
- **CI runs PostgreSQL, and the type gate is real.** The test matrix gained a
  PostgreSQL leg — it previously claimed PostgreSQL while running SQLite — and the
  `architecture` job now actually type-checks instead of passing vacuously
  ([#333](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/333)).
- **The secret scan runs in CI, and covers Discord.** `.gitleaks.toml` adds a
  `discord-webhook-url` rule the shipped ruleset could not match, and the
  `architecture` job runs `gitleaks dir` over the whole working tree. The
  pre-commit hook only ever saw the staged diff, so a hook-skipping PR was
  unchecked ([#320](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/320)).
- **Tests can resolve the *enabled* half of an optional-infra Selector.** No test
  could before, so every "enabled" branch in `CoreContainer` was unverified. Adds
  `tests/support/container_env.py` plus a `block_import` fixture that simulates a
  missing optional extra
  ([#330](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/330),
  [#351](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/351)).
- New ADRs: [057](docs/history/057-audit-actor-correlation-only.md) (audit actor is
  correlation-only) and
  [058](docs/history/058-base-repository-engine-guarantees.md) (what
  `BaseRepository` guarantees regardless of `DATABASE_ENGINE`).

### Changed

- **API-visible: unsorted list endpoints now return newest-first.**
  `BaseRepository.select_datas` and the no-sort branch of
  `select_datas_with_count` append the primary key descending as a tiebreaker
  ([ADR 058](docs/history/058-base-repository-engine-guarantees.md) D2). Offset
  paging over an unordered result set could repeat or skip rows across pages, so
  the previous "order" was whatever the engine happened to return. An explicit
  `QueryFilter.sort_field` still wins — it becomes the primary key, not the only
  one. Clients that relied on the incidental order — including `GET /v1/users` —
  will see a different sequence
  ([#325](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/325)).
- **API-visible: search and sort now fail closed with a 400 instead of returning
  too much.** A search naming no usable text column previously added no WHERE
  clause and returned the whole table with `total_items` set to the full count; it
  is now `400 DB_SEARCH_FIELD_UNUSABLE`. An unknown `sort_field` was an opaque
  `500 DB_INTERNAL_ERROR`; it is now `400 DB_UNKNOWN_FIELD` (ADR 058 D3, D4).
- **The inline broker is no longer a different runtime.** Under
  `BROKER_TYPE=inmemory` — the shipped default — `.kiq()` runs the task inside the
  server process, and it did so with an empty middleware stack and unresolved
  `Provide[...]` markers: retries, error logging, structlog context and worker
  alerts were all inert, and docs ingestion silently no-opped. The server now
  installs the same middleware stack and domain DI wiring on the inline broker
  ([#324](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/324)).
- **Admin shares the server's `CoreContainer` instead of building a second tree.**
  Two async engines, two `QueuePool`s, two `HttpClient`s and two `ErrorNotifier`
  cooldown dicts per process — so an HTTP-path alert did not suppress its admin-path
  duplicate ([#326](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/326)).
- **bcrypt runs off the event loop.** Hashing and verification are ~100 ms of
  synchronous CPU that stalled every concurrent request; both now go through a
  thread. The login miss path was also equalised so a missing username and a wrong
  credential take the same time
  ([#322](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/322)).
- **The Docker image builds as shipped, and compose starts every process.** The
  image did not build; `migrations/` was never copied so a container could not run
  Alembic; the image ran as root; and `docker compose up` started one of four
  processes ([#332](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/332)).
- **Three Alembic revision ids shortened** past the hardcoded `String(32)` of
  `alembic_version.version_num`, which PostgreSQL and MySQL reject.
  `tools/migrate_legacy_revision_ids.py` rewrites a stored long id — needed on
  SQLite, which does not enforce VARCHAR length and so accepted them
  ([#332](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/332)).
- **Dependency floors raised past the runtime-critical advisories.** `pip-audit`
  went from 32 distinct advisories to 8: `aiohttp` 3.14.3, `pyjwt` 2.13.0 (5
  advisories, and it sits directly in the auth path), `pydantic-settings` 2.14.2,
  `python-dotenv` 1.2.2, `nicegui` 3.12.0, plus eleven transitive upgrades.
  `pydantic-ai-slim` is `>=1.99.0,<2` across all four extras — the advisory needs
  the floor, and the cap keeps an unvetted 2.x major out. The remaining 8 are not
  fixable here: `starlette` (5) is held by `fastapi 0.128.0`'s own
  `starlette<0.51.0` pin, and `pip` (3) is the ambient installer rather than a
  dependency of this project
  ([#349](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/349)).
- `_maybe_configure_otel` moved out of both bootstraps into one shared
  `maybe_configure_otel(settings, service_name)` at
  `src/_core/infrastructure/observability/otel_bootstrap.py`. The two copies were
  byte-identical apart from the word "server"/"worker" in a docstring. It
  deliberately does **not** live in `otel_setup.py`: that module imports
  `opentelemetry` at module top, so it is the thing being guarded
  ([#331](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/331)).

### Fixed

- **`BaseRepository.insert_datas` no longer 500s on backends without RETURNING.**
  The bulk path committed and then read server-side defaults that were never
  loaded, so `MissingGreenlet` surfaced as `500 DB_INTERNAL_ERROR` **for rows that
  were already written** — the client saw a failure for a successful write and
  retried into duplicate-key errors. Affects MySQL/MariaDB
  (`insert_returning=False`); PostgreSQL and SQLite were unaffected, which is why
  no test caught it. It now loads defaults with one `populate_existing` SELECT
  before commit (ADR 058 D1).
- **5xx exceptions are logged.** A 5xx `BaseCustomException` produced no
  exception-level record, so in stg/prod the wrapped driver or provider error
  existed in *none* of the response body, the logs, or the alert. The LLM error
  mapper is also gated instead of substring-matching any message containing
  "rate limit", and provider errors are curated rather than interpolated raw into
  a response body — a boto3 `AccessDenied` message names the calling IAM principal
  ARN, the account id, the bucket and the key
  ([#323](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/323)).
- **The notification provider graph collapsed from five Selectors to what is
  consumable**, and configuration nothing can act on is now rejected at boot
  ([#327](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/327)).
  Setting a per-tier webhook URL *without* `NOTIFICATION_WARNING_THRESHOLD`
  previously booted and silently sent every alert to the base webhook; it now
  fails at boot ([#315](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/315)).
- **The in-memory vector store no longer ignores filter operators it does not
  implement.** `$gte`, `$lt`, `$and` and friends were dropped silently, so the same
  query returned a filtered result on S3 Vectors and an unfiltered one on the
  default backend. They now raise `VectorFilterUnsupportedException`, a curated
  400 — the filter arrives from a public request body, so an untranslated
  exception would have been a 500
  ([#328](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/328)).
- **DynamoDB batch operations no longer report success for refused work.**
  Unprocessed items were dropped, so a partially-refused batch write returned 200.
  Retries now use backoff with jitter and a genuinely incomplete batch raises
  `DynamoDBBatchIncompleteException` (503). An invalid `limit` was a 500 and is now
  a 400, and `_decode_cursor` validates strictly instead of trusting client input
  ([#329](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/329)).
- **Admin audit writes no longer fail silently.** The actor foreign key pointed at
  the wrong realm's table — an id-space overlap that could attribute an action to
  the wrong account — and a failed audit insert was swallowed. The FK is dropped in
  favour of correlation-only ([ADR 057](docs/history/057-audit-actor-correlation-only.md),
  [#348](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/348)).
- **Both README demos work again**, and several reader-facing claims that were
  false were removed. `make demo-rag`'s Step 5 no longer credits a background
  dispatch that never happens: the demo payloads are 378–425 characters against a
  20,000-character inline threshold, so they take the sync path.
- **`.claude` has the hook functions its own state tooling assumed.**
  `append_verify_log` and `cleanup_stale_verify_logs` existed in `.codex` and
  `.antigravity` but not `.claude`, while `check_state_lifecycle.py` and
  `governor_state_doctor.py` reasoned about all three
  ([#334](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/334)).
- The Governor Footer checker accepts `n/a` as a `links` entry
  ([#314](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/314)).
- Removed the dead `related_entities` refresh branch, which passed a list to
  `AsyncSession.refresh` (it takes one instance) and would have raised the moment
  any model defined the attribute (ADR 058 D5).

### Removed

- **Eleven unreferenced symbols deleted.** None had a caller, and none was an
  advertised extension point — this repo deliberately ships base classes and stub
  fallbacks with zero implementers, so a reference count alone is never grounds for
  deletion here. Gone: `TaskiqManager` (and its `CoreContainer` provider — task
  code always used `.kiq()` directly), `BaseHttpGateway` + `ExampleApiGateway`, the
  `src/_core/infrastructure/llm/exceptions.py` re-export facade (the hierarchy
  stays at `src/_core/exceptions/llm_exceptions.py`),
  `ClassificationFailedException` (LLM failures are mapped centrally by
  `try_map_llm_error`), `BrokerType` (a dead duplicate of `KNOWN_BROKER_TYPES`),
  `ExistsData`, `InternalConfig` and its `INTERNAL_CONFIG`,
  `S3VectorNotFoundException`, `AdminPermissionDeniedException` (the admin page
  guard navigates rather than raising), and three uncalled `ensure_*` wrappers in
  `_core/domain/validation.py` — the `collect_*` functions they wrapped are alive
  and unchanged. The two candidates that looked dead but are not,
  `BUSINESS_CONFLICT` and `build_stub_llm_model`, were kept
  ([#331](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/331)).

### Docs

- **Operator runbook for error notifications** — setup, coverage limits,
  cooldown and payload caveats, local-sink verification
  ([`docs/operations/error-notifications.md`](docs/operations/error-notifications.md),
  [#307](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/307)).
- **Error Notification section in the security checklist**, covering webhook
  credential handling and committed artefacts
  ([#305](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/305)),
  plus a raw-provider-exception-in-a-response-body item
  ([#335](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/335)).
- **Shared-reference re-sync** after the channel-routing work and again after the
  audit ([#316](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/316),
  [#317](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/317),
  [#335](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/335)): the
  scheduler — a fourth runtime process running an unattended irreversible `DELETE`
  — appeared in no auto-loaded rule file; `AI_USAGE_PUBLIC_API_ENABLED` and
  `AUDIT_LOG_RETENTION_DAYS` were undocumented in `_env/*.example`; and
  `examples/README.md` now records that the copy flow has no schema step, because
  `create_all` runs only under `ENV=quickstart`.
- ADRs 037, 042 and 046 received **append-only errata** rather than in-place edits
  (ADR 047 D3/D6): ADR 042's `s3vector_client` rationale credited a domain selector
  that no longer holds the invariant — boot validation does, and the two selectors
  key off different fields.

### Upgrading

```bash
git pull
uv sync --group dev --extra admin --extra aws
alembic upgrade head   # revision 0010 drops the audit actor FK
```

Three changes need a look before you upgrade:

1. **Unsorted list endpoints changed order** (newest-first). If a client depended
   on the incidental order, pass an explicit `QueryFilter.sort_field`.
2. **Search and sort now return 400 where they used to return 200 or 500.** A
   search over a non-text field, or an unknown `sort_field`, is now rejected.
3. **Eleven symbols were removed.** If you imported any name in the *Removed*
   section, that import now fails. Nothing in `examples/` or the reference domains
   used them.

Migration `0010` drops the audit actor foreign key. It is reversible, and
`tools/check_migration_safety.py` reports it as safe for a zero-downtime rollout.
If you ran migrations on **SQLite** at v0.9.0 or earlier, run
`tools/migrate_legacy_revision_ids.py` first — SQLite accepted three revision ids
that are now shortened.

## [0.9.0] - 2026-07-21

The AI-collaboration harness grows from a two-tool model (Claude + Codex) to three:
this release adds a repo-local **Antigravity 2.0 / Gemini CLI harness**, wired to the
same shared governor policy as the others. Alongside it ship three new governance
frameworks — a plan→execute hard gate (ADR 054), a review Summary Finding Ledger
(ADR 055), and a zero-downtime migration safety checker (ADR 056) — plus a real
web-search chatbot example and a Locust performance-test harness. There is **no `src/`
runtime change**: this is a harness, examples, tooling, and docs release. The minor
bump reflects the net-new Antigravity harness surface (a large asset that did not exist
before), not a runtime API change.

### Added

- **Antigravity 2.0 / Gemini CLI harness** — a repo-local harness under `.gemini/` and `.antigravity/` wires Antigravity's hooks to the shared governor policy (prompt tokens, shell/code safety, verify logging, completion gate, sync + workflow advisories, stage gate), so the multi-tool harness model now spans Claude + Codex + Antigravity. Extends the language / state / hook-surface / governor-doctor / regression test suites and syncs the shared docs + harness-asset-matrix. Harness-only, no `src/` change. ([#285](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/285), closes [#65](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/65))
- **Plan→execute boundary hard gate (ADR 054)** — `/plan-feature` now ends at the approved Execution Packet, and an approved plan (`workflow.stage == "planned"`) can no longer slide into implementation without an explicit `/execute-plan`. On Claude it is a `PreToolUse` hard block on `.py` edits under `src/`/`examples/` (`pre_tool_stage_block.py`, exit 2); on Codex a Stop-time advisory. Released via `/execute-plan` or a `[trivial]`/`[hotfix]` token, and it ranks below the four precedence layers (sandbox / prefix rules / safety hooks / absolute prohibitions). ([#282](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/282), closes [#281](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/281))
- **Review Summary Finding Ledger (ADR 055)** — review-protocol §5 now posts summary-routed (out-of-diff) findings as a task-list ledger with `OPEN`/`FIXED`/`OBSOLETE` states, closing the merge-gate bypass where a finding routed to the review summary body — not a resolvable thread — escaped tracking. Any still-`OPEN` key blocks Approve and keeps the completion gate open; `review-pr` Phase 0 gains a mandatory prior-round ledger diff on re-reviews. ([#296](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/296), closes [#292](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/292))
- **Zero-downtime migration safety (ADR 056)** — adds a no-downtime migration playbook to `docs/operations/rdb-migrations.md` (expand-contract 3-stage + per-engine PostgreSQL/MySQL/SQLite safe/unsafe DDL table + backfill/rollback) and `tools/check_migration_safety.py`, an AST-based advisory checker that scans Alembic `upgrade()` bodies for lock-taking / compatibility-breaking DDL (add NOT NULL without a safe default, non-`CONCURRENTLY` index, drop/rename, type change, blocking constraint), skipping ops against tables created in the same revision. Wired as a `verbose` non-blocking `migration-safety` pre-commit hook and into the `migrate-domain` review step. Advisory-first (exit 0). ([#301](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/301))
- **`web_search_chatbot` example** (`examples/web_search_chatbot/`) — a PydanticAI agent using `duckduckgo_search_tool()` for real web search, with a keyless `StubChatbot` fallback. The DI selector keys off `settings.llm_model_name` alone (no new flag, matching the other chatbot examples), and a new `pydantic-ai-duckduckgo` extra is added. Unit tests cover the stub, offline `TestModel` structural, and offline `FunctionModel` tool-invocation flows, plus a copy-flow smoke case. Examples-only, no `src/` change. ([#287](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/287), closes [#259](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/259)) — thanks @Diyaaa-12
- **Locust performance-test harness** — `tests/perf/locustfile.py` + a `make perf-test` target, with an always-on customer auth flow, always-on concurrent `/health` + `/health/db` reads, and an env-gated (`LOCUST_ADMIN_*`) admin `/v1/user` CRUD flow. `docs/operations/performance-locust.md` documents running it, reading the output, and an illustrative local baseline. No new dependencies (locust already in the dev group); illustrative only, not wired into CI. ([#293](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/293), closes [#3](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/3)) — thanks @Ayushhh26

### Fixed

- **Secret-check test-file path-traversal bypass closed** — the hardcoded-secret guard in `.agents/shared/governor/code_safety.py` could be evaded through a test-file path traversal; the check now resists it. ([#289](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/289))
- **Governor fail-open shims are mypy-clean** — an annotation-only pass so `pre-commit run --hook-stage manual mypy` is clean on the governor fail-open shims, with zero runtime change. ([#290](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/290), closes [#283](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/283))
- **OpenAI embedding tests guarded in minimal installs** — the `skipif` guard on `TestOpenAIBatchSplitting` now requires both `pydantic_ai` and `openai`, and a monkeypatch on a read-only property in the classification stub fallback is removed, fixing latent test failures. ([#291](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/291), closes [#288](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/288)) — thanks @Diyaaa-12
- **`ChatReply.confidence` bounded to `[0, 1]` across chatbot examples** — the PydanticAI agent output schema had no numeric constraint while the API response schema enforced `ge=0.0, le=1.0`, so a model could emit an out-of-range confidence that failed response validation; the agent schema now matches. ([#295](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/295), closes [#294](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/294))

### Docs

- **`make perf-test` synced into `commands.md` and the project-status snapshot refreshed** — a follow-up to #293. ([#298](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/298))
- **Drift-checklist §1C reconciled with harness-asset-matrix practice** — the checklist required every `docs/history/0XX-*.md` ADR to have exactly one matrix row, but the matrix intentionally carries more rows than that; §1C now matches practice. ([#299](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/299), closes [#297](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/297))
- **Harness-asset-matrix bucket-distribution narrative reconciled with `Drop=1`** — surfaced by the #297 cross-review as a pre-existing, out-of-scope drift. ([#300](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/300))
- **`absolute-prohibitions` shared-rule-sources synced with `AGENTS.md`** — a drift that originated in the Antigravity 2.0 harness work (#65). ([#302](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/302))

## [0.8.4] - 2026-07-05

A patch on top of 0.8.3: the two-domain `blog` example now survives copy-into-`src/`,
a permanent CI guard locks the copy-flow contract shut, plus a batch of
AI-collaboration harness improvements (mid-task scope gate, Codex stage-gate parity,
a unified review protocol) and new HTTP middleware contract tests. No `src/` runtime
change.

### Added

- **Examples copy-flow CI guard** — `tools/check_examples_copyflow.py` (an AST static check that forbids absolute `examples.*` imports in git-tracked `examples/**/*.py`) is wired as the `examples-copyflow` pre-commit hook and enforced by the CI `architecture` job; per-example `cp`→`src/` boot smoke (`tests/integration/examples/`), a `make smoke-examples` target, and a new `architecture-review-checklist` §10 lock the copy-into-`src/` contract shut after the #262/#261 remediation ([#265](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/265), closes [#260](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/260))
- **HTTP middleware contract tests** — CORS / `X-Request-ID` / middleware-ordering contract coverage for the server stack, so the request-id and CORS wiring cannot silently regress ([#267](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/267))
- **Mid-task scope-expansion gate** — a harness gate that flags when in-flight work drifts beyond its stated scope, plus a "Direction & Non-goals" section in `project-dna.md` §0 (ADR 050) ([#270](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/270), closes [#268](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/268))
- **Codex Stop-time stage-gate adapter** — brings Codex to parity with Claude's mid-task stage gate as a non-blocking Stop-time advisory that reuses the shared `governor.stage_gate` policy unchanged (ADR 050) ([#278](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/278), closes [#269](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/269))

### Changed

- **Review-skill family unified under a shared Review Protocol** — `/review-pr`, `/review-architecture`, and `/security-review` now share one Review Protocol definition (correctness / regression / stability / contract / architecture / security dimensions) instead of each wrapper re-declaring its own ([#275](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/275), #274)

### Fixed

- **`blog` example now survives copy-into-`src/`** — the two-domain example crashed on the documented `cp -r examples/blog src/` activation with `Table 'author' is already defined`, because `post_container` pulled `examples.blog.author.AuthorModel` while auto-discovery had already registered `src.author.AuthorModel` for the same table. Intra-domain imports are now package-relative and the two cross-domain references resolve to runtime-absolute `src.author.*` — the same shape as the real `src/auth → src/user` dependency — so both domains copy in, the app boots, and `authorDisplayName` resolves end-to-end ([#263](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/263), closes [#261](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/261))
- **Verify-first harness reminder now reaches the model** — the reminder was emitted on a channel the model did not observe; it now emits on the model-visible `additionalContext` channel ([#273](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/273), fixes [#271](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/271))

### Docs

- **ADRs 051–053 backfilled and ADR index hygiene restored** ([#276](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/276))

## [0.8.3] - 2026-07-02

A small patch on top of 0.8.2: two new LLM-calling contributor examples, plus a
repo-wide fix so an example actually runs when copied into `src/`. No `src/`
runtime change.

### Added

- **`chatbot_with_memory` example** (`examples/chatbot_with_memory/`) — a multi-turn chatbot that persists each turn and replays prior turns from session history into a PydanticAI `Agent` via structured `message_history`, so the model sees the conversation so far. Mirrors the `src/classification` Protocol + Adapter + Selector + Stub wiring, degrading to a deterministic `StubChatbotMemory` when no LLM provider is configured ([#255](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/255), closes [#251](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/251))
- **`chatbot_with_guardrails` example** (`examples/chatbot_with_guardrails/`) — a chatbot that wires the shared runtime guardrails (`src/_core/infrastructure/llm/guardrails.py`) around a PydanticAI `Agent`: a prompt-injection input guard blocks with `400 PROMPT_INJECTION_DETECTED`, reusing the existing guardrail exceptions and telemetry with a `guardrails_enabled` kill-switch honored on both the real and stub paths ([#256](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/256), closes [#250](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/250))

### Fixed

- **Examples now run when copied into `src/`** — single-domain examples referenced their own containers via absolute `from examples.<name>...` imports and wired by string package path, so `cp -r examples/<name> src/<name>` left each router's `Provide[...]` markers pointing at the `examples.*` class objects while auto-discovery instantiated the `src.*` ones — every copied example returned `500` at request time. Intra-example imports are now package-relative and bootstraps `wire(modules=[...])` the imported module object, so `todo`, `url_shortener`, `webhook_receiver`, `simple_chatbot`, `chatbot_with_memory`, and `chatbot_with_guardrails` all boot and serve correctly after copy-in (verified end-to-end via `make quickstart`). The two-domain `blog` example is a separate cross-domain case, tracked as a follow-up ([#261](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/261)) ([#262](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/262))

### Docs

- **`examples/README.md` flags that `blog/` does not yet run via copy-into-`src/`** — the two-domain cross-domain example still uses absolute intra-example imports (fix tracked in [#261](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/261)), so its catalog row now carries a note instead of implying it copies in and runs like the single-domain examples

## [0.8.2] - 2026-06-27

A small patch on top of 0.8.1: the first real-LLM-calling contributor example,
plus a docs note distinguishing example production surfaces. No `src/` runtime
change.

### Added

- **`simple_chatbot` example** (`examples/simple_chatbot/`) — the first example that calls a real external LLM. A stateless PydanticAI `Agent` with an `output_type=ChatReply` structured output, prompt/reply records persisted via `ChatMessageDTO` (each retrievable by ID — the example itself is stateless, with no conversation memory fed back to the agent), and `tokens_used` surfaced for educational visibility. Mirrors the `src/classification` Protocol + Adapter + Selector + Stub wiring, so it degrades to a deterministic `StubChatbot` when no LLM provider is configured. Deliberately minimal — no endpoint auth and runtime guardrails deferred to [#250](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/250); production caveats (auth + rate limiting + cost/budget controls, and a pointer to `guardrails.py`) are documented in the example README ([#249](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/249), closes [#97](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/97))

### Docs

- **Examples index distinguishes DB-only from real-LLM-calling examples** — a "Production surface" callout plus a `Surface` column in `examples/README.md`, so a reader sees the cost/abuse surface (auth + per-user rate/budget caps + runtime guardrails) before copying an LLM-calling example ([#253](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/253), closes [#252](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/252))

## [0.8.1] - 2026-06-18

A small patch on top of 0.8.0: a core not-found correctness fix plus a new
contributor example.

### Added

- **`url_shortener` example** (`examples/url_shortener/`) — a CRUD `link` domain plus a Taskiq `cleanup_expired_links_task` that shares one `LinkService` with the HTTP router, mirroring the `examples/todo/` layout and the `src/user` worker pattern. The README documents the InMemory single-process enqueue recipe — bootstrap `UrlShortenerContainer` on the shared `CoreContainer` and `wire()` the task module before `.kiq()`, since the InMemory broker runs the task inline in the caller ([#239](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/239), closes [#94](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/94))

### Fixed

- **Not-found returned `500` instead of `404` on every RDB read** — `Database.session()` re-wrapped *every* in-block exception, including the domain `BaseCustomException` a repository raises on a missing row, as `DatabaseException(500, DB_INTERNAL_ERROR)` (and in dev leaked the internal message into `errorDetails.original_error`). `session()` now re-raises `BaseCustomException` untouched ahead of the catch-all, so a read on a missing row returns `404`; only genuine driver errors become a 500. Adds session-level regression tests and tightens the docs e2e assertion from `(404, 500)` to `404` ([#246](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/246), closes [#245](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/245))

### Upgrading

No database migration. One behavior change to act on when upgrading a derived codebase:

- **RDB reads on a missing row now return `404`, not `500`.** Any derived client or test relying on the previous (incorrect) `500 DB_INTERNAL_ERROR` for not-found should expect `404` with the domain `BaseCustomException` message instead.

## [0.8.0] - 2026-06-17

This release simplifies admin theming down to a single Toss-style theme — a
breaking change that removes the multi-preset machinery — lands two new
contributor examples, and clears a batch of trust-signal fixes around the
worker/broker docs and fork-PR CI.

> Spans every change merged since v0.7.2 (2026-06-04).

### Added

- **`blog` example** (`examples/blog/`) — two domains wired through Protocol-based cross-domain DIP, the canonical pattern for one domain depending on another ([#237](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/237))
- **`webhook_receiver` example** (`examples/webhook_receiver/`) — a fast HTTP accept that enqueues a background Taskiq task to process the payload asynchronously, then a status-polling read ([#240](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/240))

### Changed

- **BREAKING — single Toss-style admin theme.** The multi-preset theming system is removed: the `ADMIN_THEME_PALETTE` setting/env var, the `_PALETTES` registry, the `palette_primary` helper, and the `default`/`linear`/`shadcn`/`supabase` presets are gone. The admin look is now two token dicts (`_ROOT_TOKENS` / `_DARK_TOKENS`) in `src/_core/infrastructure/admin/theme.py` — rebrand by editing those dicts. Ships the Toss Design System grey palette + blue/green/red semantics, a light-mode chrome flip, 20px/pill rounding, a dark-mode elevation ladder, a per-mode login backdrop + dark-mode toggle, and global micro-interactions ([#235](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/235))
- `make worker` and `make dev` now pass `--env local` — both previously invoked their launchers without the required `--env` and exited immediately ([#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))
- `run_server_local.py` honors a `PORT` env override (default `8001`), so a second instance can run alongside the primary dev server ([#235](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/235))
- The `Governor Footer Lint` CI comment steps are now best-effort (`continue-on-error`), so a fork PR's read-only `GITHUB_TOKEN` can no longer turn an otherwise-passing check red ([#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))

### Fixed

- **AG Grid empty admin list rendered blank** — a stuck `ag-delay-render` on the grid root left rows permanently `visibility:hidden` in the NiceGUI embed (data present but invisible); `_HELPER_CSS` now forces `.admin-grid` cells visible ([#234](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/234))
- **InMemory broker documented as a standalone-worker default** — `commands.md` and `canonical-demo.md` told readers to run a standalone worker on `BROKER_TYPE=inmemory`, which crash-loops (`InMemoryBroker.listen()` raises). The docs now explain InMemory runs tasks inline in the producer and point to the RabbitMQ/SQS recipe, and a new fast-fail guard (`src/_apps/worker/guards.py`) exits `run_worker_local.py` with an actionable message instead of crash-looping ([#241](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/241), [#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))
- `TaskiqManager.send_task` now logs `SendTaskError` via structlog before re-raising ([#243](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/243))
- Examples catalog refreshed (`todo` / `blog` marked landed) and the now-vestigial `examples/**/tests/**` ruff ignore removed ([#242](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/242))

### Docs

- Worker-environment args and InMemory broker limits clarified across the example READMEs and the external-broker recipe ([#96](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/96))

### Upgrading

No database migration. One breaking change to act on when upgrading a derived codebase:

- **`ADMIN_THEME_PALETTE` is removed.** Drop the variable if you set it — the admin now ships a single Toss-style theme. To rebrand, edit the `_ROOT_TOKENS` / `_DARK_TOKENS` dicts in `src/_core/infrastructure/admin/theme.py`; `ADMIN_BRAND_NAME` and `ADMIN_DARK_MODE_DEFAULT` still apply.

## [0.7.2] - 2026-06-04

An admin code-cleanup patch on top of 0.7.1.

### Fixed

- **Admin authorization redirect** — an operator hitting a page they lack permission for was redirected to `/admin/dashboard`, a non-existent route (blank page); now redirects to the real `/admin/` dashboard landing ([#229](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/229))

### Changed

- Internal admin tidy-ups (no user-facing behavior change) — renamed the `theme.palette_accent` helper to `palette_primary` (matches its `--q-primary` return value), simplified the drawer mini-rail nav state, removed a dead `app_username` alias, and stripped dev-process comments from shipped source ([#229](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/229))

## [0.7.1] - 2026-06-04

A security-hardening patch on top of 0.7.0, closing findings from a security
review. Both fixes are behavior-affecting — see **Upgrading** in the release
notes before deploying a derived codebase.

### Security

- **Broken access control on document reads** — `GET /v1/docs/documents` and `/v1/docs/documents/{id}` were public while `DocumentResponse` returns the raw `content`, letting any unauthenticated caller enumerate and exfiltrate every stored document. Both reads now require `Depends(get_current_user)`, matching the existing write/query gates; the e2e 401 test is extended to cover them ([#227](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/227))
- **Credentialed CORS reflection in strict environments** — `ALLOW_ORIGINS` defaulted to `["*"]` while the CORS middleware uses `allow_credentials=True`, so a `stg`/`prod` deploy that forgot an explicit allowlist would reflect any `Origin` with `Access-Control-Allow-Credentials` (exploitable against the cookie-backed admin session). A strict-env validator now **rejects `*` in `allow_origins` for `stg`/`prod`** at boot; `dev`/`local`/`quickstart` keep the wildcard for convenience ([#227](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/227))

### Changed

- Security-reference sync — `project-dna.md` §8 and `security-checklist.md` §2 corrected to the `admin_identity` realm model (#218 / ADR 049), and a new admin session-cookie hardening item (`https_only` / `SameSite` in `stg`/`prod`) added to the checklist ([#227](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/227))

### Upgrading

No database migration. Two behavior changes to act on when upgrading a derived codebase:

- **`stg`/`prod` must set an explicit `ALLOW_ORIGINS` allowlist** — the `*` dev default is now rejected at boot in strict environments.
- **`GET /v1/docs/documents` and `/v1/docs/documents/{id}` now require a Bearer token** — unauthenticated callers receive `401`; update derived clients that read documents without auth.

## [0.7.0] - 2026-06-02

This release hardens the admin and AI-agent surfaces and reworks the admin UI.
Four threads: **(1) Admin security** — a separate admin-identity bounded context
with its own JWT realm, server-route RBAC, a setup wizard with page-level
permissions, and an audit log with a retention pipeline; **(2) AI guardrails** —
OWASP LLM01 / LLM07 prompt-injection defenses across the PydanticAI call sites
(structural → runtime → observability); **(3) Admin UX** — a token-driven design
system, a data-dashboard landing, centralized error handling, and loading
states; **(4) Release hygiene** — version, CHANGELOG, and project-status sync.

> Spans every change merged since v0.6.0 (2026-05-07); no interim release was tagged.

### Added

- **Admin identity bounded context** (`src/admin_identity/`, ADR 049) — admin/operator identity separated from customer identity, with its own credential store (`admin_identity` + `admin_refresh_token` tables) **and** its own JWT realm (distinct `ADMIN_JWT_SECRET_KEY` / issuer / audience; a config validator rejects realm collapse). Adds `/v1/admin/login|refresh|logout`; the shared `JwtTokenCodec` is extracted to `src/_core/common/` ([#218](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/218))
- **Server-route RBAC for `/v1/user`** — a `require_admin` interface dependency (admin-realm token required; a customer token resolves to `401 INVALID_TOKEN`, the trust boundary) gates all `/v1/user` reads + writes at the router level (default-deny); non-admin self-service stays on `/v1/auth/me` ([#199](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/199))
- **Admin setup wizard + page-level permissions** — a one-time `/admin/setup` creates the first real admin (the bootstrap credential is permanently disabled afterward), backed by `AdminAccountUseCase` + `AdminPermissionRegistry`; `/admin/accounts` UI for account create/delete/permission-edit with a last-admin guard, a forced password-change flow, and a mandatory `require_auth(page_key=...)` per-route gate (AST-enforced) ([#194](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/194))
- **Admin audit log** — `src/_core/infrastructure/admin/audit/` (model + `AdminAuditLogRepository` + `AuditLogger` facade + `@audit_action` decorator) records login/logout, account/permission/password, and first-admin events as `SUCCESS`/`FAILURE` with an `error_code` (never raw `str(exc)`, no password hashes). Adds the `/admin/audit-log` operator UI, a per-domain read-event opt-in (`BaseAdminPage.log_reads`), and a `TaskiqScheduler` retention-cleanup job (`make scheduler`, `audit_log_retention_days`) ([#196](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/196), [#206](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/206))
- **Prompt-injection guardrails (OWASP LLM01 / LLM07)** across the PydanticAI RAG + classifier call sites:
  - *Structural* — `instructions=` slot migration + `Final[LiteralString]` persona; retrieved documents and user input wrapped in boundary XML and escaped via `escape_for_prompt_xml` ([#197](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/197))
  - *Runtime* — `src/_core/infrastructure/llm/guardrails.py`: input injection detection (block), output PII-fabrication diff (block), prompt-leak (log-only); a `GUARDRAILS_ENABLED` DI kill-switch ([#209](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/209))
  - *Observability* — an `ai_usage.guardrail_triggered` flag through the usage ledger, a `/v1/usage?guardrailTriggered=` filter, standardized telemetry, and a red-team regression corpus ([#211](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/211))
- **Admin design system** — a token-driven theme (`theme.py`: 4 style presets via `ADMIN_THEME_PALETTE`, dark mode, self-hosted Wanted Sans) and a `components/` builder library, with the `docs/ai/shared/admin-design-system.md` catalog ([#193](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/193))
- **Admin data dashboard** — the `/admin/` landing rebuilt around a `dashboard_metrics` read facade (per-source isolation; audit read gated on the `audit_log` permission): domain record-count stat cards, the first ECharts builder `c.bar_chart()`, a recent-activity table, and quick-action nav ([#223](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/223))

### Changed

- **Admin authentication re-homed to `admin_identity`** — the interim single-table admin model (`User.role` / `permissions` / `password_temporary` / `is_bootstrap_admin`, introduced by #154/#194) is removed; the `user` table is now pure customer identity and existing admins are migrated into `admin_identity`. NiceGUI admin login + bootstrap seed are re-pointed accordingly (token-less session shape preserved) ([#218](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/218), supersedes [#154](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/154) / [#194](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/194))
- **Centralized admin error handling** — `AdminErrorHandler` + `@admin_error_boundary` + a global `app.on_exception` net + an unauthenticated `/admin/error` page; only 4xx `BaseCustomException.message` surfaces (warning), `>=500`/generic show a generic message, and raw `str(exc)` never reaches the UI (full detail goes to the structured log) ([#195](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/195))
- **Admin loading states** — a `button_loading` context manager on every admin write button + structure-mirroring skeletons on list/detail loads ([#198](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/198))
- **Admin shell look & feel** — the dark content palette retuned from blue-navy to a neutral charcoal/zinc cohesive with the shadcn/supabase/linear chrome (lifted off near-OLED black; page < chrome < card elevation; `.q-card` bound to `--admin-surface`), and the sidebar now collapses to an icon-only **mini rail** with a top-of-drawer collapse control (nav tooltips + `aria-label`; header hamburger mobile-only) ([#223](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/223))

### Fixed

- Guardrail PII scan no longer false-positives on reformatted phone numbers (regex normalization) ([#214](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/214))

## [0.6.0] - 2026-05-07

This release completes the production feature surface and prepares the project
for OSS launch. Three themes: **(1) Production feature completion** — JWT
authentication domain with refresh-token rotation, NiceGUI admin JWT + minimal
RBAC, and `/docs` selector revamp with `frontend-handoff.md`; **(2) Governance
maturity** — ADR 047 full rollout (governor-review-log folded into PR Footer
blocks), harness sync advisory SOT migration across both tools; **(3) OSS
launch readiness** — `docs/adoption.md`, `docs/comparison.md`,
`docs/compatibility.md`, `SUPPORT.md`, expanded `CONTRIBUTING.md`,
`docs/README.md` index, terminal demo GIFs, and truthfulness fixes across
README / SECURITY.md / examples / tutorial.

### Added

- JWT authentication domain (`src/auth/`) — HS256 access/refresh tokens, DB-backed rotation/revocation, `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/auth/me`, Bearer protection for user API routes ([#4](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/4))
- NiceGUI admin JWT login + minimal RBAC — credential check via auth-domain, `User.role` DB field (`UserRole` enum), `ADMIN_BOOTSTRAP_*` idempotent seeding; legacy env-var auth provider removed ([#154](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/154), [PR #155](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/155))
- `/docs` selector revamp — GitHub-flavoured layout, built-in light/dark toggle with `localStorage` persistence, `GET /openapi-download.json` (Content-Disposition: attachment); `docs/frontend-handoff.md` covering OpenAPI contract, camelCase serialisation, JWT flow, CORS, and Bruno/Postman/Hey API/Orval recipes ([#156](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/156))
- `docs/adoption.md` — greenfield and partial-import adoption paths for teams onboarding from an existing FastAPI project
- `docs/comparison.md` — standalone deep-dive comparison including Litestar, Robyn, cookiecutter, and full-stack-fastapi-template with per-claim evidence links
- `docs/compatibility.md` — Python / FastAPI / Pydantic / SQLAlchemy / Claude Code / Codex CLI / OS compatibility matrix
- `SUPPORT.md` — in-scope / out-of-scope / breaking-change policy / response SLA / single-maintainer statement
- `CONTRIBUTING.md` expanded — first-PR-friendly areas, test execution guide, architecture guardrails, review expectations, skill harness change policy
- `docs/README.md` — docs folder index providing entry points for all reference documents
- Terminal demo GIFs (`docs/assets/cast/demo.gif`, `docs/assets/cast/new-domain.gif`) demonstrating end-to-end API flow and `/new-domain` domain scaffolding
- `docs/canonical-demo.md` — full integration walkthrough (auth · RBAC · worker · admin · RAG · OTEL · tests)
- `/sync-guidelines` project-status.md table hygiene check — step 3 extended to verify row-count consistency between the status table and archived rows ([#176](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/176))

### Changed

- README restructured — hero tagline `Production FastAPI architecture, with AI-assisted domain scaffolding built in.`, 60/40 two-column Why section (Production rigor primary / AI-assisted acceleration first-class amplifier), Quickstart → Canonical demo → Why → Compare section order; ADR/governance mentions moved to deeper sections
- Governor-Review Provenance Consolidation full rollout (ADR 047) — per-PR `governor-review-log/` archive folded into PR-description `## Governor Footer` block; durable ICs promoted into ADR 047 Consequences (`ADR047-G1 ~ ADR047-G27`) or `project-dna.md`; historical archive at `docs/history/archive/governor-review-log/` ([#157](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/157))
- Harness governance improvements — sync advisory SOT migrated to `governor.sync_advisory` module for both Claude bash hook and Codex stop hook; completion-gate fossil sweep; lifecycle invariant tests; shared changed-files delegation; override de-recommendation in `/plan-feature` ([#162](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/162)–[#182](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/182))
- pyproject.toml `keywords` and `classifiers` moved to correct `[project]` table; 12 discovery keywords added (`fastapi`, `ddd`, `agent`, `llm`, `rag`, `template`, `boilerplate`, `claude-code`, `codex-cli`, `taskiq`, `nicegui`, `pydantic-ai`)

### Fixed

- Stale claims corrected: ADR count `40` → `18 active · 30 archived`; CRUD method count `7` → `8`; `examples/todo/` port `8000` → `8001`; `docs/tutorial/first-domain.md` Step 4 self-contradiction resolved to single-restart flow; `SECURITY.md` supported versions updated to `0.4.x` / `0.5.x`
- Demo script (`scripts/demo.sh`) JWT token fallback field corrected

### Removed

- `governor-review-log/` working directory — migrated to `docs/history/archive/governor-review-log/` as closed historical archive ([#157](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/157))

## [0.5.0] - 2026-04-29

This release hardens the AI agent workflow governance and delivers production
infrastructure across three themes: **(1) AI workflow governance** — Hybrid
Harness v1 (7-step Default Coding Flow, shared governor module, localized
reminders), Tier 1 Language Policy, Reasoning-Level Consistency Guards,
Governor Footer CI; **(2) Production infrastructure** — AI Usage Ledger
(`ai_usage` domain), Taskiq smart retry with task-scoped structured logging,
optional OpenTelemetry tracing; **(3) Contributor experience** — unified
Quality Gate review contract, `/plan-feature` Approach Options stage,
`examples/todo/` reference domain.

### Added

- Hybrid Harness v1 — 7-step Default Coding Flow (`framing → approach options → plan → implement → verify → self-review → completion gate`), exception-token parser ([PR #126](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/126)), verify-first adapters ([PR #127](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/127)), completion-gate Stop adapter with governor sync advisory ([PR #128](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/128)), shared governor module eliminating four hook duplicates ([PR #130](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/130)); ADR 045 ([#117](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/117))
- AGENT_LOCALE localized hook reminders — `governor/locale.py` canonical locale module (18 keys, ko/en), `python -m governor.locale` CLI, IC-19 always-fallback enforcement at every emit callsite ([#133](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/133), [PR #134](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/134))
- Tier 1 Language Policy — `AGENTS.md § Language Policy` enforcing English-only prose on governance/harness/contributor-facing paths; `tools/check_language_policy.py`, pre-commit hook, CI enforcement, bilingual escape-token vocabulary + `LOCALE_DATA_FILES` as two narrowly-scoped exceptions ([#131](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/131), [PR #132](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/132))
- Reasoning-Level Consistency Guards (Layer 2 Governor) — four guards: F (volatile workspace facts re-verification), G (R-point closure completeness), H (effect vs. process question discrimination), I (self-licensing detection); IC-RG-1 through IC-RG-5; canonical in `AGENTS.md` ([PR #143](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/143))
- Cross-tool prompt template standardisation — canonical cross-review prompt templates for `/review-pr`, `/review-architecture`, `/security-review`, `/sync-guidelines` with R-point closure categories and `Sync Required` field ([#144](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/144), [PR #147](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/147))
- Governor Footer CI — `tools/check_governor_footer.py` + `Governor Footer Lint` GitHub Actions workflow; PR-description `## Governor Footer` block as canonical G-closure record; ADR 047 ([#145](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/145), [PR #148](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/148))
- AI Usage Ledger — `ai_usage` domain with `AgentUsageRecord` / `PromptSnapshot` value objects, RDB migrations, admin and API surfaces for per-call usage accounting ([#75](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/75), [PR #149](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/149))
- Taskiq smart retry middleware — task-scoped structlog context binding, structured task failure logging, permanent-aware retry strategy wired through worker bootstrap ([#120](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/120), [PR #150](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/150))
- Optional OpenTelemetry tracing — `[otel]` extra (`opentelemetry-api/sdk/exporter-otlp-proto-grpc`), `OTEL_ENABLED` + `OTEL_EXPORTER_OTLP_ENDPOINT` settings, `_maybe_configure_otel` at server/worker bootstrap, Jaeger/Tempo/Phoenix recipe at `docs/operations/observability-otel.md`; ADR 046 Pillar 1 ([#136](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/136))
- `/plan-feature` Approach Options stage — Phase 1 now presents 2–3 candidate approaches with trade-offs and a recommendation before architecture analysis ([#116](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/116))
- Quality Gate Skill unified review contract — `/review-pr`, `/review-architecture`, `/security-review` emit a consistent `Scope / Sources Loaded / Findings / Drift Candidates / Next Actions / Completion State / Sync Required` output shape; `/sync-guidelines` documented as the closure step ([#113](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/113))
- `examples/todo/` contributor reference — minimal CRUD example mirroring `src/user/` layout, not subject to auto-discovery (copy to `src/todo/` to run); `/review-architecture` recognises the `examples` profile and relaxes §5 Test Coverage and §2 Auth requirements ([#112](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/112), [#119](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/119))

### Changed

- Responsibility-Driven Refactor (ADR 043) — `error_mapper.py` promoted to the infra ACL (domain services raise domain exceptions only); `ClassifierProtocol` / `PydanticAIClassifier` / `StubClassifier` align with the ADR 040 consumer pattern; `_core/infrastructure/ai/providers.py` unifies `parse_model_name` and provider builder; `AdminCrudServiceProtocol` + `extra_services_config` give admin layer type stability; bootstrap conductor decomposed into private functions; `BaseEmbeddingProtocol` / `BaseVectorStoreProtocol` switch to `typing.Protocol`
- **BREAKING** — `boto3` and `aioboto3` moved from core `[project.dependencies]` to `[project.optional-dependencies].aws` extra; four AWS-backed clients now lazy-import `aioboto3`/`boto3`/`botocore`; non-AWS deployments no longer pay the boto3 install cost. Migration: add `--extra aws` to your `uv sync` command if you use S3/MinIO, DynamoDB, or S3 Vectors ([#104](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/104))

### Removed

- `tools/check_g_closure.py` + legacy `check-g-closure` pre-commit hook — superseded by `tools/check_governor_footer.py` + `Governor Footer Lint` CI ([#145](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/145), ADR 047)

## [0.4.0] - 2026-04-21

### Added

- Zero-config quickstart (`make quickstart` / `make demo` / `ENV=quickstart` with SQLite + InMemory broker + auto create_all) so the blueprint can boot in under 60 seconds with no external infra ([#78](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/78))
- End-to-end RAG example as a reusable `_core` pattern (`RagPipeline`, `BaseChunkDTO` / `CitationDTO` / `QueryAnswerDTO`, `AnswerAgentProtocol`, `StubEmbedder` / `StubAnswerAgent` / `PydanticAIAnswerAgent`, `BaseInMemoryVectorStore`) with `src/docs/` consumer domain, `make demo-rag`, and `VECTOR_STORE_TYPE` env var ([#80](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/80))
- Optional Infrastructure pattern in CoreContainer — `providers.Selector` + lazy factories for all 5 non-broker optional infras (storage, DynamoDB, S3 Vectors, embedding, LLM); disabled branches return `providers.Object(None)` for data stores or `StubEmbedder` / PydanticAI `TestModel` for AI infras so apps boot with only `DATABASE_ENGINE=sqlite` set and optional extras uninstalled ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- `build_stub_llm_model()` factory — returns PydanticAI `TestModel` when `pydantic-ai` is installed, `None` otherwise, so `ClassificationService` and future LLM-consuming domains degrade gracefully when `LLM_*` env vars are unset ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- Structured logging via `structlog` + `asgi-correlation-id` — one `ProcessorFormatter` pipeline bridges structlog-native records and every existing `logging.getLogger(__name__)` call site. Dual renderer (JSON in stg/prod, coloured console in dev), `LOG_LEVEL` / `LOG_JSON_FORMAT` env vars with independent override, per-request `X-Request-ID` correlation bound into `contextvars` and surfaced on every record, `http_request` access-log middleware (method / path / status / duration_ms), Taskiq `StructlogContextMiddleware` binding task IDs + lifting `correlation_id` labels from the dispatcher side, and a `sqlalchemy.engine` double-emit fix that translates `DATABASE_ECHO` into a logger level ([#9](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/9))
- AGENTS.md "Optional Infrastructure Toggles" reference section (formerly "Optional Infrastructure" — renamed in PR-B.4a) and `docs/ai/shared/scaffolding-layers.md` "Optional AI Infra Variant" section for `/new-domain` scaffolding ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- README restructure (633 → 260 lines), `docs/reference.md`, and `docs/README.ko.md` Korean mirror ([#79](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/79))
- Visual architecture diagrams (Mermaid + SVG exports) with canonical `docs/ai/shared/architecture-diagrams.md` and `make diagrams` target ([#81](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/81), [#89](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/89))
- "Your first domain in 10 minutes" tutorial ([#84](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/84))
- Contributor funnel — good-first-issues audit, `examples/` seed, five seed issues for contributors ([#85](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/85))
- Secret hygiene — gitleaks pre-commit hook, history scan, `SECURITY.md` expansion ([#87](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/87))
- CI `minimal-install` job — runs `uv sync --group dev` alone (no extras) and asserts the app boots, `/api/health` serves, no `/admin` routes are mounted. This is the regression guard for the "extras-uninstall → still boots" promise ([#104](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/104))
- ADR 040 (RAG as reusable `_core` pattern), ADR 041 (Multi-backend infrastructure layout — persistence umbrella + vector backend subfolders), ADR 042 (Optional Infrastructure — Selector + lazy factory)

### Changed

- ADR curation — 40 ADRs consolidated down to 14 core + 29 archived under `docs/history/archive/`, with `docs/history/README.md` providing a core-reading-order guide for onboarding ([#83](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/83))
- `CoreContainer.llm_config` and `CoreContainer.embedding_config` are no longer public providers — both VOs are now constructed inside the lazy factory functions, reducing the container's surface area without changing the VO classes themselves ([#101](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/101))
- `src/_core/infrastructure/` reorganised under the `persistence/` umbrella (RDB at `persistence/rdb/`, DynamoDB at `persistence/nosql/dynamodb/`) with vector backends split into `vectors/s3/` and `vectors/in_memory/` sharing a root `vector_model.py` ([#80](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/80), ADR 041)
- RAG DTOs relocated from `_core/domain/value_objects/rag/` to `_core/domain/dtos/rag.py` and renamed `QueryAnswer` → `QueryAnswerDTO` for consistency with the ADR 004 DTO suffix convention ([#80](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/80))
- **BREAKING** — `nicegui` moved from core `[project.dependencies]` to a new `[project.optional-dependencies].admin` extra. API-only deployments no longer pay the nicegui install cost; the NiceGUI admin dashboard now requires `uv sync --extra admin`. Contributors running `make setup` / `make quickstart` get the extra automatically. The server bootstrap emits a structured `admin_mount_skipped` record (via the #9 logging pipeline) when nicegui is not installed. This is a SemVer-minor breaking change permitted under the project's `0.x` contract; a deprecation-warning phase was considered but rejected given the small current user base and the cleaner migration story ([#104](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/104))
- `Database.__init__` no longer passes `echo=True` to SQLAlchemy's `create_engine` (which would install a parallel `StreamHandler` on `sqlalchemy.engine` and double-emit every query alongside the structlog root handler). `DATABASE_ECHO=true` now translates to `logging.getLogger("sqlalchemy.engine").setLevel(INFO)` — same user-visible semantics, records flow through the structlog pipeline exactly once ([#9](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/9))

### Fixed

- `generic_exception_handler` replaced the stray `print(error_trace)` with a structured `logger.exception("unhandled_exception", exc_info=exc, exception_type=...)` — traceback renders inline in both console and JSON modes ([#9](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/9))

## [0.3.0] - 2026-04-09

### Added

- NiceGUI admin dashboard with auto-discovery, env-var auth, AG Grid CRUD, and field masking ([#14](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/14))
- DynamoDB support with `BaseDynamoRepository`, `DynamoModel`, and `DynamoDBClient` ([#13](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/13))
- Broker abstraction with `providers.Selector` for SQS/RabbitMQ/InMemory multi-backend ([#8](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/8))
- Flexible RDB configuration with multi-engine and per-environment support ([#7](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/7))
- Environment-aware config validation in Settings — strict mode for stg/prod ([#53](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/53))
- Password hashing (`hash_password`, `verify_password`) and input validation in `_core.common.security`
- `QueryFilter` value object for paginated query params with sort/search
- DynamoDB Local service in CI for integration tests ([#13](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/13))
- Branch name validation in CI for pull requests (`{type}/{description}` format enforcement)
- `/add-admin-page` skill for NiceGUI admin page scaffolding
- ADR 026 (NiceGUI Admin), ADR 027 (Flexible RDB), ADR 028 (Config Validation), ADR 029 (Broker Abstraction)

### Changed

- Replace SQLAdmin with NiceGUI for admin interface ([#14](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/14))
- Restore `CreateDTO`/`UpdateDTO` generics to `BaseService` (3 TypeVars) — reverts prior simplification (ADR 011 post-decision update)
- Rename Serena memory `refactoring_status` → `project_status` for clarity ([#60](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/60))
- Expand `sync-guidelines` to update all 4 Serena memories (was only 1) ([#60](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/60))
- Make `taskiq-aws` an optional dependency with lazy import ([#8](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/8))
- Admin views moved from `interface/admin/views/` to `interface/admin/pages/`

### Removed

- `/create-pr` skill — branch name validation moved to CI; PR creation handled by Claude Code built-in capability

### Fixed

- Add missing `__init__.py` in `_core/domain/protocols/` and `_core/domain/value_objects/` ([#60](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/60))
- Mount NiceGUI directly on main app instead of sub-app
- Harden admin security with server-side masking and timing-safe auth
- Skip SQS broker test when `taskiq-aws` not installed ([#8](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/8))

## [0.2.0] - 2026-04-07

### Added

- Worker Payload Schema: `BasePayload` and `PayloadConfig` for worker message contract validation ([#45](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/45))
- Database health check endpoint with `HealthService` ([#19](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/19))
- `/create-pr` and `/review-pr` GitHub collaboration skills ([#31](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/31))
- Conventional commit message validation hook ([#31](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/31))
- `make help` as default Makefile target ([#31](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/31))
- 9 missing ADRs (017-025) from full commit history analysis
- ADR 014 (OMC vs Native decision) and ADR 015 (rebranding) and ADR 016 (Worker Payload Schema)

### Changed

- Rebrand project to **AI Agent Backend Platform** (`fastapi-agent-blueprint`) ([#43](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/43))
- Rename `interface/dtos/` to `interface/schemas/` for terminology consistency ([#38](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/38))
- Unify exception handling with `app.add_exception_handler` ([#35](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/35))
- Consolidate sync hook to single git-diff-based Stop hook ([#40](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/40))
- Strengthen harness hook security checks and expand detection scope ([#47](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/47))
- Extract `HealthService` to follow Router -> Service pattern ([#19](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/19))
- Move health check logic into `Database.check_connection()` ([#29](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/29))
- Translate all documentation to English (ADRs, skills, references, config, code comments) ([#25](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/25))
- Improve ADR template with anti-rationalization principles ([#48](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/48))
- Align all 17 existing ADRs with improved template structure ([#48](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/48))

### Removed

- Domain Event infrastructure (unused) ([#38](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/38))

### Fixed

- Correct `error_code` attribute in `ExceptionMiddleware` ([#26](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/26))
- Sync flag file path for sandbox compatibility ([#38](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/38))

## [0.1.0] - 2026-03-26

### Added

- Initial project structure with 3-tier hybrid layer architecture
- Domain auto-discovery system (`DynamicContainer` + factory function)
- `BaseService` and `BaseRepository` with generic CRUD operations
- User domain as reference implementation
- Alembic migration support
- Taskiq worker integration with RabbitMQ broker
- SQLAdmin dashboard
- Docker Compose for local development
- GitHub Actions CI workflow
- Ruff for unified linting and formatting
- Claude Code skills: `/new-domain`, `/add-api`, `/add-worker-task`, `/add-cross-domain`, `/review-architecture`, `/security-review`, `/test-domain`, `/fix-bug`, `/onboard`
- ADR documentation (001-013)
- CONTRIBUTING guide and issue templates

[Unreleased]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.10.1...v0.11.0
[0.10.1]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.8.4...v0.9.0
[0.8.4]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.8.3...v0.8.4
[0.8.3]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.7.2...v0.8.0
[0.7.2]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Mr-DooSun/fastapi-agent-blueprint/releases/tag/v0.1.0
