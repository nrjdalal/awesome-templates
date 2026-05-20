# Frontend Handoff Guide

This guide is for frontend engineers consuming the FastAPI backend exposed by
this blueprint. It is intentionally **scope first, tools second** — the docs UI
in your browser is a viewer, not a workspace. For anything that needs persisted
inputs, tokens, or environments, import the OpenAPI spec into a real client.

---

## 1. TL;DR

1. **Get the spec**: open `/docs` and click `Download OpenAPI (JSON)` — or fetch
   `/api/openapi.json` directly. Save it as `openapi.json`.
2. **Pick a client**: Postman / Bruno / Insomnia / Hoppscotch / Scalar Client.
   Bruno is recommended when you want to commit collections to git.
3. **Import the spec**: most clients accept the JSON file directly and produce
   a folder of requests, including auth headers and example bodies.
4. **(Optional) Generate a typed SDK**: run `npx @hey-api/openapi-ts` once and
   re-run on every spec diff to keep your TypeScript client in sync.

If something below disagrees with what the spec actually returns, **trust the
spec**. This document describes the operating contract; the spec is the source
of truth for shape.

---

## 2. API Contract Scope

These are the operating rules that the spec alone does not communicate.

### 2.1 Base URL and path prefixes

| Environment | Base URL |
|-------------|----------|
| Quickstart / dev | `http://127.0.0.1:8001` |
| Staging / prod   | Not defined by the blueprint — set per deployment |

The FastAPI app is mounted with `root_path="/api"` and each domain router adds
a `/v1` prefix. Two consequences:

- The OpenAPI spec exposes paths as `/v1/...` with `servers: [{url: "/api"}]`.
  Client tools that import the spec join the two and call `/api/v1/...`.
- The dev server also accepts the un-prefixed path (`/v1/...` directly), which
  is what the bundled `make demo` / `make demo-rag` curl scripts use.

When in doubt, **use `/api/v1/...`** — that matches the spec exactly and works
in both dev and behind a proxy.

### 2.2 Wire format conventions

All Request / Response models inherit a Pydantic config that:

- Serializes field names as **camelCase** via `alias_generator=to_camel`
  (`accessToken`, `refreshToken`, `errorCode`, `currentPage`, `nextCursor`, …).
- Accepts both camelCase **and** snake_case on input
  (`populate_by_name=True`).

When you read a response, expect camelCase. When you build a request body,
prefer camelCase to stay consistent with the spec.

### 2.3 Success envelope

Every successful response wraps the payload in a `SuccessResponse`:

```json
{
  "success": true,
  "message": "Request processed successfully",
  "data": { "...": "..." },
  "pagination": null
}
```

For collection endpoints, `data` is an array and `pagination` is populated
(see §2.6). For single-item endpoints, `data` is the object itself and
`pagination` is `null`.

### 2.4 Authentication

The blueprint ships JWT auth (HS256) on the `auth` domain.

| Method | Path (spec) | External call | Purpose |
|--------|-------------|--------------|---------|
| POST | `/v1/auth/register` | `POST /api/v1/auth/register` | Create a user account, return tokens |
| POST | `/v1/auth/login`    | `POST /api/v1/auth/login`    | Exchange username + password for tokens |
| POST | `/v1/auth/refresh`  | `POST /api/v1/auth/refresh`  | Rotate refresh token, issue a new access token |
| POST | `/v1/auth/logout`   | `POST /api/v1/auth/logout`   | Revoke a refresh token |
| GET  | `/v1/auth/me`       | `GET /api/v1/auth/me`        | Return the current user (requires `Authorization`) |

**Register / Login response shape** (camelCase, wrapped):

```json
{
  "success": true,
  "message": "Request processed successfully",
  "data": {
    "accessToken": "eyJhbGciOi...",
    "refreshToken": "eyJhbGciOi...",
    "tokenType": "bearer",
    "expiresIn": 900,
    "user": { "id": 1, "username": "alice", "fullName": "Alice", "email": "alice@example.com" }
  },
  "pagination": null
}
```

**Calling protected endpoints**: include the access token as a Bearer header.

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

The access token expires (see `expiresIn`, in seconds). Use
`/api/v1/auth/refresh` with `{ "refreshToken": "..." }` to obtain a new pair
without re-entering credentials. Refresh tokens are stored server-side and
can be revoked individually via `logout`.

### 2.5 Error envelope

Every error response — whether validation, business rule, or unhandled
exception — follows the same shape:

```json
{
  "success": false,
  "message": "Internal server error",
  "errorCode": "INTERNAL_SERVER_ERROR",
  "errorDetails": null
}
```

For 422 validation errors, `errorDetails.errors` is an array of field-level
problems pulled from FastAPI / pydantic. Treat `success: false` as the sole
discriminator — do not branch on HTTP status alone.

### 2.6 Pagination

Two patterns coexist depending on the storage backend.

**RDB domains** (offset-based, page / pageSize):

```json
{
  "success": true,
  "message": "Request processed successfully",
  "data": [ { "id": 1, "...": "..." } ],
  "pagination": {
    "currentPage": 1,
    "pageSize": 10,
    "totalItems": 42,
    "totalPages": 5,
    "hasPrevious": false,
    "hasNext": true,
    "nextPage": 2,
    "previousPage": null
  }
}
```

**DynamoDB domains** (cursor-based):

```json
{
  "success": true,
  "message": "Request processed successfully",
  "data": [ { "id": "abc", "...": "..." } ],
  "pagination": {
    "nextCursor": "eyJwayI6...",
    "pageSize": 25,
    "hasNext": true
  }
}
```

