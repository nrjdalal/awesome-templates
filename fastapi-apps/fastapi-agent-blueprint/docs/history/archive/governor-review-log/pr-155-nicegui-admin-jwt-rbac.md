# PR #155 - NiceGUI Admin JWT/RBAC Migration

## Summary

PR [#155](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/155) implements issue #154 by moving NiceGUI admin authentication from `ADMIN_ID` / `ADMIN_PASSWORD` environment-variable credential checks to the existing auth-domain credential verification flow plus DB-backed `user.role == "admin"` authorization. The implementation keeps the issue #4 JWT claim shape unchanged, avoids storing access/refresh/JWT tokens in NiceGUI session storage, adds idempotent `ADMIN_BOOTSTRAP_*` admin seeding, updates targeted tests, and syncs admin-auth references. The PR is governor-changing because it touches Tier A shared reference files under `docs/ai/shared/**` and the Tier C workflow file `.github/workflows/ci.yml`.

## Review Rounds

1. **Round 0 - Feature plan cross-review**
   - Target: issue #154 execution plan before implementation.
   - Prompt focus: NiceGUI admin boundary, inherited issue #4 JWT constraints, refresh-token storage safety, role-claim avoidance, bootstrap admin scope, and PR/review sequencing.
   - Surfaced points:
     - R0.1: Browser-side token storage or direct `/v1/auth/login` reuse is not a good NiceGUI admin fit.
     - R0.2: `AuthUseCase.login()` token-pair issuance would create unnecessary refresh-token state for the admin UI.
     - R0.3: Admin login should use a dedicated admin flow backed by `AuthService.verify_credentials()`.
     - R0.4: Admin authorization must stay DB-side; do not add `role` to JWT claims.
     - R0.5: Initial admin creation/promotion belongs in an explicit bootstrap setting path, not in the login authority.
   - Final Verdict: merge-ready plan after selecting the token-free admin session approach.

2. **Round 1 - Codex implementation self-review**
   - Target: PR #155 local branch diff against `main` after the draft PR was created.
   - Prompt focus: `/review-pr` equivalent over architecture rules, security checklist, governor-trigger detection, and stale env-var references.
   - Note: a separate `codex exec -m gpt-5.5 --sandbox read-only` attempt was blocked by sandbox/session permissions and then rejected by the escalation reviewer because it would transmit private workspace data to an external model service. The blocked path was not bypassed; this round records the current Codex session's read-only self-review plus the successful Claude cross-review in Round 2.
   - Surfaced points:
     - R1.1: `.github/workflows/ci.yml` still passed `ADMIN_ID` / `ADMIN_PASSWORD` to CI jobs.
     - R1.2: Tier A/C changes require a PR-numbered governor-review-log entry and README index row.
   - Final Verdict: minor fixes recommended until the stale CI env vars and governor artifacts land.

3. **Round 2 - Claude Opus max-effort cross-review**
   - Target: PR #155 diff after the CI env cleanup.
   - Prompt focus: admin auth migration, JWT claim preservation, NiceGUI session purity, bootstrap idempotency, and Tier A/C governor requirements.
   - Surfaced points:
     - R2.1: Missing `docs/ai/shared/governor-review-log/pr-155-*.md` entry and README index row.
     - R2.2: Bootstrap promotion of an existing non-admin user was correct but logged only the generic ready event.
     - R2.3: Auth responses excluded `password` explicitly but relied on `UserResponse` shape to drop `role`.
     - R2.4: `require_auth()` is now async, so shared admin-page examples and review guidance must show `await require_auth()`.
   - Final Verdict: conditional pass before fixes; merge-ready after the listed artifacts and low-risk hardening patches land.

4. **Round 3 - Closure review after fixes**
   - Target: branch diff after addressing R1 and R2 points.
   - Prompt focus: verify that the review findings were either fixed or explicitly closed.
   - Surfaced points:
     - R3.1: R2.2 and R2.3 were fixed by the review follow-up commit.
     - R3.2: R2.4 was fixed by syncing `project-dna`, `add-admin-page`, `security-checklist`, and the security-review sample.
     - R3.3: R1.2/R2.1 are fixed by this log entry and the README index row; the PR body is the remaining GitHub-side update after push.
   - Final Verdict: merge-ready after final verification and PR body update.

## Inherited Constraints

- IC-153-1: `auth` remains a non-CRUD domain. Do not force `AuthService` into `BaseService` just to match CRUD scaffolding.
- IC-153-2: Refresh tokens are never stored in plaintext. Persistence uses keyed HMAC-SHA256 hashes plus `jti`, `user_id`, expiry, and revocation timestamps.
- IC-153-3: Access tokens remain stateless for serverless compatibility. Stateful behavior belongs to refresh-token revocation and rotation only.
- IC-153-4: The JWT claim shape remains `sub`, `jti`, `type`, `iat`, `exp`, `iss`, and `aud` unless a later ADR supersedes issue #4.
- IC-153-5: Tier 1 edits are English-only and governor-review-log closure categories must be exactly `Fixed`, `Deferred-with-rationale`, or `Rejected`.
- IC-155-1: NiceGUI admin session storage may contain only authentication metadata needed by the UI (`authenticated`, `user_id`, `username`, `role`); it must not store access tokens, refresh tokens, or raw JWTs.
- IC-155-2: NiceGUI admin authorization is DB-role based. Non-admin users and wrong passwords both surface as invalid credentials.
- IC-155-3: `ADMIN_BOOTSTRAP_*` settings are seed-only. They may create or promote the initial admin user, but they are never the primary login authority.
- IC-155-4: Minimal RBAC for this PR is limited to `user.role` admin authorization. Permission tables, public role-management APIs, and admin role-management UI remain follow-up scope.

## Self-Application Proof

### `/review-pr` Equivalent

- Scope: PR #155, base `main`, head `feat/154-nicegui-admin-jwt-rbac`, issue #154, affected areas `auth`, `user`, `_core.infrastructure.admin`, `_apps.admin`, admin pages, env examples, workflow env, tests, and shared references.
- Sources loaded: `AGENTS.md`, `docs/ai/shared/project-dna.md`, `docs/ai/shared/architecture-review-checklist.md`, `docs/ai/shared/security-checklist.md`, `docs/ai/shared/governor-paths.md`, `docs/ai/shared/governor-review-log/pr-153-jwt-auth-domain.md`, and changed files from `git diff main...HEAD`.
- Findings: none after the R1/R2 follow-up patches.
- Drift Candidates:
  - `docs/ai/shared/project-dna.md`: DB-backed admin auth status and async admin page example. `auto-fix: yes`, `sync-required: false after this PR`.
  - `docs/ai/shared/security-checklist.md`: admin auth and `await require_auth()` review wording. `auto-fix: yes`, `sync-required: false after this PR`.
  - `docs/ai/shared/skills/add-admin-page.md`: async page guard example. `auto-fix: yes`, `sync-required: false after this PR`.
  - `docs/ai/shared/skills/security-review.md`: sample admin-auth review wording. `auto-fix: yes`, `sync-required: false after this PR`.
  - `docs/ai/shared/governor-review-log/pr-155-nicegui-admin-jwt-rbac.md`: required for Tier A/C change. `auto-fix: yes`, `sync-required: false after this PR`.
  - `docs/ai/shared/governor-review-log/README.md`: index row required. `auto-fix: yes`, `sync-required: false after this PR`.
  - PR #155 body: governor checklist must link this artifact and mark completed review steps after this commit is pushed. `auto-fix: yes`, `sync-required: false after PR body update`.
- Completion State: complete after this log entry, README index row, final verification, and PR body update.
- Sync Required: false after this log entry, README index row, and PR body update.

### `/review-architecture` Equivalent

- Scope: `src/auth/`, `src/user/`, `src/_core/infrastructure/admin/`, `src/_apps/admin/`, discovered admin pages, and migration `0005_add_user_role`.
- Sources loaded: `AGENTS.md`, `docs/ai/shared/project-dna.md`, and `docs/ai/shared/architecture-review-checklist.md`.
- Findings: none.
- Evidence:
  - Layer grep found no Domain -> Infrastructure imports in the changed auth/user domain surfaces.
  - `AuthService` stays non-CRUD and owns credential verification, JWT encode/decode, and refresh-token persistence delegation.
  - `AuthUseCase.admin_login()` and `get_admin_session()` orchestrate admin-only authorization without issuing token pairs.
  - `UserService.ensure_admin_user()` owns idempotent create/promote behavior and uses repository protocols.
  - `BaseAdminPage`, page auto-discovery, layout rendering, and sensitive-field masking remain intact.
  - Existing admin page handlers now await `require_auth()` before rendering.
  - Migration `0005_add_user_role` upgrades and downgrades the `user.role` column with a server default for existing rows.
- Drift Candidates: same as `/review-pr` equivalent.
- Completion State: complete with no open architecture findings.
- Sync Required: false after this PR.

### `/security-review` Equivalent

- Scope: admin login/session flow, JWT claim regression, bootstrap admin settings, public auth/user API responses, logging, and CI/env references.
- Sources loaded: `AGENTS.md`, `docs/ai/shared/project-dna.md`, and `docs/ai/shared/security-checklist.md`.
- Findings: none after the R2 follow-up patches.
- Evidence:
  - Admin credential checks delegate to `AuthService.verify_credentials()` through `AuthUseCase.admin_login()`.
  - Non-admin users and wrong passwords both raise `InvalidCredentialsException`.
  - JWT encode/decode still requires only `sub`, `jti`, `type`, `iat`, `exp`, `iss`, and `aud`; tests assert no `role` claim.
  - NiceGUI `app.storage.user` stores only `authenticated`, `user_id`, `username`, and `role`; unit tests assert no access or refresh token keys.
  - Public auth/user responses explicitly exclude `password` and `role`.
  - `ADMIN_BOOTSTRAP_ENABLED` defaults to false; enabled bootstrap requires a password and strict environments reject `admin`.
  - Bootstrap logs distinguish create, already-admin, and promote-existing paths without logging passwords or tokens.
  - CI no longer passes `ADMIN_ID` / `ADMIN_PASSWORD`.
- Drift Candidates: same as `/review-pr` equivalent.
- Completion State: complete with no open security findings.
- Sync Required: false after this PR.

### `/sync-guidelines` Equivalent

- Mode: review follow-up.
- Input Drift Candidates:
  - Admin auth status in `project-dna`.
  - Admin auth checks in `security-checklist`.
  - Async `require_auth()` examples in `project-dna` and `add-admin-page`.
  - Sample security-review wording.
  - Governor log and README index requirements.
  - PR body governor checklist.
- `AUTO-FIX`: `project-dna`, `security-checklist`, `docs/ai/shared/skills/add-admin-page.md`, `docs/ai/shared/skills/security-review.md`, this log entry, and README index row.
- `REVIEW`: none.
- `Remaining`: update the PR #155 body after this artifact is pushed.
- Next Actions: run full verification, push the branch, update PR #155 body, and mark the draft PR ready once checks and reviews are closed.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | R0.1: browser token storage or direct `/v1/auth/login` reuse is not a good NiceGUI admin fit | Fixed | Implemented a token-free `AdminSessionDTO` and `AdminAuthProvider` session metadata flow. |
| Round 0 | R0.2: `AuthUseCase.login()` token-pair issuance would create unnecessary refresh-token state for admin UI | Fixed | `AuthUseCase.admin_login()` returns `AdminSessionDTO` and does not call `issue_token_pair()`. |
| Round 0 | R0.3: admin login should use a dedicated admin flow backed by credential verification | Fixed | `AdminAuthProvider.authenticate()` delegates to `AuthUseCase.admin_login()`, which calls `AuthService.verify_credentials()`. |
| Round 0 | R0.4: admin authorization must stay DB-side, with no `role` JWT claim | Fixed | `user.role` is checked after credential verification; JWT claim regression tests assert the exact issue #4 claim set. |
| Round 0 | R0.5: initial admin creation/promotion belongs in explicit bootstrap settings | Fixed | Added `ADMIN_BOOTSTRAP_*` settings and idempotent `UserService.ensure_admin_user()`. |
| Round 1 | R1.1: CI still passed `ADMIN_ID` / `ADMIN_PASSWORD` | Fixed | `.github/workflows/ci.yml` now uses `ADMIN_BOOTSTRAP_ENABLED=false` and no old admin login env vars. |
| Round 1 | R1.2: Tier A/C changes require governor artifacts | Fixed | This file and the README index row close the repository-side artifact requirement. |
| Round 1 | R1.3: separate `codex exec` read-only review was blocked by sandbox/external-transfer policy | Deferred-with-rationale | The blocked external execution was not bypassed; current-session Codex self-review plus Claude Opus cross-review were used and recorded. |
| Round 2 | R2.1: governor-review-log entry and README index row were missing | Fixed | This file and the README index row add the required PR-numbered trail. |
| Round 2 | R2.2: bootstrap promotion path needed distinct observability | Fixed | `UserService.ensure_admin_user()` now logs created, already-admin, and promoted cases separately without sensitive fields. |
| Round 2 | R2.3: public auth response role exclusion should be explicit | Fixed | Auth response mapping now excludes both `password` and `role`. |
| Round 2 | R2.4: async `require_auth()` pattern needed shared doc/skill sync | Fixed | Updated `project-dna`, `add-admin-page`, `security-checklist`, and the `security-review` sample. |
| Round 3 | R3.1: R2.2/R2.3 closure needed verification | Fixed | Targeted auth/user tests and ruff passed after the review follow-up patch. |
| Round 3 | R3.2: R2.4 closure needed sync verification | Fixed | Shared admin-page examples now show the awaited guard pattern. |
| Round 3 | R3.3: repository-side governor artifacts and PR body update needed sequencing | Fixed | Repository artifacts are added here; PR body update is the final GitHub-side step after push. |
