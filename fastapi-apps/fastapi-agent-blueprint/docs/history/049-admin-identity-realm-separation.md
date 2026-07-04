# 049. Admin Identity Realm Separation — Dedicated Bounded Context + Token Realm

- Status: Accepted
- Date: 2026-06-01
- Related issue: [#218](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/218)
- Supersedes (partial): PR #154/#155 unified-table admin model. The admin-identity invariants IC-155-1~4 (project-dna §15.5) are re-defined against the new `admin_identity` bounded context rather than the shared `user` table. The customer JWT invariants IC-153-2/3/4/6 remain in force for **both** realms.
- Constraints: ADR [047](047-governor-review-provenance-consolidation.md) Governor Footer contract and ADR [048](048-independent-review-generalization.md) independent-review modes remain unchanged. ADR [004](004-dto-entity-responsibility.md) unified-DTO rule applies to the new domain.

## Summary

At #154 (PR #155) admin and customer identity were deliberately unified into a single `user` table distinguished by a `role` column, and a single `AuthService` / `AuthTokenConfig` served all logins. This was the correct minimal choice at the time, but it leaves two security properties unsatisfied:

1. **Credential isolation (blast-radius).** A leak of the customer `user` table also leaks every admin password hash.
2. **Trust boundary.** A single JWT signing secret + audience means a leaked customer signing key can forge admin tokens, and — more subtly — a customer access token (`sub=N`) can be replayed against an admin-gated route and resolve to `admin#N` (privilege escalation).

This ADR separates admin identity into a dedicated `admin_identity` bounded context with **its own credential store AND its own JWT token realm** (distinct secret / issuer / audience / TTL + a separate `admin_refresh_token` table), while keeping the auth *mechanism* (password hashing, JWT codec) as shared `_core` library code. External IdP / SSO / MFA is explicitly **out of scope** and recorded as a documented extension point.

## Background

### The store/trust-boundary distinction (cross-review correction)

An initial proposal favored splitting only the table while sharing the JWT realm ("separate table is enough"). A cross-tool review (Codex `gpt-5.5`, xhigh) flagged this as **half-right and dangerous**:

> Table separation is a *store* boundary. Token separation is a *trust* boundary. Splitting only the store while sharing the signing key/audience lets a customer token (`sub=5`) be interpreted as `admin#5` on an admin route, because the signature still validates. To actually achieve credential isolation + a strong operational boundary you must separate both.

This ADR therefore separates store **and** token realm. What is shared vs separated:

| Shared (`_core`) | Separated (per realm) |
|---|---|
| `hash_password` / `verify_password`, `JwtTokenCodec` (encode/decode/hash), canonical claim shape | credential store (table + repository), token secret / issuer / audience / TTL, refresh-token table, service / use-case / DI, server route dependencies |

### Industry framing

The change moves the blueprint from the Django-style unified-table posture (fine for in-app admins / MVP) toward the Rails-Devise-style separated-principal posture (separate model + scope, shared mechanism). Full control-plane/data-plane separation via an external workforce IdP is the enterprise endpoint and is left as an extension point, not bundled.

## Decision

### D1 — New `admin_identity` bounded context

A new domain `src/admin_identity/` holds admin/operator identities. It follows the standard domain scaffolding (auto-discovered via `discover_domains()`). It owns the `admin_identity` table and an `admin_refresh_token` table. The admin identity has **no `role` column** — membership in the `admin_identity` store *is* the role.

### D2 — Separate admin token realm

Admin tokens are signed with `ADMIN_JWT_SECRET_KEY` and carry `ADMIN_JWT_ISSUER` / `ADMIN_JWT_AUDIENCE` distinct from the customer realm. The HS256 algorithm and leeway are shared mechanism params. The canonical claim shape (IC-153-4: `sub, jti, type, iat, exp, iss, aud`) is preserved; only `iss` / `aud` / secret differ. The config validator (`_validate_environment_safety`) rejects a collapsed realm: `ADMIN_JWT_SECRET_KEY == JWT_SECRET_KEY` or `ADMIN_JWT_AUDIENCE == JWT_AUDIENCE` is a hard error, and in strict envs `ADMIN_JWT_SECRET_KEY` must be explicitly set.

### D3 — Shared JWT codec extracted to `_core`

The encode/decode/hash logic is extracted from `AuthService` into `src/_core/common/jwt_codec.py` (`JwtTokenCodec` + `JwtCodecConfig`), parameterized by realm config. Both `AuthService` (customer) and `AdminAuthService` (admin) construct a codec from their own config. The codec raises codec-local errors (`TokenExpiredError` / `InvalidTokenError`); each service translates them into its own domain exceptions.

### D4 — `user` table purged of admin fields

`role`, `permissions`, `password_temporary`, and `is_bootstrap_admin` are removed from the `user` table/DTO/service/repository and re-homed on `admin_identity`. `user` becomes a pure customer identity. Migration 0007 copies existing `role='admin'` rows into `admin_identity`, deletes them from `user` (cascading their customer refresh tokens), and drops the four columns (SQLite via `op.batch_alter_table`).

### D5 — Admin auth API + re-pointed gates

A new `/v1/admin/login|refresh|logout` API issues admin-realm tokens. The `require_admin` server dependency moves to `admin_identity` and verifies admin-realm tokens against the admin store (resolving `sub` against `admin_identity`, not `user`). The NiceGUI `AdminAuthProvider` is re-pointed to the admin use-case but keeps its token-less 4-key session model (IC-155-1 preserved).

### D6 — External IdP as documented extension (out of scope)

External workforce IdP / SSO / MFA / SCIM and a physically separate admin database are **not** implemented. They are recorded here as the sanctioned extension path: swap `AdminAuthService.verify_credentials` for an IdP-backed verifier and/or point the `admin_identity` repository at a separate database URL. No core change is required to adopt them later.

## Consequences

- **ADR049-G1 (durable-domain)** — Admin and customer identities live in physically separate stores (`admin_identity` vs `user`). No admin row may exist in `user`; `user` carries no admin/role fields. Cross-realm reads go through the owning domain's repository only.
- **ADR049-G2 (durable-domain)** — The admin token realm MUST use a signing secret and audience distinct from the customer realm. Collapsing them (equal secret or equal audience) is a configuration error and is rejected at startup. This is the trust boundary; do not weaken it for convenience.
- **ADR049-G3 (durable-domain)** — Auth *mechanism* (password hashing, `JwtTokenCodec`, token hashing) is shared via `_core`; auth *trust boundary* (store, realm config, refresh table, route dependency) is per-realm. New auth realms follow this split — share mechanism, separate boundary.
- **ADR049-G4 (durable-domain)** — `require_admin` and any future admin-gated route MUST verify admin-realm tokens against the `admin_identity` store. A customer-realm token presented to an admin route MUST be rejected at the signature/audience layer (regression-tested).
- **ADR049-G5 (durable-domain)** — IC-155-1 (NiceGUI token-less 4-key session) is preserved: the dashboard still stores only `authenticated` / `user_id` / `username` / `role`-equivalent keys and never raw JWTs. The admin token realm (D2) exists for the admin HTTP API, not the NiceGUI session.
- The full IC-155-1~4 set is re-stated against `admin_identity` in `docs/ai/shared/project-dna.md` §17 (added in the closing `/sync-guidelines` step). IC-153-2/3/4/6 remain binding for both realms.
- **Migration risk:** existing admin sessions/tokens are invalidated on deploy — admins must re-login. Intended; note in release notes.
- **Scope:** large change; may land as stacked PRs (foundation+scaffold / wiring+strip / migration+tests+docs).
