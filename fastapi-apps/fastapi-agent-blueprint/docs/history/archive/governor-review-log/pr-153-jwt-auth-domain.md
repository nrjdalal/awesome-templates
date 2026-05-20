# PR #153 - JWT Authentication Domain

## Summary

PR [#153](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/153) implements issue #4 by adding a non-CRUD `auth` domain for HS256 JWT register, login, refresh, logout, and current-user lookup. The PR adds strict JWT settings, DB-backed hashed refresh-token persistence and revocation, `/v1/auth/*` routes, Bearer protection for the existing `user` API routes, auth-focused unit/integration/e2e tests, and shared status reference updates. The PR is governor-changing because it touches Tier A paths: `docs/ai/shared/project-dna.md` and `.claude/rules/project-status.md`.

## Review Rounds

1. **Round 0 - Plan cross-review**
   - Target: feature plan for issue #4.
   - Prompt focus: JWT domain scope, NiceGUI admin boundary, serverless compatibility, FastMCP follow-up separation, and commit/PR/review sequence.
   - Surfaced points:
     - R0.1: use a dedicated `auth` domain instead of adding login-only methods to `user`.
     - R0.2: keep `AuthService` non-CRUD and compose flows through `AuthUseCase`.
     - R0.3: persist refresh-token revocation with DB rows and no plaintext token storage.
     - R0.4: add strict JWT setting validation and preserve existing user e2e success paths with valid Bearer tokens.
   - Final Verdict: merge-ready plan after the listed reinforcements were included.

2. **Round 1 - Claude implementation review before PR creation**
   - Target: local implementation diff before commits and PR creation.
   - Prompt focus: architecture/security correctness, test coverage, and stale reference drift.
   - Surfaced points:
     - R1.1: duplicate `pyjwt` dependency entry.
     - R1.2: missing `min_length` on auth credential input strings.
     - R1.3: recommended e2e coverage for expired refresh token, duplicate registration, and login enumeration parity.
   - Final Verdict: approve with changes.

3. **Round 2 - Codex completion-gate review**
   - Target: PR #153 local branch diff after PR creation.
   - Prompt focus: `/review-pr`, `/review-architecture auth`, `/security-review auth`, and `/sync-guidelines` self-application.
   - Surfaced points:
     - R2.1: `RefreshTokenRequest.refresh_token` and `LogoutRequest.refresh_token` needed explicit maximum length bounds.
     - R2.2: Tier A changes require this governor-review-log entry and README index row before the completion gate closes.
   - Final Verdict: minor fixes recommended until the input-bound patch and governor artifacts land.

4. **Round 3 - Claude Opus 4.7 max `/review-pr`**
   - Target: PR #153 after the refresh-token request length patch.
   - Prompt focus: diff-scope correctness, architecture/security grounding, JWT token security, refresh-token reuse/revocation, route protection, drift decision, volatile facts, and completion-gate closure.
   - Surfaced points:
     - R3.1: governor-review-log entry missing for PR #153.
     - R3.2: governor-review-log README index row missing for PR #153.
     - R3.3: PR body governor checkboxes still need final updates after repository artifacts exist.
     - R3.4: `AuthContainer` duplicates `UserRepository` / `UserService` factories instead of consuming `UserContainer`.
     - R3.5: PR labels are absent.
     - R3.6: `TokenPairData` carries `UserDTO` before router conversion to `TokenPairResponse`.
     - R3.7: refresh-token logout uses a non-locking read before revoke.
     - R3.8: volatile facts for branch, PR number, issue link, and Tier A files were re-verified.
   - Final Verdict: minor fixes recommended; code/security is merge-ready, governor closure remains.

## Inherited Constraints

- IC-153-1: `auth` remains a non-CRUD domain. Do not force `AuthService` into `BaseService` just to match CRUD scaffolding.
- IC-153-2: Refresh tokens are never stored in plaintext. Persistence uses keyed HMAC-SHA256 hashes plus `jti`, `user_id`, expiry, and revocation timestamps.
- IC-153-3: Access tokens remain stateless for serverless compatibility. Stateful behavior belongs to refresh-token revocation and rotation only.
- IC-153-4: NiceGUI admin authentication remains the existing env-var login provider in this PR. JWT/RBAC admin migration is a follow-up, not hidden scope.
- IC-153-5: Existing `user` API routes are Bearer-protected, while `/v1/auth/register` stays the public signup path.
- IC-153-6: Any future RBAC, rate limiting, RS256/key rotation, FastMCP auth integration, or non-user route protection work must treat this PR's JWT claim shape and refresh-token persistence as inherited constraints unless a later ADR supersedes them.
- IC-153-7: Tier 1 edits in this PR are English-only and must keep the governor-review-log closure categories exact: `Fixed`, `Deferred-with-rationale`, or `Rejected`.

## Self-Application Proof

### `/review-architecture auth`

- Scope: `src/auth/`, user repository protocol extension, server bootstrap wiring, and migration `0004_add_auth_refresh_tokens`.
- Sources loaded: `AGENTS.md`, `docs/ai/shared/project-dna.md`, `docs/ai/shared/architecture-review-checklist.md`, and overlapping auth/security rules from `docs/ai/shared/security-checklist.md`.
- Findings: none.
- Evidence:
  - Layer dependency grep found no Domain -> Infrastructure imports in `src/auth/domain`, `src/auth/application`, or `src/user/domain`.
  - `AuthService` depends on `RefreshTokenRepositoryProtocol` and `UserRepositoryProtocol`, not infrastructure repositories.
  - `RefreshTokenRepository` returns `RefreshTokenDTO.model_validate(..., from_attributes=True)`.
  - `AuthContainer` inherits `containers.DeclarativeContainer`, declares `core_container = providers.DependenciesContainer()`, uses Singleton repositories, and Factory services/use cases.
  - `auth_bootstrap.py` wires routers and dependencies, then includes the `/v1` router.
- Drift Candidates:
  - `docs/ai/shared/project-dna.md`: JWT/Authentication status updated to active. `auto-fix: yes`, `sync-required: false after this PR`.
  - `.claude/rules/project-status.md`: project status updated to include `auth`. `auto-fix: yes`, `sync-required: false after this PR`.
- Completion State: complete after this log entry and README index row.
- Sync Required: false after this log entry and README index row.

### `/security-review auth`

- Scope: `src/auth/`, `src/_core/config.py` JWT settings, `src/user/interface/server/routers/user_router.py`, and auth/user e2e tests.
- Sources loaded: `AGENTS.md`, `docs/ai/shared/project-dna.md`, and `docs/ai/shared/security-checklist.md`.
- Findings: none.
- Evidence:
  - JWT decode requires `sub`, `jti`, `type`, `iat`, `exp`, `iss`, and `aud`, enforces configured issuer/audience, and allows only HS256 in v1.
  - Strict environments require explicit `JWT_SECRET_KEY` and reject unsafe placeholders or secrets shorter than 32 bytes.
  - Refresh-token persistence stores HMAC-SHA256 hashes, not plaintext tokens.
  - Refresh-token comparisons use `hmac.compare_digest`.
  - Refresh rotation revokes the current `jti` before issuing a new pair, and reuse returns 401.
  - `/v1/user*` routes use router-level `Depends(get_current_user)`.
  - User responses continue to exclude `password`.
  - Auth code does not add sensitive structured logging fields.
  - Auth request string fields have explicit length bounds, including refresh-token request bodies.
- Drift Candidates:
  - `docs/ai/shared/project-dna.md`: JWT/Authentication status is now active and aligned with live code. `auto-fix: yes`, `sync-required: false after this PR`.
- Completion State: complete with no open security findings.
- Sync Required: false after this log entry and README index row.

### `/review-pr`

- Scope: PR #153, base `main`, head `feat/4-jwt-auth-domain`, affected domains `auth`, `user`, `_core`, and Tier A shared status files.
- Sources loaded: `AGENTS.md`, `docs/ai/shared/project-dna.md`, `docs/ai/shared/architecture-review-checklist.md`, `docs/ai/shared/security-checklist.md`, and `docs/ai/shared/governor-paths.md`.
- Findings: none.
- Drift Candidates:
  - `docs/ai/shared/governor-review-log/pr-153-jwt-auth-domain.md`: required for Tier A change. `auto-fix: yes`, `sync-required: false after this PR`.
  - `docs/ai/shared/governor-review-log/README.md`: index row required. `auto-fix: yes`, `sync-required: false after this PR`.
  - PR #153 body: governor checklist must link this artifact and mark completed review steps after this commit is pushed. `auto-fix: yes`, `sync-required: false after PR body update`.
- Completion State: complete after this log entry, README index row, and PR body update.
- Sync Required: false after this log entry, README index row, and PR body update.

### `/sync-guidelines`

- Mode: review follow-up.
- Input Drift Candidates:
  - `docs/ai/shared/project-dna.md` JWT/Authentication status.
  - `.claude/rules/project-status.md` active-domain and infrastructure status.
  - `docs/ai/shared/governor-review-log/pr-153-jwt-auth-domain.md` missing artifact.
  - `docs/ai/shared/governor-review-log/README.md` missing index row.
  - PR #153 body missing final governor checklist updates.
- `project-dna`: updated.
- `AUTO-FIX`: this log entry and README index row.
- `REVIEW`: none.
- `Remaining`: PR body update outside the repository after this artifact is pushed.
- Next Actions: update PR #153 body to link this entry and mark governor closure checkboxes.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | R0.1: use dedicated `auth` domain instead of login-only `user` methods | Fixed | Implemented `src/auth/` with separate service, use case, router, DI, and tests. |
| Round 0 | R0.2: keep `AuthService` non-CRUD and compose flows through `AuthUseCase` | Fixed | `AuthService` does not extend `BaseService`; `AuthUseCase` owns register/login/refresh/logout orchestration. |
| Round 0 | R0.3: persist refresh-token revocation without plaintext token storage | Fixed | Added `refresh_token` table with `token_hash`, `jti`, expiry, revocation timestamp, repository, and migration. |
| Round 0 | R0.4: strict JWT settings and existing user e2e regression handling | Fixed | Added JWT setting validation and updated user e2e tests to use Bearer tokens. |
| Round 1 | R1.1: duplicate `pyjwt` dependency entry | Fixed | `pyproject.toml` contains a single `pyjwt>=2.10.0` dependency entry. |
| Round 1 | R1.2: missing `min_length` on auth credential input strings | Fixed | `RegisterRequest`, `LoginRequest`, and user create/update string fields now have lower bounds. |
| Round 1 | R1.3: add e2e coverage for expired refresh, duplicate register, and login enumeration parity | Fixed | Added auth e2e tests for all three scenarios. |
| Round 2 | R2.1: refresh-token request bodies need maximum length bounds | Fixed | `RefreshTokenRequest.refresh_token` and `LogoutRequest.refresh_token` now use `max_length=4096`. |
| Round 2 | R2.2: Tier A changes require governor review-log and README index artifacts | Fixed | This file and the README index row close the repository-side artifact requirement. |
| Round 3 | R3.1: governor-review-log entry missing for PR #153 | Fixed | This file is the PR #153 log entry. |
| Round 3 | R3.2: governor-review-log README index row missing for PR #153 | Fixed | README index row added with the PR #153 link. |
| Round 3 | R3.3: PR body governor checkboxes need final update | Fixed | PR body will be updated after this repository artifact is pushed, because the body must link the committed log entry. |
| Round 3 | R3.4: `AuthContainer` duplicates user wiring instead of consuming `UserContainer` | Rejected | No shared rule requires cross-container consumption here, both factories share the same `core_container.database`, and the implementation remains within DI boundaries. |
| Round 3 | R3.5: PR labels are absent | Rejected | PR labels are not required by the repository shared rule sources or the user acceptance criteria for issue #4. |
| Round 3 | R3.6: `TokenPairData` carries `UserDTO` before response conversion | Rejected | `TokenPairData` is an internal use-case return object; routers convert to `TokenPairResponse` and exclude `password` before API serialization. |
| Round 3 | R3.7: logout uses non-locking read before revoke | Rejected | Logout is idempotent; refresh rotation uses `revoke_by_jti` with `with_for_update()` and treats an already-revoked row as reuse. |
| Round 3 | R3.8: volatile facts require re-verification | Fixed | Branch, PR number, base/head, issue link, changed files, and Tier A trigger files were re-verified during `/review-pr`. |
