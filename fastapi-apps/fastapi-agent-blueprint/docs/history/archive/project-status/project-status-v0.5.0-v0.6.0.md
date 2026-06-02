# Project Status — v0.5.0 → v0.6.0 Historical Record

> Archived from `.claude/rules/project-status.md` (#225, 2026-06-03).
> These rows represent features shipped between v0.5.0 (2026-04-29) and v0.6.0 (2026-05-07).
> Live table: [.claude/rules/project-status.md](../../../../.claude/rules/project-status.md).

## Major Changes (v0.5.0 → v0.6.0)

| Feature | Issue | Impact |
|---------|-------|--------|
| JWT Authentication Domain | #4 | Adds `src/auth/` with HS256 access/refresh tokens, DB-backed refresh-token rotation/revocation, `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/auth/me`, and Bearer protection for existing `user` API routes. NiceGUI admin auth was env-var based at #4 landing time; superseded by #154 (PR #155). |
| NiceGUI Admin JWT + Minimal RBAC | #154 (PR #155) | Migrates NiceGUI admin login from `ADMIN_ID`/`ADMIN_PASSWORD` to auth-domain credential check + DB-backed admin role checks. Adds `user.role` field (`UserRole` enum, default `USER_ROLE_USER`) and idempotent `ADMIN_BOOTSTRAP_*` admin seeding. Token-free NiceGUI session metadata preserves #4 JWT claim shape. |
| /docs Selector Revamp + Frontend Handoff | #156 | Replaces purple AI-styled selector with GitHub-flavoured Minimal layout + light/dark toggle. Adds `GET /openapi-download.json` and `docs/frontend-handoff.md` (camelCase serialization, `SuccessResponse` envelope, RDB/cursor pagination shapes, JWT auth flow, CORS, breaking-change signals, Postman/Bruno/Hey API/Orval recipes). |
| Governor-Review Provenance Consolidation | #157 (ADR 047) | Folds per-PR `governor-review-log/` archive into PR-description `## Governor Footer` block (CI-linted by `tools/check_governor_footer.py`). Adds IC durability taxonomy. Promotes durable-governance ICs into ADR 047 Consequences (ADR047-G1~G27). Adds `/sync-guidelines` cosmetic carve-out to governor-paths.md Exclusions. |
| Independent Review Generalization | ADR 048 (PR #187) | Replaces "cross-tool only" mandatory sub-step with three-mode **independent review**: `cross-tool` (another AI tool), `self-structured` (single-tool structured checklist), `human` (non-author reviewer). `[skip-governor-footer]` restricted to non-governor-changing PRs in CI mode — governor-changing PRs cannot escape the requirement (ADR048-G1). Self-Structured Review Checklist added to all four review/sync skill docs. |
| Context Budget Reduction | #186 (PR #187) | Archives 18 v0.4.0→v0.5.0 project-status rows to `docs/history/archive/project-status/`. Updates Current Version Context from v0.4.0 → v0.6.0. Defers AGENTS.md structural split to a follow-up issue (target: always-loaded context below ~600 lines; current after this PR: see issue #186). |
