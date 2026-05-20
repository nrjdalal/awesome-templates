# PR #156 — `/docs` Selector Revamp + Frontend Handoff Guide

## Summary

PR [#156](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/156) replaces the AI-styled purple `/docs` selector with a GitHub-flavoured Minimal layout (large list rows + emoji recognition cue + primary card accent strip + light/dark toggle), adds a `GET /openapi-download.json` route returning the live spec with `Content-Disposition: attachment`, ships `docs/frontend-handoff.md` describing the operating contract that the OpenAPI spec alone cannot communicate (camelCase serialization, `SuccessResponse` envelope, JWT auth flow, RDB / cursor pagination shapes, CORS, breaking-change signals, plus Postman / Bruno / Hey API / Orval recipes), and syncs every quickstart / demo / tutorial trail (`README.md`, `docs/README.ko.md`, `docs/quickstart.md`, `docs/reference.md`, `docs/tutorial/first-domain.md`, `examples/README.md`, `Makefile`, `scripts/demo.sh`, `scripts/demo-rag.sh`) so they point at `/docs` (selector) instead of `/docs-swagger` directly. Production guard tests added: `Settings.docs_url` gating, selector body assertions, attachment download, legacy `?theme=` graceful fallthrough, and all five CDN-mounted docs UI routes.

The PR is governor-changing because the closing `/sync-guidelines` step also updated `.claude/rules/architecture-conventions.md`, `.claude/rules/project-status.md`, `.claude/rules/project-overview.md`, and `.claude/rules/commands.md` (Tier A/B per `docs/ai/shared/governor-paths.md`).

## Review Rounds

1. **Round 0 — Design plan cross-review (codex CLI)**
   - Target: v1 plan for the selector revamp + handoff guide before any code edits.
   - Prompt focus: contract scope sources, dependency surfaces, security gates, route layering.
   - Surfaced points:
     - R0.1: PyYAML was transitive-only — adding `/openapi.yaml` would silently break unless `pyproject.toml` declared the direct dep.
     - R0.2: Selector card pointing at `docs/frontend-handoff.md` would 404 until merged because the server does not statically serve `docs/`.
     - R0.3: `?download=1` on the FastAPI built-in `/openapi.json` cannot flip to `Content-Disposition: attachment`.
   - Final Verdict: minor fixes recommended → v2 plan dropped the YAML route, switched to a dedicated `/openapi-download.json`, pinned the handoff link to GitHub `main`.

2. **Round 1 — First implementation cross-review (codex CLI, read-only)**
   - Target: initial `frontend-handoff.md` draft + `/openapi-download.json` route + selector card reorder.
   - Surfaced points:
     - R1.1: Login response example was un-wrapped and snake_case (`access_token` at top level), but the live response is `SuccessResponse(data={"accessToken": ...})` due to the `to_camel` alias generator.
     - R1.2: Error envelope and pagination shapes had the same camelCase / wrapper drift.
     - R1.3: Smoke-test `jq -r '.access_token'` would not capture the token from the wrapped envelope.
     - R1.4: Register payload was missing the required `fullName` field, so the curl example would 422.
   - Final Verdict: block until R1.1–R1.4 fixed. Rewrote §2 of the handoff guide to mirror the actual `ApiConfig` (`alias_generator=to_camel`, `populate_by_name=True`).

3. **Round 2 — Refined preview legibility cross-review (codex CLI, read-only)**
   - Target: 4 preview themes (Brutalist / Editorial / Minimal / Mac) + Refined v1 + dispatch.
   - Surfaced points:
     - R2.1: Refined v1 stripped emoji because they were lumped under "AI cliché", but emoji glyphs were the actual recognition cue carrying legibility — Refined v2 must restore them.
     - R2.2: Editorial `_editorial_row()` ignored `kind`, so primary and secondary rows rendered identically (silent hierarchy bug).
     - R2.3: Toolbar mixed preview links + theme toggle in one helper, making cleanup ambiguous.
     - R2.4: Container background and card background were both `var(--card)` in dark mode, flattening the surface contrast.
   - Final Verdict: conditional pass after fixes → v2 reintroduces emoji, primary card accent strip, dark `--surface` variable, and `aria-hidden` on the icon spans.

4. **Round 3 — Cleanup cross-review (codex CLI, read-only)**
   - Target: PR after Minimal was promoted to production tone and the four preview themes plus Refined were deleted.
   - Surfaced points:
     - R3.1: `?theme=brutalist` URLs would silently fall through to default rather than hard-failing — graceful but should be locked by a regression test.
     - R3.2: Five docs UI mounts (Swagger / ReDoc / Scalar / Stoplight Elements / RapiDoc) had no route guard; cleanup risk would leave one orphaned.
     - R3.3: `frontend-handoff.md` §3 listed only four browser viewers (ReDoc missing) — drift against the live selector.
   - Final Verdict: conditional pass → added `test_legacy_theme_query_falls_through_to_default`, parametrized `test_docs_ui_routes_serve_html`, and ReDoc back into the handoff guide.

5. **Round 4 — `/sync-guidelines` cross-review (codex CLI, read-only)**
   - Target: closing-gate sync of `.claude/rules/*` plus `project-dna` §8 evaluation against the PR #156 + #155 surface.
   - Surfaced points:
     - R4.1: `.claude/rules/project-status.md` #4 JWT row still claimed "NiceGUI admin auth remains env-var based" — superseded by #154 (PR #155).
     - R4.2: `.agents/skills/sync-guidelines/SKILL.md` shipped a 5-item `Procedure` block (with the reading instruction merged into step 1) while the Claude wrapper had a 4-item `Procedure Overview` — Hybrid C drift.
     - R4.3: Committing the sync edits onto PR #156 changes its classification from "non-governor-changing" to governor-changing because `.claude/rules/**` is Tier A/B.
   - Final Verdict: block merge until #4 row is corrected, the agents wrapper is reshaped to match the Claude `Procedure Overview` pattern, and the governor-review-log entry plus PR template Governor section land. All three were closed in the same sync push (this entry is part of R4.3 closure).

6. **Round 5 — closure-on-closure cross-review (codex CLI, read-only)**
   - Target: this entry, the README index row, the PR body Governor section, and the four `.claude/rules/*` files after commit 9616511.
   - Prompt focus: Round 4 R-point closures, Inherited Constraint shape (forward-looking vs descriptive), G closure linter conformance, Tier 1 language policy, Hybrid C phase parity, orphan claims.
   - Surfaced points:
     - R5.1: Self-Application Proof claimed "4 codex CLI reviews" while Review Rounds enumerated Round 0-4 (5 rounds) — internal count mismatch.
   - Verified: G closure linter passes (4-column shape, canonical labels), Tier 1 language checker passes (0 violations), Hybrid C parity restored (shared procedure 4 phases / both wrappers 4-step Procedure Overview), R4.1 + R4.2 + local half of R4.3 closed.
   - Final Verdict: closed after the R5.1 minor fix.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | R0.1: PyYAML is transitive-only — adding `/openapi.yaml` would break unless `pyproject.toml` declared it directly | Fixed | v2 plan dropped the YAML route entirely. |
| Round 0 | R0.2: selector card pointing at `docs/frontend-handoff.md` would 404 because the server does not statically serve `docs/` | Fixed | Card link pinned to a GitHub `main` URL. |
| Round 0 | R0.3: `?download=1` cannot flip the FastAPI built-in `/openapi.json` to `Content-Disposition: attachment` | Fixed | Added a dedicated `/openapi-download.json` route. |
| Round 1 | R1.1: handoff guide login example was un-wrapped + snake_case while the live response is `SuccessResponse(data={"accessToken": ...})` via `to_camel` alias | Fixed | Rewrote `frontend-handoff.md` §2 to mirror the actual `ApiConfig`. |
| Round 1 | R1.2: error envelope and pagination shapes had the same wrapper / camelCase drift | Fixed | Fields normalised to camelCase (`errorCode`, `currentPage`, `nextCursor`). |
| Round 1 | R1.3: smoke-test `jq -r '.access_token'` would not capture the wrapped token | Fixed | Updated to `jq -r '.data.accessToken'`. |
| Round 1 | R1.4: register payload was missing the required `fullName` field | Fixed | Curl example completed. |
| Round 2 | R2.1: Refined v1 stripped emoji as "AI cliché" but emoji glyphs were the actual recognition cue | Fixed | Refined v2 restored emoji + introduced `icon` field on `DOCS_CARDS` / `_handoff_cards`. |
| Round 2 | R2.2: Editorial `_editorial_row()` ignored `kind`, so primary and secondary rendered identically | Fixed | Helper now reads `kind` and applies primary serif accent. |
| Round 2 | R2.3: toolbar mixed preview links with theme toggle in one helper, ambiguating cleanup | Deferred-with-rationale | Cleanup removed the preview toolbar entirely; the surviving production toggle is its own concern. |
| Round 2 | R2.4: `.container` and `.docs-card` shared `var(--card)` so dark surface contrast was flat | Fixed | Added a `--surface` variable; dark card now lifts off the canvas. |
| Round 3 | R3.1: legacy `?theme=brutalist` URLs silently fall through to default — graceful but unguarded | Fixed | `test_legacy_theme_query_falls_through_to_default` locks the contract. |
| Round 3 | R3.2: five docs UI mounts had no route guard; cleanup risk would orphan one | Fixed | Added parametrized `test_docs_ui_routes_serve_html`. |
| Round 3 | R3.3: `frontend-handoff.md` §3 listed only four browser viewers (ReDoc missing) | Fixed | Browser viewer list completed. |
| Round 4 | R4.1: `.claude/rules/project-status.md` #4 JWT row still claimed env-var admin auth, superseded by #154 | Fixed | Row updated with a superseded note. |
| Round 4 | R4.2: `.agents/skills/sync-guidelines/SKILL.md` had a 5-item `Procedure` while Claude wrapper had a 4-item `Procedure Overview` (Hybrid C drift) | Fixed | Agents wrapper reshaped to match the Claude `Procedure Overview` pattern. |
| Round 4 | R4.3: committing the sync edits onto PR #156 changes its classification to governor-changing | Fixed | This entry, the README index row, and the PR body Governor section closed the gate. |
| Round 5 | R5.1: Self-Application Proof claimed "4 codex CLI reviews" while Review Rounds enumerate Round 0-4 (5 rounds), an internal count mismatch | Fixed | Self-Application Proof now reads "5 codex CLI rounds completed" and explicitly enumerates Round 0-4 plus the Round 5 closure-on-closure verification. |

## Inherited Constraints

- IC-156-1: The selector renderer is a single `_render_selector` helper. Theme toggle JS / FOUC-prevention inline script / aria attributes belong to the production surface; they are not preview-time scaffolding.
- IC-156-2: `DOCS_CARDS` and `_handoff_cards()` carry an `icon` field. Renderers that omit the field MUST fall back via `.get("icon", "")` so a future card definition cannot raise `KeyError` in production traffic.
- IC-156-3: `kind` discrimination (`primary` / `secondary`) is the canonical Recommended-vs-rest hierarchy carrier. Helpers that ignore `kind` (the Editorial regression in R2.2) are a regression class — every list-row helper must read `kind`.
- IC-156-4: `/openapi-download.json` is dev-only by design (gated indirectly through `docs_router` registration in `bootstrap.py`). Exposing the spec in stg/prod requires an ADR — `TestDocsUrlGating` is the regression guard.
- IC-156-5: AI-pattern clichés (`linear-gradient`, `-webkit-background-clip`, `backdrop-filter`, ChatGPT-style purple gradient palettes) MUST stay out of the selector renderer. `test_docs_selector_returns_html` greps for the three CSS clichés.
- IC-156-6: The browser docs UI list (Swagger / ReDoc / Scalar / Stoplight Elements / RapiDoc) is referenced in three places: `docs_router.py` mounts, `docs/frontend-handoff.md` §3, and the selector card list. All three must agree — `test_docs_ui_routes_serve_html` is the route guard, but the doc and selector card list still need manual sync on every viewer addition.
- IC-156-7 (carried from #155 IC-155-3): `ADMIN_BOOTSTRAP_*` is seed-only. Quickstart `admin / admin` is the seeded `User`, not a runtime credential channel — `commands.md` admin section MUST describe both the seed env vars and the auth-domain login path.

## Self-Application Proof

### `/review-architecture` equivalent (manual, not the slash skill)

- Scope: `src/_core/application/routers/api/docs_router.py`, `tests/e2e/test_docs_routes.py`, `tests/unit/_core/test_config.py`, `docs/frontend-handoff.md`
- Sources Loaded: AGENTS.md, project-dna.md §1 + §8, drift-checklist.md
- Findings: no Domain → Infrastructure imports (selector lives in `_core/application/`), no Mapper class, no Entity pattern, no AI-pattern CSS clichés in the production renderer.
- Drift Candidates: see Round 4 entries.
- Sync Required: true (closed in this entry).

### `/sync-guidelines` (this run)

- Mode: standalone inspection
- Input Drift Candidates: none
- project-dna: unchanged (§8 evaluated, docs UX out of scope for the active-features axis)
- AUTO-FIX (5 items): `project-status.md` adds rows for #154 (PR #155) and #156, refines RBAC wording, supersedes the stale `#4` admin-auth sentence; `commands.md` admin login note replaced env-var reference with auth-domain JWT + `ADMIN_BOOTSTRAP_*` seed; all four `.claude/rules/*` files have `Last synced: 2026-05-01`.
- REVIEW (1 item): no `project-dna` §8 entry for docs selector / handoff guide — `§8` lists infra and domain capabilities, not docs UX copy. Resolution: not added.
- Remaining: none after R4 closure.
- Next Actions: PR #156 ready to merge once this entry, the README index row, and the PR template Governor section land in the same push.

### Cross-tool review trail

- 5 codex CLI rounds completed (`codex exec --sandbox read-only --skip-git-repo-check`): Round 0 design plan, Round 1 first implementation pass, Round 2 Refined preview legibility, Round 3 cleanup, Round 4 `/sync-guidelines` closure. Round 5 closure-on-closure review verified the artefacts in this entry, the README index row, and the PR body Governor section. All R-points closed via the table above (16 Fixed + 1 Deferred-with-rationale).

### Verification

- `uv run pytest tests/ -q --ignore=tests/unit/_core/infrastructure/persistence/nosql --ignore=tests/integration` → 651 passed / 13 skipped (the skipped surface is the AWS-extra suite that the dev shell does not have installed; the new tests are 9 of the passing count).
- `uv run pre-commit run --all-files` → all hooks green (ruff format + check, mypy boundaries, Tier 1 language policy via `tools/check_language_policy.py`, governor closure via `tools/check_g_closure.py`).
- `python3 tools/check_language_policy.py` → 0 violations.