Cursor pagination cannot jump pages — feed `nextCursor` back as the `cursor`
query parameter to fetch the next page. There is no `totalItems` for cursor
responses by design (DynamoDB does not provide cheap counts).

Which domain uses which pattern is documented in the OpenAPI spec per route.

### 2.7 CORS

CORS origins are controlled by the `ALLOW_ORIGINS` env var on the backend
(default `["*"]` for the blueprint). For staging / prod, expect the backend
team to lock this down to a specific frontend origin list. If you hit
`No 'Access-Control-Allow-Origin' header is present`, ask for that env value to
include your origin — do not reach for a proxy as the first step.

### 2.8 Breaking change signals

The blueprint does not yet publish a versioned changelog beyond git history.
Watch for:

- A bump in the `/v1/...` prefix (a new prefix means a parallel breaking version)
- Removed or renamed fields in the OpenAPI spec — a CI job that diffs
  `openapi.json` between PRs is the cheapest way to catch this
- Backend release notes referencing `BREAKING:` in the commit subject

If you import the spec into Postman or generate an SDK, regenerate after every
backend release to surface drift early.

---

## 3. Test Client Choice

The browser docs UIs (Swagger / ReDoc / Scalar / Stoplight Elements / RapiDoc) lose
their state on reload. For any workflow where you need to keep tokens,
environments, or saved request bodies, use a real client. Importing the
OpenAPI spec gives you a starting collection in any of these tools.

| Tool | Persistence | Git-friendly | Self-host | OpenAPI import | Pick when |
|------|-------------|--------------|-----------|----------------|-----------|
| Postman        | account / cloud | no (proprietary) | no | yes | Team standard already; you want the largest ecosystem |
| Bruno          | local files (`.bru`) | yes | desktop only | yes | You want collections versioned alongside the frontend repo |
| Insomnia       | local | partial | self-host paid | yes | Lightweight Postman alternative, single dev |
| Hoppscotch     | local + self-host | partial | yes (OSS) | yes | You need a self-hosted OSS web client |
| Scalar Client  | local | no | yes | yes (docs-integrated) | You want a try-it that lives next to the docs |

**Recommendation**: Bruno for new teams. Collections are plain `.bru` files, so
you can commit them to the frontend repo, share environments via dotenv-style
files, and review request changes in PRs the same way you review code.

---

## 4. TypeScript SDK Generation

For a typed client that stays in sync with the backend spec, generate it from
`openapi.json` instead of writing fetch calls by hand.

### Hey API (`@hey-api/openapi-ts`)

The most active 2026 generator. Used by Vercel, PayPal, and OpenCode.

```bash
npx @hey-api/openapi-ts \
  --input http://127.0.0.1:8001/api/openapi.json \
  --output src/api/client
```

The output includes typed services, a fetch-based client, and request/response
schemas. Pin the exact version in `package.json` and re-run on every backend
release to catch breaking changes at compile time.

### Orval

Pick this if you want generated React Query / SWR / Vue Query hooks instead of
a raw client.

```bash
npx orval --config ./orval.config.ts
```

`orval.config.ts` points at the spec URL or the local `openapi.json` and chooses
the framework target (`react-query`, `swr`, `vue-query`, `angular`, …).

---

## 5. Getting the Spec

Three ways, in order of preference:

1. **Browser**: open `/docs` and click `Download OpenAPI (JSON)`. The download
   route sets `Content-Disposition: attachment`, so your browser saves a
   real `openapi.json` file rather than rendering it.
2. **Live URL**: clients that accept a URL can pull
   `http://127.0.0.1:8001/api/openapi.json` directly. Useful for SDK
   generators run in CI against a running dev server.
3. **Repo artifact (future)**: if the backend team adopts a CI step that
   commits `docs/openapi/openapi.json` on every release, the frontend can
   diff it in PRs and pin SDK regeneration to a specific commit. Not yet
   wired into this blueprint.

The spec is only exposed in dev environments by default
(`Settings.openapi_url` is `None` when `ENV=stg|prod`). For environments
beyond dev, ask the backend team how they intend to publish the spec —
runtime exposure, CI artifact, or auth-gated internal route.

---

## 6. Mock Server (Optional)

If the frontend needs to start before the backend route exists, the blueprint
does not ship a mock server, but the spec works with external mock tools:

- [`@stoplight/prism`](https://github.com/stoplightio/prism) — OSS, runs from
  the spec file (`prism mock openapi.json`)
- Apidog / Postman mock servers — hosted, paid above the free tier

Mock-first development is a frontend choice and stays out of the backend repo.

---

## 7. Quick Smoke Test

Once you have the spec imported, the following sequence verifies your tooling
is wired correctly against a running `make quickstart` instance. Note the
camelCase field names and the `data.` envelope on the responses:

```bash
BASE=http://127.0.0.1:8001/api/v1

# 1. Register (returns the same shape as login — accessToken in data)
curl -sS -X POST "$BASE/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","fullName":"Alice","email":"alice@example.com","password":"alicepass"}'

# 2. Login → capture access token from data.accessToken
TOKEN=$(curl -sS -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"alicepass"}' | jq -r '.data.accessToken')

# 3. Call a protected route
curl -sS "$BASE/auth/me" -H "Authorization: Bearer $TOKEN"
```

If step 3 returns a `success: true` envelope with the user payload under
`data`, your auth flow is wired correctly and you are ready to import the
spec into your client of choice.
