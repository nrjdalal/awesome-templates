# Harness Asset Inventory Matrix

> Last synced: 2026-07-10 (#65: added the Antigravity 2.0 adapter — `.gemini/settings.json` + `.antigravity/{plugin,gemini-extension,mcp_config,permissions}.json` + `.antigravity/rules/project-harness.md` + 8 `.antigravity/hooks/*.py` shims; counts 74 → 88 — the prior "73" undercounted Tier 1 by one, see counting note). Prior: 2026-07-09 (#281 / ADR 054: added `.claude/hooks/pre-tool-stage-block.{sh}` + `pre_tool_stage_block.py` Tier 3 rows for the plan→execute hard block; also rowed the previously-omitted `.claude/hooks/session-start-context.sh`; counts 70 → 73). Prior: 2026-07-03 (#268 / ADR 050: added `.claude/hooks/stage-gate.{sh}` + `post_tool_stage_gate.py` Tier 3 rows, `governor/stage_gate.py` module, counts 68 → 70). Prior: 2026-06-29 (#257: added native `execute-plan` Tier 2 row + counts)
> Source of truth: this is a **living inventory**. Update when assets are added, renamed, or removed. `/sync-guidelines` validates that this file matches the actual filesystem.
> Sibling docs: [ADR 045](../../history/045-hybrid-harness-target-architecture.md) · [target-operating-model.md](target-operating-model.md) · [migration-strategy.md](migration-strategy.md)

## Purpose

This matrix answers issue #117 Required Output #1: classify every harness asset into one of four buckets and record the evidence that justifies the classification. It is the input that constrains the Target Operating Model and Migration Strategy.

## Bucket Definitions

The four buckets defined in #117 are interpreted as follows. The original wording in the issue ("Replace — can be replaced by superpowers") is reinterpreted because superpowers is **not** an external package this repo adopts; it is a philosophy reference. See [ADR 045 §Background](../../history/045-hybrid-harness-target-architecture.md) and [archive/044](../../history/archive/044-superpowers-gstack-process-governor-evaluation.md).

| Bucket | Meaning | Example |
|---|---|---|
| **Keep** | Asset stays as-is. Project-specific value that no philosophy port can substitute. | `AGENTS.md`, `project-dna.md`, RDB-architecture skills |
| **Replace** | Asset is rewritten in place to absorb superpowers-style discipline. The file location is unchanged but its content is replaced. | (none in this initial inventory; reserved for future passes) |
| **Overlay** | Asset is preserved but the canonical execution path runs through the new Default Coding Flow. The asset becomes a *reference* that the flow consults, not a primary entry point. | `planning-checklists.md`, `plan-feature` skill, `onboard` skill |
| **Drop** | Asset is removed because it is duplicated, dead, or superseded. | (none in this initial inventory; reserved for future passes) |

## Classification Columns

Each asset is recorded with the following nine fields (issue #117 mandates seven; two more are added for Tier grouping and follow-up tracking).

| Column | Issue #117 mapping | Description |
|---|---|---|
| Asset | asset name | Filesystem path, repo-relative |
| Layer | (added) | Tier 0~4 grouping for readability |
| Current Role | current role | What this asset does in the running harness |
| Why It Exists | why it exists | The constraint or precedent that produced it (often an ADR or issue) |
| Replacement Feasibility | replacement feasibility | Could superpowers-style philosophy substitute it? `None` / `Partial` / `Full` |
| Bucket | (decision) | `Keep` / `Replace` / `Overlay` / `Drop` |
| Final Location | final ownership location | Where the asset lives after Phase 5 |
| Migration Risk | migration risk | `Low` / `Medium` / `High` with one-line rationale |
| Stability/Error-rate Impact | impact on error rate / stability | Net effect on the operational metrics targeted by issue #117 |
| Notes | (added) | Cross-reference to related ADR, issue, or follow-up phase |

---

## Tier 0 — Constitutional Assets

The shared constitution and the tool-level entry points. These files transitively define every downstream asset; they are unconditionally `Keep`.

| Asset | Bucket | Risk | Impact |
|---|---|---|---|
| `AGENTS.md` | Keep | Low (additive section only) | High |
| `CLAUDE.md` | Keep | Low | Medium |
| `.codex/config.toml` | Keep | Low | Medium |
| `.codex/hooks.json` | Keep | Low | Medium |
| `.claude/settings.json` | Keep | Low | Medium |
| `.claude/settings.local.json` | Keep | Low | Low |
| `.gemini/settings.json` | Keep | Medium | High |
| `.antigravity/plugin.json` | Keep | Low | Medium |
| `.antigravity/gemini-extension.json` | Keep | Low | Low |
| `.antigravity/mcp_config.json` | Keep | Medium | Medium |
| `.antigravity/permissions.json` | Keep | Medium | High |
| `.mcp.json` | Keep | Low | Low |
| `docs/history/045-hybrid-harness-target-architecture.md` | Keep | Low | High |
| `.github/pull_request_template.md` | Keep | Low | High |

### `AGENTS.md`

- **Current role**: Canonical shared collaboration rules. Every other harness file references this one.
- **Why it exists**: Cross-tool drift was previously handled by duplicating rules across `CLAUDE.md` and Codex-specific files. Centralised in this document during the Codex CLI adoption (#66).
- **Replacement feasibility**: None. Project-specific architecture and prohibitions cannot be substituted by an external philosophy.
- **Final location**: unchanged.
- **Migration risk**: Low. Phase 1 only adds `§ Default Coding Flow` and Tool-Specific Harnesses cross-links; nothing existing is rewritten.
- **Stability impact**: High. Default Flow precedence rules anchor every later phase.
- **Notes**: Phase 1 edit is the first time this file gains a process-layer section; previously it covered only architecture and conventions.

### `CLAUDE.md`

- **Current role**: Claude-specific harness guide; redirects to `AGENTS.md` for shared rules.
- **Why it exists**: Pre-existed AGENTS.md split (#66). Now an explicit Claude-only entry point.
- **Replacement feasibility**: None. Tool-specific guidance cannot be shared.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Medium. Phase 1 update adds Default Flow cross-link; Phase 2 may add prompt-submit hook reference.
- **Notes**: Quality Gate Flow section becomes a redirect to Default Coding Flow once Phase 4 lands.

### `.codex/config.toml`

- **Current role**: Codex CLI sandbox / approval / web_search settings + MCP servers + research profile.
- **Why it exists**: #66 Codex adoption. Defaults: `sandbox_mode="workspace-write"`, `approval_policy="on-request"`, `web_search="disabled"`, `[profiles.research].web_search="live"`.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low. Phase 1 does not edit this file. Phase 5 may add hook configuration.
- **Stability impact**: High. Default Flow precedence rule (D1.1) explicitly subordinates the flow below this file's sandbox / approval configuration.
- **Notes**: Codex review (R7) emphasised that any web-search-requiring step must explicitly use `profiles.research`; the Phase 0.5 review itself was run under that profile.

### `.codex/hooks.json`

- **Current role**: Five Codex hook chains (SessionStart / UserPromptSubmit / PreToolUse Bash / PostToolUse Bash / Stop), each with a 30~120s timeout.
- **Why it exists**: Mirrors the Claude `.claude/settings.json` hooks structure adopted in #66.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Medium starting Phase 2. UserPromptSubmit gets the exception-token parser; PostToolUse Bash matcher is insufficient for non-Bash edits (Codex R7) and may grow a second hook entry or be supplemented by Stop-side change-detection.
- **Stability impact**: High once hooks land.
- **Notes**: Codex R7 — schema validation of hook payloads must precede Phase 3 work.

### `.claude/settings.json`

- **Current role**: Four Claude hook chains (SessionStart / PreToolUse Edit|Write|Bash / PostToolUse Edit|Write / Stop) + plugin enablement (`pyright-lsp`).
- **Why it exists**: Established by #63 (Serena → pyright-lsp) and #66 cross-tool harness alignment.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Medium starting Phase 3. New hooks attach to existing matchers; payload backward-compatibility must hold.
- **Stability impact**: High.
- **Notes**: PostToolUse matcher set is `Edit|Write` (not Bash-only as in Codex), so Phase 3 verification-first hook can attach here directly; #268 (ADR 050) attaches the stage-gate advisory as the third sibling in the same matcher block. Codex side requires a different shape — see migration-strategy.md.

### `.claude/settings.local.json`

- **Current role**: User-specific overrides; `.gitignore`d.
- **Why it exists**: #66 Codex adoption + Claude harness alignment. Local-only customisation.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low (file is gitignored — no PR can modify it).
- **Stability impact**: Low.
- **Notes**: Track only the existence of the file pattern; contents are user-private.

### `.mcp.json`

- **Current role**: Claude-only MCP server config (currently `context7`).
- **Why it exists**: Context7 stays as MCP per 2026-04 review (`docs/ai/shared/repo-facts.md`).
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Low (does not interact with Default Flow).
- **Notes**: Codex MCP servers live under `.codex/config.toml [mcp_servers.*]`, not here.

### `.gemini/settings.json`

- **Current role**: Antigravity / Gemini CLI project hook configuration. Wires `SessionStart`, `BeforeAgent`, `BeforeTool`, `AfterTool`, and `AfterAgent` to `.antigravity/hooks/` through `.agents/shared/harness-python.sh`.
- **Why it exists**: Antigravity 2.0 parity requires repo-committable hook configuration for Desktop / CLI compatible runtimes.
- **Replacement feasibility**: None. It is the tool-specific adapter surface.
- **Final location**: unchanged.
- **Migration risk**: Medium. Hook event names differ from Claude and Codex, so payload compatibility must be verified against the live runtime.
- **Stability impact**: High. This is the project-local entry point for Antigravity governance reminders.

### `.antigravity/{plugin.json,gemini-extension.json,mcp_config.json,permissions.json}`

- **Current role**: Antigravity plugin manifest, Gemini CLI extension validation manifest, MCP template, and permission template.
- **Why it exists**: Keeps Antigravity setup repo-local while avoiding credentials or machine-local settings in committed files.
- **Replacement feasibility**: None. These files are Antigravity-specific packaging and setup surfaces.
- **Final location**: unchanged.
- **Migration risk**: Medium for permissions / MCP because local runtimes may evolve schema details; low for the two manifests.
- **Stability impact**: Medium. They make the adapter installable, linkable, and reviewable without duplicating shared policy.

### `docs/history/045-hybrid-harness-target-architecture.md`

- **Current role**: ADR 045 — top-level decisions for the hybrid harness target architecture (this initiative). Navigator to the three living docs.
- **Why it exists**: Issue #117 mandates a load-bearing decision record alongside the matrix / operating model / migration strategy.
- **Replacement feasibility**: None (an ADR is immutable history once accepted).
- **Final location**: unchanged.
- **Migration risk**: Low (immutable).
- **Stability impact**: High (every later phase cites this ADR).
- **Notes**: Self-classified — included in the matrix because the matrix is a living inventory and this ADR is itself a constitutional asset of the process layer.

### `.github/pull_request_template.md`

- **Current role**: GitHub PR template. Original purpose was simple change-summary + checklist. Round-4 (Pillar 5) added a "Governor-Changing PR" section that artefact-locks independent review (generalized by ADR 048 from the original cross-tool-only model), self-application proof, and review-trail link.
- **Why it exists**: Round-4 review found that user-memory-only enforcement of cross-tool review is insufficient for new contributors and new sessions. PR template moves the requirement into a repo artefact.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low (additive section; non-governor-changing PRs delete the section).
- **Stability impact**: High (every PR sees the template; governor-changing PRs cannot easily skip the checklist).
- **Notes**: Pillar 5 of ADR 045's Self-Application Recovery.

---

## Tier 1 — Shared Reference and Enforcement Layer

Canonical reference documents and shared enforcement assets that both Claude and
Codex consume. Most are factual or architecture references (`Keep`). Three are
process-discipline checklists that become *consulted* by the Default Coding Flow
rather than primary entry points (`Overlay`).

| Asset | Bucket | Risk | Impact |
|---|---|---|---|
| `project-dna.md` | Keep | Low | High |
| `architecture-diagrams.md` | Keep | Low | Medium |
| `scaffolding-layers.md` | Keep | Low | High |
| `security-checklist.md` | Keep | Low | High |
| `test-patterns.md` | Keep | Low | High |
| `architecture-review-checklist.md` | Keep | Low | Medium |
| `review-protocol.md` | Keep | Low | High |
| `ai-infrastructure-overview.md` | Keep | Low | Medium |
| `repo-facts.md` | Keep | Low | Medium |
| `test-files.md` | Keep | Low | Medium |
| `admin-design-system.md` | Keep | Low | Medium |
| `planning-checklists.md` | Overlay | Low | Medium |
| `drift-checklist.md` | Overlay | Low | Medium |
| `onboarding-role-tracks.md` | Overlay | Low | Low |
| `harness-asset-matrix.md` | Keep | Low | High |
| `target-operating-model.md` | Keep | Low | High |
| `migration-strategy.md` | Keep | Low | High |
| `governor-review-log/` (directory) | Keep | None (frozen) | Low |
| `governor-paths.md` | Keep | Low | High |
| `.agents/shared/governor/` (package) | Keep | Low | High |
| `tools/check_g_closure.py` | Drop | None (removed) | None |
| `tools/check_governor_footer.py` | Keep | Low | High |

### `project-dna.md`

- **Current role**: 976-line canonical pattern catalogue auto-extracted from the codebase. Sections §0~§14 cover directory structure, base classes, generics, CRUD, DI, conversions, security, features, routers, exception, admin, vector, embedding, LLM.
- **Why it exists**: Adopted as part of the Hybrid C harness so that Claude, Codex, and Antigravity read identical architecture references.
- **Replacement feasibility**: None — superpowers carries no project-specific architecture.
- **Final location**: unchanged.
- **Migration risk**: Low (read-only reference).
- **Stability impact**: High. Implementation skills resolve their procedure detail by reading from here.
- **Notes**: Section count and ADR cross-references must remain in sync with `/sync-guidelines` snapshot. New tiers (e.g. §15 Default Flow) would be additive.

### `architecture-diagrams.md`

- **Current role**: Mermaid diagrams for layer dependency, Write/Read flows, RDB / DynamoDB / S3 Vector tables. Re-rendered to SVG via `make diagrams`.
- **Why it exists**: Visual reference; surfaced by `architecture-review-checklist.md`.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Medium.
- **Notes**: Edits require `make diagrams` to refresh exports under `docs/assets/architecture/`.

### `scaffolding-layers.md`

- **Current role**: 299-line scaffolding manual: per-layer file list, paths, import rules. Source of truth for `/new-domain`.
- **Why it exists**: Hybrid C shared procedure for layer scaffolding. Carries the Optional AI Infra Variant section (post-ADR 042).
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low. Phase 1 may add a "Default Flow Position" reference for `/new-domain`.
- **Stability impact**: High.
- **Notes**: Cited from `architecture-conventions.md` and the `/new-domain` skill.

### `security-checklist.md`

- **Current role**: 369-line OWASP-aligned security review reference. Surface for `/security-review`.
- **Why it exists**: Project-specific security stance (auth, OWASP Top 10, key-rotation rules).
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: High.
- **Notes**: `/security-review` skill reads this; no Default Flow change needed for Phase 1.

### `test-patterns.md`

- **Current role**: 144-line test pyramid + factory/fixture patterns. Cited by `/test-domain` and the test-baseline file inventory.
- **Why it exists**: Shared test conventions across domains.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: High. Anchors the `verify` step of the Default Flow.
- **Notes**: Phase 3 verification-first hook will rely on this file's authoritative naming conventions for "what counts as a test for this change".

### `architecture-review-checklist.md`

- **Current role**: 117-line architecture-audit checklist (10 categories; §10 Examples Copy-Flow added by #260). Surface for `/review-architecture`.
- **Why it exists**: Standardise the questions a domain or full-repo review must answer.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Medium.
- **Notes**: Examples-profile carve-out (`examples/todo`) was added 2026-04-26 — see `repo-facts.md`.

### `review-protocol.md`

- **Current role**: Canonical protocol shared by the three review skills (`/review-pr`, `/review-architecture`, `/security-review`): concern dimensions + stable IDs, the Finding Basis rule, the `Findings`/`Coverage` output contract, the intent/PASS `Verdict`, and the GitHub posting/verdict rules.
- **Why it exists**: Unifies the review-skill family so review points, output shape, and posting are deterministic; replaces the per-skill "Core Principle" that forbade correctness/regression findings (issue #274).
- **Replacement feasibility**: None — project-specific review contract.
- **Final location**: unchanged.
- **Migration risk**: Low (read-only reference; skills point to it).
- **Stability impact**: High. All three review skills resolve their contract, dimensions, and posting rules from here; the Reasoning-Level Consistency Guards stay canonical in `AGENTS.md`.
- **Notes**: `review-pr` is the PR-scoped entry point (emits a behavior `Verdict`); the other two are audit-only (`Verdict: N/A (audit-only scope)`). Skills depend on this protocol + the shared checklists, never on each other's bodies.

### `ai-infrastructure-overview.md`

- **Current role**: 162-line overview of LLM / Embedding / RAG / Vector / Classifier patterns (includes OTEL backend comparison matrix, ADR 046).
- **Why it exists**: New-contributor orientation to the AI infra layer.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Medium.
- **Notes**: Pattern-pointer document; rarely edited.

### `repo-facts.md`

- **Current role**: Canonical sources index + tooling decisions log.
- **Why it exists**: Single document the drift checklist consumes.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low (additive only — Phase 1 adds the four new doc references).
- **Stability impact**: Medium.
- **Notes**: This file is updated whenever Tier 0/1 gain new entries.

### `test-files.md`

- **Current role**: 33-line baseline-test file checklist (factories / unit / integration / admin).
- **Why it exists**: Enforces minimum-viable test coverage for new domains.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Medium.
- **Notes**: Examples profile is exempted — short carve-out is documented here, not in the matrix.

### `planning-checklists.md`

- **Current role**: 211-line planning checklist for feature work (Requirements, Data Model, Business Rules, Security, Tasks). Currently consulted by `/plan-feature` only.
- **Why it exists**: Prevent planning omissions in implementation work.
- **Replacement feasibility**: Partial. Default Flow's `framing` and `plan` steps now route to a *subset* of these questions automatically; the full checklist remains as the deep-dive reference.
- **Bucket: Overlay** because the canonical entry point shifts from "user invokes `/plan-feature`" to "Default Flow routes the user through framing → plan, which references this checklist". The file content stays.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Medium.
- **Notes**: After Phase 1, the `/plan-feature` skill body explicitly cites this checklist as Phase 0/2 supporting reference rather than the primary procedure.

### `drift-checklist.md`

- **Current role**: 220-line drift-detection items consumed by `/sync-guidelines`.
- **Why it exists**: Code ↔ shared docs ↔ tool harness alignment.
- **Replacement feasibility**: Partial. Drift-detection becomes a `completion gate` activity in the Default Flow instead of a free-standing skill the user invokes.
- **Bucket: Overlay** for the same reason as planning-checklists.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Medium.
- **Notes**: Phase 1 must add a checklist row for "Tier 0/1/2 entries in `harness-asset-matrix.md` match filesystem".

### `onboarding-role-tracks.md`

- **Current role**: 100-line role-specific onboarding (New / Intermediate / Advanced).
- **Why it exists**: Surface for `/onboard`.
- **Replacement feasibility**: Partial. Onboarding is the most clearly commodity scaffolding among reference docs; only the project-specific intro must remain locally.
- **Bucket: Overlay** — the role tracks themselves are kept; the Default Flow does not invoke onboarding except at session-start.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: Low.
- **Notes**: Could be re-evaluated for `Drop` if a future ADR consolidates onboarding into a single page.

### `harness-asset-matrix.md`

- **Current role**: This document. Living inventory of every harness asset and its bucket.
- **Why it exists**: Issue #117 Required Output #1.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low (additive only — entries are added when assets are added).
- **Stability impact**: High (asset triage authority for every Phase).
- **Notes**: Self-classified. `/sync-guidelines` validates that the matrix matches the actual filesystem (see drift-checklist.md row).

### `target-operating-model.md`

- **Current role**: Long-form Target Operating Model — 7-step Default Flow, mandatory subset, exception model, Claude/Codex/Antigravity alignment, sample-workflow traces.
- **Why it exists**: Issue #117 Required Output #2.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: High (every Phase 2~5 adapter spec resolves to this document).
- **Notes**: Self-classified.

### `migration-strategy.md`

- **Current role**: Phased migration plan — Phase 0~5 spec, rollback, dual-system window, asset movement order.
- **Why it exists**: Issue #117 Required Output #3.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: High (Phase 2~5 acceptance criteria copy from §1).
- **Notes**: Self-classified.

### `governor-review-log/` (directory) — closed historical archive

- **Current role**: **Closed historical archive** (ADR 047 D6). Holds the 18 entries written between PR #125 and PR #158 documenting the Phase 1~5 build-out of the hybrid harness. No new entries are added — independent review provenance for new PRs lives in the PR description's `## Governor Footer` block (`tools/check_governor_footer.py`).
- **Why it exists**: Round-4 self-coherence review (PR #125) made cross-tool review trails first-class repo artefacts during the harness build-out. ADR 047 retired the per-PR archive obligation after the build-out closed; the directory is preserved as a frozen historical record because the IC declarations inside still serve as alias targets for ADR 047's IC Classification Table.
- **Replacement feasibility**: Replaced by PR-description Governor Footer + ADR Consequences (`ADR{NNN}-G{N}` slots). Existing entries are not migrated; they remain as historical context.
- **Final location**: unchanged. README.md banner declares the archive closed.
- **Migration risk**: None (frozen).
- **Stability impact**: Low (read-only enforcement only — language-policy provenance carve-out continues to apply for the existing entries).
- **Notes**: Append-only English errata under `Errata YYYY-MM-DD:` headings is the only allowed edit pattern for existing entries.

### `governor-paths.md`

- **Current role**: Canonical source for the governor-changing path list (Tier A / B / C plus exclusions). All consumer docs (AGENTS.md, target-operating-model.md, migration-strategy.md, drift-checklist.md, `.github/pull_request_template.md`) link this file rather than redeclare the list.
- **Why it exists**: Round-4 cross-tool review (R4.3) caught microscopic drift between the five copies of the path list. A single source removes the drift surface and prepares Phase 5's shared module to read the file directly.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Migration risk**: Low.
- **Stability impact**: High — every path-classification decision in Phase 2~5 hooks resolves to this file.
- **Notes**: Itself governor-changing. Editing it requires a PR with a `## Governor Footer` block (Governor Footer model per ADR 047 — `governor-review-log/` per-PR obligation retired).

### `.agents/shared/governor/` (Phase 5 / #124 — NEW)

- **Current role**: Shared governor *policy* package consumed by Claude/Codex/Antigravity hook adapters as a thin shim. Phase 5 snapshot — eight modules: `__init__.py` (public API + `__all__`), `paths.py` (REPO_ROOT discovery + GOVERNOR_PATHS_MD), `time_window.py` (single `_within_24h`), `tokens.py` (Phase 2 parser + EXPLORATION_TOKENS; #268 adds PLAN_WAIVER_TOKENS), `markers.py` (write_marker + read_latest_token + MarkerLifecycle enum + consume_phase2_markers per IC-11/IC-12), `safety.py` (HC-1 single-entry `safe_parse_exception_token` returning `Blocked | ParsedToken`), `verify.py` (Phase 3 REMINDER_TEXT + should_remind_claude), `completion_gate.py` (Phase 4 GateResult dataclass + evaluate_gate + render_reminder + parse_trigger_globs + match_log_entry). Later additions (see Update Log): `sync_cosmetic.py` (ADR 047), `stage_gate.py` (#268 / ADR 050 — GATED_STAGES allowlist, implementation-surface predicate, plan-waiver suppression, exclusive-create session markers), and Antigravity hook shims reusing the same package.
- **Why it exists**: Phase 4 retrospective surfaced `_within_24h` × 4, `_read_latest_token` × 4, `EXPLORATION_TOKENS` × 2, and reminder-text duplicates whose silent drift would risk governor incidents. Phase 5 (#124) consolidates them into a single Tier B `.agents/shared/governor/` package per ADR 045 / target-operating-model §5. Hooks become thin shims (commit 5).
- **Replacement feasibility**: None — this is the consolidation target itself.
- **Final location**: `.agents/shared/governor/`. `pyproject.toml` registers `[tool.pytest.ini_options].pythonpath = [".agents/shared"]` so tests import `governor.*` directly.
- **Migration risk**: Low. Behaviour-invariance proven by 202 unit tests (93 baseline + 109 added; Round 1 R-points added 2 stale/malformed marker scenarios) and three-tier fail-open coverage including the R0-A.1 invariant (importing a shim under `contextlib.suppress(Exception)` MUST NOT raise SystemExit).
- **Stability impact**: High. Single source of truth for governor policy; closes the inline-redeclaration loophole asserted by `test_governor_boundary.py`.
- **Notes**: Boundary contract (R0-C.3): this package owns *policy*; tool-specific runtime utilities (`.codex/hooks/_shared.py` git/subprocess helpers, Codex `session_id()` / verify-log writer / `cleanup_stale_verify_logs`) remain per-tool. `__all__` declared in `__init__.py` enforces stability — `test_governor_boundary.py::test_governor_all_does_not_drop_known_names` fails the build if a public name is removed without deliberate review.

### `tools/check_g_closure.py` (#145) — superseded and removed by ADR 047 PR (#159)

- **Current role**: Removed in PR #159 (ADR 047 PR B-F rollout). Was a mechanical checker for AGENTS.md guard G that scanned `docs/history/archive/governor-review-log/pr-*.md`.
- **Why it exists (historical)**: Issue #145 turned the reasoning-level G closure rule from text-only discipline into a local pre-commit / CI-enforced guard for governor review-log entries.
- **Replacement feasibility**: Replaced by `tools/check_governor_footer.py` which validates the PR-description `## Governor Footer` block (closure-label vocabulary preserved exactly: `Fixed` / `Deferred-with-rationale` / `Rejected` per Guard G — ADR047-G26).
- **Final location**: deleted.
- **Migration risk**: None (the closed archive is no longer churned, so a linter for it is no longer needed).
- **Stability impact**: None.
- **Notes**: The `governor-review-log-g-closure` pre-commit hook entry is also removed in PR #159. Test file `tests/unit/agents_shared/test_g_closure.py` is removed alongside the tool.

### `tools/check_governor_footer.py` (ADR 047 PR B) — NEW

- **Current role**: Mechanical checker for the PR-description `## Governor Footer` block (ADR 047 D2). Validates 10-field shape, enum vocabularies, integer types, ADR consequence ID grammar (`ADR{NNN}-G{N}`), and (with `--require-governor-footer`) enforces presence + `trigger: yes` + `rounds >= 1` for governor-changing PRs.
- **Why it exists**: Replaces `tools/check_g_closure.py` as the active closure-label / Guard G enforcement target after ADR 047 retires the per-PR `governor-review-log/` archive.
- **Replacement feasibility**: None. Repository-specific enforcement for the new Governor Footer shape; Markdown fenced examples in ADR 047 / PR template are deliberately ignored so the linter does not parse them as the real footer.
- **Final location**: `tools/check_governor_footer.py`.
- **Migration risk**: Low. Scope bounded to the PR description body (CI fetches via `gh pr view`). V1 does not validate ADR slot existence, count consistency with R-points, or reviewer vocabulary.
- **Stability impact**: High. Without it, removing `check_g_closure.py` would leave Guard G as text-only enforcement — codex design review flagged this as the single biggest risk of the ADR 047 rollout.
- **Notes**: Wired in CI via `.github/workflows/governor-footer-lint.yml` (event triggers `opened` / `synchronize` / `reopened` / `edited`; sticky comment on failure; `[skip-governor-footer]` token bypass — non-governor-changing PRs only; governor-changing use is a hard CI failure per ADR 048-G1). Regression-covered by `tests/unit/tools/test_governor_footer.py` (31 cases).

---

## Tier 2 — Skills (3-Layer Hybrid C)

Fifteen skills, each existing in three layers (`docs/ai/shared/skills/{name}.md` shared procedure + `.claude/skills/{name}/SKILL.md` wrapper + `.agents/skills/{name}/SKILL.md` wrapper). The bucket is assigned per skill (all three layers share the bucket); the matrix records the skill once.

Bucket guideline:
- Skills that scaffold or audit *project-specific architecture* (3-tier hybrid, optional infra DI, ADR 040/042/043 patterns) → **Keep**.
- Skills whose procedure is *generic process discipline* (planning, review, onboarding) → **Overlay**: the Default Flow routes work through them; their bodies remain.

| Skill | Bucket | Risk | Impact |
|---|---|---|---|
| `new-domain` | Keep | Low | High |
| `add-api` | Keep | Low | High |
| `add-worker-task` | Keep | Low | Medium |
| `add-admin-page` | Keep | Low | Medium |
| `add-cross-domain` | Keep | Low | Medium |
| `migrate-domain` | Keep | Low | Medium |
| `test-domain` | Keep | Low | High |
| `review-architecture` | Keep | Low | High |
| `security-review` | Keep | Low | High |
| `sync-guidelines` | Keep | Low | High |
| `plan-feature` | Overlay | Low | High |
| `execute-plan` | Overlay | Low | High |
| `review-pr` | Overlay | Low | High |
| `fix-bug` | Overlay | Low | Medium |
| `onboard` | Overlay | Low | Low |

### `new-domain` (Keep)

- **Current role**: Full domain scaffolding (15 content + 25 `__init__.py` + 4 tests = 44 files).
- **Why it exists**: Project's 3-tier hybrid architecture is too large to scaffold by hand.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: All 3 layers gain a "Default Flow Position" section locating the skill at `implement` step (post-`framing`/`approach`/`plan`); shared procedure adds Pre/Post-implementation routing notes.
- **Notes**: Carries the Optional AI Infra Variant pattern (ADR 042); examples-profile carve-out applies.

### `add-api` (Keep)

- **Current role**: Add an endpoint to an existing domain following bottom-up layering.
- **Why it exists**: Enforces DTO rules, base-service generics, router conventions per ADR 011/043.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `implement`. Shared procedure adds an explicit "verify with `/test-domain`" pointer.
- **Notes**: Most-used skill after `/plan-feature`.

### `add-worker-task` (Keep)

- **Current role**: Taskiq worker task scaffolding with explicit payload contract and thin task adapter.
- **Why it exists**: Broker abstraction (#8) requires a uniform pattern; payload-vs-business separation enforced.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `implement`.
- **Notes**: Codex-side `BROKER_TYPE` env-var rules apply; not affected by hook phases.

### `add-admin-page` (Keep)

- **Current role**: NiceGUI admin page scaffold with config / page split + sensitive-field masking.
- **Why it exists**: ADR 014 admin dashboard pattern; admin extra split (#104).
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `implement`.
- **Notes**: Requires `admin` extra installed; skill body documents fallback message when extra is absent.

### `add-cross-domain` (Keep)

- **Current role**: Wire one domain's data to another via Protocol-based DIP.
- **Why it exists**: Prevents direct cross-domain implementation imports (Absolute Prohibition).
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `implement` (after `approach options` for whether to introduce the dependency at all).
- **Notes**: Most likely to require `approach options` step because cross-domain dependencies are architecture commitments.

### `migrate-domain` (Keep)

- **Current role**: Alembic revision generation, application, downgrade, status.
- **Why it exists**: Migration safety guards (autogenerated revisions are review-required).
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `implement` and feeds into the `verify` step (must run `alembic upgrade head` against a clean DB).
- **Notes**: `disable-model-invocation: true` in skill frontmatter; manual user invocation only.

### `test-domain` (Keep)

- **Current role**: Generate or run tests for a domain. Surface for the `verify` step.
- **Why it exists**: Project-specific test patterns (factories, integration baseline, e2e).
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `verify`. Shared procedure becomes the canonical `verify`-step skill.
- **Notes**: Phase 3 verification-first hook will auto-suggest invocation when changed_files include source code.

### `review-architecture` (Keep)

- **Current role**: Audit a domain or the full repo for architecture compliance against the shared checklist.
- **Why it exists**: Catches Absolute Prohibition violations and ADR drift.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `self-review` (architecture commitments) and may be triggered before `completion gate`.
- **Notes**: Examples profile carve-out applies (relaxed §5 / §2).

### `security-review` (Keep)

- **Current role**: OWASP-aligned audit for a domain or file.
- **Why it exists**: Project-specific security stance.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `self-review` (security-sensitive surfaces).
- **Notes**: Trigger list lives in the shared procedure; not all changes invoke this.

### `sync-guidelines` (Keep)

- **Current role**: Drift management — code ↔ shared docs ↔ skill wrappers.
- **Why it exists**: Single closure step that reconciles all rule sources.
- **Replacement feasibility**: None.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `completion gate` follow-up. Adds drift detection for `harness-asset-matrix.md` ↔ filesystem.
- **Notes**: `disable-model-invocation: true`; user-explicit only. Critical for Phase 1 acceptance — must catch any 3-layer skill drift introduced this PR.

### `plan-feature` (Overlay)

- **Current role**: Feature planning with five phases (Requirements, Approach, Architecture, Security, Tasks). Phase 1 (Approach Options) was added in #115/#116 — the first philosophy port.
- **Why it exists**: Prevent omission-driven feature planning.
- **Replacement feasibility**: Partial. The skill itself remains; the Default Flow now invokes its phases as discrete steps (`framing`, `approach options`, `plan`).
- **Bucket: Overlay**. Skill body unchanged in essence; the entry-point shifts from "user invokes /plan-feature" to "Default Flow routes through it".
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position section + recursion guard ("do not invoke /plan-feature recursively from within /plan-feature").
- **Notes**: First skill where the philosophy port is most visible. Issue #257 extends the output contract with an Execution Packet consumed by `execute-plan`.

### `execute-plan` (Overlay)

- **Current role**: Native execution workflow for approved Execution Packets, routing complex / architecture-changing / governor-changing / multi-task work through task-by-task implementation, verification, review, and ledger updates.
- **Why it exists**: Absorbs the useful superpowers-style execution discipline into the local harness without adopting an external superpowers dependency.
- **Replacement feasibility**: Partial. The procedure is generic process discipline, but it depends on local skills, work-ledger state, Governor Footer policy, and project-specific review gates.
- **Bucket: Overlay**. Default Flow routes complex work through it after `plan-feature`; single-skill and trivial work continue through the existing lighter flow.
- **Final location**: new Hybrid C skill triple.
- **Issue #257 edit**: Adds shared procedure + Claude / Codex wrappers; records workflow state through `work_ledger.update_workflow_state`.
- **Notes**: Enforcement starts advisory-first; future hardening PRs may promote only high-confidence missing-plan / missing-review / pending-verification conditions to hard gates or CI checks.

### `review-pr` (Overlay)

- **Current role**: PR architecture quality-gate review with drift-candidate detection.
- **Why it exists**: Standardise PR-time architecture audits.
- **Replacement feasibility**: Partial. Activity becomes part of the `completion gate` step.
- **Bucket: Overlay**.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position = `completion gate`. Recursion guard.
- **Notes**: Phase 4 Stop hook will auto-suggest invocation once a commit-time gate is wired.

### `fix-bug` (Overlay)

- **Current role**: Reproduce → Trace → Fix → Verify 4-phase bug workflow.
- **Why it exists**: Prevent symptom-only fixes.
- **Replacement feasibility**: Partial. The four phases map naturally onto Default Flow's `framing`+`plan`+`implement`+`verify`.
- **Bucket: Overlay**. The skill body remains valuable for the Trace/Verify detail; entry-point shifts.
- **Final location**: unchanged.
- **Phase 1 edit**: Default Flow Position section explaining the 1:1 phase mapping.
- **Notes**: `[hotfix]` exception token is the natural escape for genuinely urgent bug-fix work.

### `onboard` (Overlay)

- **Current role**: Interactive onboarding (Welcome / Domains / Workflow / Assets / Next Steps).
- **Why it exists**: New-contributor structured introduction.
- **Replacement feasibility**: Full for the procedure; project intro must stay local.
- **Bucket: Overlay** — kept on disk, but Default Flow does not invoke it during normal coding.
- **Final location**: unchanged.
- **Phase 1 edit**: Add Default Flow Position section that clarifies "session-start only; not a coding-flow skill".
- **Notes**: Largest skill body (317 lines shared procedure); could be a future Drop candidate after a few revisions of usage data.

---

## Tier 3 — Hooks

Thirty-one hook scripts (9 Claude shell + 6 Claude Python implementations + 8 Codex Python + 8 Antigravity Python; the Claude count includes `.claude/hooks/session-start-context.sh`, an active SessionStart hook rowed during the #281 sync after a prior sync omitted it). Phase 2 (#121) added `.claude/hooks/user-prompt-submit.sh` + `.claude/hooks/user_prompt_submit.py` as the first Claude UserPromptSubmit hook surface; Phase 3 (#122) added `.claude/hooks/verify-first.{sh,py}` + `.codex/hooks/verify_first.py`; Phase 4 (#123) added `.claude/hooks/completion_gate.py` + `.codex/hooks/completion_gate.py` as the completion-gate helper pair (IC-11 Option A + Pillar 7); #268 (ADR 050) added `.claude/hooks/stage-gate.sh` + `.claude/hooks/post_tool_stage_gate.py` as the mid-task stage-gate advisory pair (third `PostToolUse Edit|Write` sibling); #269 shipped the Codex counterpart as a Stop-time advisory folded into `.codex/hooks/stop-sync-reminder.py` (no new hook file — Codex fires one Stop event), reusing the shared `governor.stage_gate` policy; #281 (ADR 054) added `.claude/hooks/pre-tool-stage-block.sh` + `.claude/hooks/pre_tool_stage_block.py` as the plan→execute boundary **hard block** (a new `PreToolUse Edit|Write` sibling, exit 2), with the Codex counterpart folded into `.codex/hooks/stop-sync-reminder.py` as a Stop-time advisory (`plan_execute_segment`, no new hook file). The Antigravity adapter wires Gemini / Antigravity events through `.gemini/settings.json` to `.antigravity/hooks/`, reusing the same shared governor policy with runtime state isolated under `.antigravity/state/`.

| Asset | Bucket | Risk | Impact |
|---|---|---|---|
| `.claude/hooks/check-required-plugins.sh` | Keep | Low | Low |
| `.claude/hooks/session-start-context.sh` | Keep | Low | Low |
| `.claude/hooks/pre-tool-security.sh` | Keep | Low | Medium |
| `.claude/hooks/post-tool-format.sh` | Keep | Low | Medium |
| `.claude/hooks/stop-sync-reminder.sh` | Keep | Low | Medium |
| `.claude/hooks/user-prompt-submit.sh` | Keep | Low | Medium |
| `.claude/hooks/verify-first.sh` | Overlay | Low | Low |
| `.claude/hooks/stage-gate.sh` | Overlay | Low | Low |
| `.claude/hooks/pre-tool-stage-block.sh` | Overlay | Low | Low |
| `.claude/hooks/pre_tool_security.py` | Keep | Low | Medium |
| `.claude/hooks/user_prompt_submit.py` | Keep | Low | Medium |
| `.claude/hooks/verify_first.py` | Overlay | Low | Low |
| `.claude/hooks/completion_gate.py` | Overlay | Low | Low |
| `.claude/hooks/post_tool_stage_gate.py` | Overlay | Low | Low |
| `.claude/hooks/pre_tool_stage_block.py` | Overlay | Low | Low |
| `.codex/hooks/_shared.py` | Keep | Low | Low |
| `.codex/hooks/session-start.py` | Keep | Low | Low |
| `.codex/hooks/user-prompt-submit.py` | Keep | Low | Medium |
| `.codex/hooks/pre-tool-security.py` | Keep | Low | Medium |
| `.codex/hooks/post-tool-format.py` | Keep | Low | Medium |
| `.codex/hooks/stop-sync-reminder.py` | Keep | Low | Medium |
| `.codex/hooks/verify_first.py` | Overlay | Low | Low |
| `.codex/hooks/completion_gate.py` | Overlay | Low | Low |
| `.antigravity/hooks/_shared.py` | Keep | Low | Low |
| `.antigravity/hooks/session-start.py` | Keep | Low | Low |
| `.antigravity/hooks/user-prompt-submit.py` | Keep | Medium | Medium |
| `.antigravity/hooks/pre-tool-security.py` | Keep | Medium | Medium |
| `.antigravity/hooks/post-tool-format.py` | Keep | Medium | Medium |
| `.antigravity/hooks/verify_first.py` | Overlay | Medium | Low |
| `.antigravity/hooks/completion_gate.py` | Overlay | Medium | Low |
| `.antigravity/hooks/stop-sync-reminder.py` | Overlay | Medium | Medium |

### `.claude/hooks/check-required-plugins.sh`

- **Current role**: SessionStart guard that ensures `pyright-lsp` is enabled.
- **Why it exists**: #63 plugin migration; missing plugins silently break LSP-aware skills.
- **Bucket**: Keep.
- **Notes**: No Default Flow interaction.

### `.claude/hooks/session-start-context.sh`

- **Current role**: SessionStart hook that injects project status/context (via `.agents/shared` state) into the session at startup.
- **Why it exists**: Surfaces the resumed work-ledger goal/scope/stage and environment notes at session start so the agent has current project context without an explicit read.
- **Bucket**: Keep.
- **Notes**: Rowed during the #281 / ADR 054 sync — this active SessionStart hook (wired in `.claude/settings.json`) had been omitted from the matrix by a prior sync. No Default Flow interaction.

### `.claude/hooks/pre-tool-security.sh`

- **Current role**: PreToolUse on Edit / Write / Bash; static checks against destructive commands and architecture violations.
- **Why it exists**: Safety gate in the precedence layer (D1.3).
- **Bucket**: Keep.
- **Notes**: Default Flow ranks **below** this hook; escape tokens cannot bypass it.

### `.claude/hooks/post-tool-format.sh`

- **Current role**: PostToolUse on Edit / Write; runs `ruff format` + `ruff check --fix` on `.py` files.
- **Why it exists**: Format consistency without manual invocation.
- **Bucket**: Keep.
- **Notes**: Phase 3 (#122) verification-first hook (`.claude/hooks/verify-first.sh`) and #268 (ADR 050) stage-gate hook (`.claude/hooks/stage-gate.sh`) live in the *same* `PostToolUse Edit|Write` matcher block as siblings, not separate matchers. SoC: this hook mutates files (ruff); verify-first and stage-gate are advisory only — since #271 verify-first emits model-visible `hookSpecificOutput.additionalContext` JSON on stdout (exit 0), never blocking.

### `.claude/hooks/stop-sync-reminder.sh`

- **Current role**: Stop hook reminding the user to run `/sync-guidelines` if shared rule sources changed. AGENT_LOCALE (#133) resolves advisory header/footer strings through `.agents/shared/harness-python.sh -m governor.locale KEY`.
- **Why it exists**: Drift management closure.
- **Bucket**: Keep.
- **Notes**: Phase 4 (#123) completion-gate output (`COMPLETION_OUT`) is captured and merged after the sync-advisory block (HC-4.1 non-blocking; printed only when `CHANGED` is non-empty). IC-11 Option A requires `COMPLETION_OUT` to be computed before the early-exit guard so markers are consumed on every Stop regardless of file changes.

### `.claude/hooks/pre_tool_security.py`

- **Current role**: Python implementation of pre-tool security checks. The `.sh` wrapper at `.claude/hooks/pre-tool-security.sh` reads stdin and pipes to this `.py` module through `.agents/shared/harness-python.sh`.
- **Why it exists**: Cleaner separation between hook contract (the `.sh` matched against `.claude/settings.json` matchers) and security-check logic (the `.py` module). Mirrors `.codex/hooks/_shared.py` + `.codex/hooks/pre-tool-security.py` separation on the Codex side.
- **Bucket**: Keep.
- **Migration risk**: Low.
- **Notes**: Earlier draft of this matrix (initial Phase 1 pass) misclassified this as Drop. Self-verification during cross-link work caught the misclassification: `.claude/hooks/pre-tool-security.sh` invokes `.claude/hooks/pre_tool_security.py` via the shared launcher. The two files are an active pair, not duplication.

### `.codex/hooks/_shared.py`

- **Current role**: Shared utility for Codex hook scripts (logging / config / colorised output).
- **Bucket**: Keep.
- **Notes**: Phase 5 shared governor module may absorb part of this; the file itself remains during Phases 1~4.

### `.codex/hooks/session-start.py`

- **Current role**: SessionStart message announcing Codex repo harness.
- **Bucket**: Keep.
- **Notes**: Phase 2 extension may inject a Default Flow reminder banner here.

### `.codex/hooks/user-prompt-submit.py`

- **Current role**: Phase 5 (#124) thin shim. HC-1 ordering (`safety-block-first → parser-second`) is now enforced inside `.agents/shared/governor/safety.py::safe_parse_exception_token`, a single-entry function returning `Blocked | ParsedToken`. The shim cannot reach the parser past a destructive-prompt block (R0-C.1 — callable-injection rejected as bypass-prone).
- **Bucket**: Keep — Phase 5 consolidation preserves behaviour byte-identically.
- **Notes**: Codex R3 / IC-1 still hold: exception-token recognition never overrides safety / sandbox / Absolute Prohibitions. Marker file location: `.codex/state/exception-token-{ts}-{seq}.json` (gitignored). Phase 5 invariant: no top-level `sys.exit` (R0-A.1). HC-1 unit-test coverage: `test_safe_parse_does_not_invoke_parser_when_blocked`.

### `.claude/hooks/user-prompt-submit.sh`

- **Current role**: Phase 2 (#121) UserPromptSubmit wrapper. Mirrors `pre-tool-security.sh` shape — pipes stdin to the Python helper. Informational only, exits 0.
- **Why it exists**: Claude did not have a UserPromptSubmit hook before Phase 2; this PR adds the surface so the exception-token vocabulary defined in PR #125 becomes machine-readable on the Claude side.
- **Bucket**: Keep.
- **Notes**: Mirrored against Codex `.codex/hooks/user-prompt-submit.py` for Phase 5 consolidation under `.agents/shared/governor/`.

### `.claude/hooks/user_prompt_submit.py`

- **Current role**: Phase 5 (#124) thin shim — the parser body now lives in `.agents/shared/governor/tokens.py`. This file imports `parse_exception_token` and `write_marker` from the shared module, exposes them as module attributes (back-compat for tests that monkeypatch `STATE_DIR`), and orchestrates stdin/stderr.
- **Why it exists**: Sh wrapper + py helper split + Phase 5 consolidation. Avoids shell-escaping NFKC + regex inline.
- **Bucket**: Keep.
- **Notes**: Phase 5 invariant: no top-level `sys.exit` / `raise SystemExit` (R0-A.1). Output identical to Codex side because both shims import the same shared helper. Parity asserted by `tests/unit/agents_shared/test_token_parser.py` and `test_shared_module_parity.py`.

### `.claude/hooks/verify-first.sh`

- **Current role**: Phase 3 (#122) PostToolUse `Edit|Write` sibling wrapper. Pipes stdin to `verify_first.py`; always exits 0 (HC-3.3 informational only).
- **Why it exists**: New SoC surface — formatting (`post-tool-format.sh`) is mutating; verify-first is advisory. Mixing them in one script complicates failure modes.
- **Bucket**: Overlay.
- **Notes**: Mirrors the `pre-tool-security.sh` + `pre_tool_security.py` shape. Phase 5 (#124) consolidates with `.codex/hooks/verify_first.py` into `.agents/shared/governor/`.

### `.claude/hooks/verify_first.py`

- **Current role**: Phase 5 (#124) thin shim — the verify-first decision body now lives in `.agents/shared/governor/verify.py`. The shim imports `REMINDER_TEXT`, `is_python_source`, `extract_file_path`, and the marker reader, then exposes `read_latest_token_marker` (READ_ONLY lifecycle wrapper) and `should_remind` for the existing test surface.
- **Why it exists**: Reminds the user that the Default Coding Flow `verify` step is missing for the changed Python file. Read-only on Phase 2 markers (IC-11 — verify-first reads with `MarkerLifecycle.READ_ONLY`; Phase 4 #123 owns lifecycle).
- **Bucket**: Overlay.
- **Notes**: `REMINDER_TEXT` is now a single shared constant — string-equality is intrinsic, not asserted. Phase 5 invariant: no top-level `sys.exit` (R0-A.1). Fail-open on every error path (HC-3.6 / HC-5.5). Emit channel (#271, ADR 050 D3 drift-candidate remediation): `hookSpecificOutput.additionalContext` JSON on stdout with exit 0 — the model-visible non-blocking PostToolUse channel; plain stderr on exit 0 reached only the user transcript, so the pre-#271 reminder never influenced the agent. Codex side is unaffected by design: its reminder is delivered by the Stop hook's `systemMessage`, which targets the user after the turn has ended.

### `.claude/hooks/stage-gate.sh`

- **Current role**: #268 (ADR 050) PostToolUse `Edit|Write` third sibling wrapper. Pipes stdin to `post_tool_stage_gate.py`; always exits 0 (ADR050-G1 advisory only).
- **Why it exists**: Mid-task scope-expansion gate — the Default Coding Flow was prompt-scoped, so capability gaps discovered mid-execution entered implementation with no plan. This wrapper delivers the runtime nudge.
- **Bucket**: Overlay.
- **Notes**: Mirrors the `verify-first.sh` + `verify_first.py` shape. #269 shipped the Codex counterpart as a Stop-time advisory in `.codex/hooks/stop-sync-reminder.py` (no PostToolUse on the Codex side — it folds into the existing Stop hook rather than adding a sibling).

### `.claude/hooks/post_tool_stage_gate.py`

- **Current role**: Thin shim over `.agents/shared/governor/stage_gate.py`. Emits the stage-gate advisory as `hookSpecificOutput.additionalContext` JSON on stdout with exit 0 — the documented model-visible non-blocking PostToolUse channel (ADR 050 D3).
- **Why it exists**: Fires once per session when a `.py` under `src/`/`examples/` is edited while the work ledger's `workflow.stage` is `idle`/`complete`/`blocked` and no plan-waiver token marker is active. Fail-open on missing/corrupt ledger (`.agents/state/` is untracked, so contributors and CI never see it).
- **Bucket**: Overlay.
- **Notes**: Exclusive-create session marker (`stage-gate-<session_id>.json`) — only the claim winner emits (R1.3). Locale key `STAGE_GATE_REMINDER` resolved at emit time (#133 pattern). Phase 5 invariants: no top-level `sys.exit` (R0-A.1), HC-5.5 fail-open. ADR 050 D3 records the drift candidate that `verify_first.py` still emits transcript-only stderr.

### `.claude/hooks/pre-tool-stage-block.sh`

- **Current role**: #281 (ADR 054) `PreToolUse Edit|Write` wrapper for the plan→execute hard block. Pipes stdin to `pre_tool_stage_block.py` and **propagates its exit code** (unlike `stage-gate.sh`, which always exits 0) so exit 2 blocks the edit. Guards a missing/unreadable script or launcher with `|| exit 0` so the interpreter's own exit 2 cannot masquerade as a block (fail-open, ADR054-G5).
- **Why it exists**: The ADR 050 advisory stays silent on `workflow.stage == "planned"` (an approved plan not yet handed to `/execute-plan`) — the exact window ADR 054 hard-blocks so an approved plan cannot slide into implementation without an explicit `/execute-plan`.
- **Bucket**: Overlay.
- **Notes**: Second Claude `PreToolUse Edit|Write` hook (after `pre-tool-security.sh`); wired as a distinct matcher entry in `.claude/settings.json`. Codex has no `PreToolUse`, so its counterpart is the Stop-time advisory `plan_execute_segment` in `.codex/hooks/stop-sync-reminder.py` (ADR054-G4 asymmetry — Claude blocks, Codex advises).

### `.claude/hooks/pre_tool_stage_block.py`

- **Current role**: Thin shim over `governor.stage_gate.should_block_plan_execute_edit`. Blocks the edit with exit 2 + `[BLOCKED]` stderr (the model-visible `PreToolUse` channel `pre_tool_security.py` uses) when a `.py` under `src/`/`examples/` is edited while `workflow.stage == "planned"` and no plan-waiver token (`[trivial]`/`[hotfix]`) is active.
- **Why it exists**: Enforces the plan→execute boundary on Claude (ADR054-G1). Unlike the ADR 050 advisory it has **no once-per-session dedup** — a block must hold on every retry until `/execute-plan` advances the stage to `executing`. There is deliberately no Claude `PostToolUse` advisory for `planned` (the block intercepts the same cases pre-edit — ADR 054 D4).
- **Bucket**: Overlay.
- **Notes**: Reuses the `governor.stage_gate` policy + `PLAN_EXECUTE_GATED_STAGES = {planned}` (disjoint from the ADR 050 `GATED_STAGES`). Locale key `PLAN_EXECUTE_REMINDER` resolved at emit time (#133 pattern), imported never inlined (ADR050-G4). Phase 5 invariants: no top-level `sys.exit` outside `__main__`; HC-5.5 / ADR054-G5 fail-open (any error → exit 0, never fail-closed).

### `.codex/hooks/pre-tool-security.py`

- **Current role**: PreToolUse Bash matcher; checks destructive commands, SQL injection patterns, secret leakage.
- **Bucket**: Keep.
- **Notes**: Codex R7 — Default Flow does not weaken any prefix_rule decision (`forbidden`/`prompt`).

### `.codex/hooks/post-tool-format.py`

- **Current role**: PostToolUse Bash matcher. Two responsibilities: (1) runs ruff after a Bash invocation that touched Python files; (2) Phase 3 (#122) — records verify-class commands (`pytest`, `make test`, `make demo[-rag]`, `alembic upgrade`) to `.codex/state/verify-log-{session}.json` so the Stop hook can detect whether verify happened in this session.
- **Bucket**: Keep — but Codex R7 is critical: this hook **does not see** edits that bypass Bash (e.g. `apply_patch`). Phase 3 verification-first reminder relies on Stop-side change detection for Codex (`.codex/hooks/stop-sync-reminder.py` extension), not on extending this hook to emit reminders.
- **Notes**: Largest Codex-side blind spot identified during Phase 0.5 review. Phase 3 R0.4 wraps the file in a top-level fail-open so invalid stdin / ruff-missing / verify-log writer failures all return exit 0.

### `.codex/hooks/stop-sync-reminder.py`

- **Current role**: Stop hook with six responsibilities merged into a single `{"systemMessage": "..."}` JSON output via `build_segments` orchestrator (AGENT_LOCALE #133 / PR #134, IC-2): (1) sync-advisory for governor-path drift; (2) Phase 3 (#122) verify-first via `verify_first.should_remind()`; (3) Phase 4 (#123) completion-gate via `completion_gate` module; (4) Phase 2 exception-token marker consumption (`consume_phase2_markers` — IC-11 Option A); (5) stale verify-log cleanup; (6) #269 (ADR 050) mid-task stage-gate advisory via `stage_gate_segment`, evaluated *before* (4) so the shared `should_stage_gate` policy can read the exception-token (plan-waiver) markers that consumption deletes. AGENT_LOCALE env resolves locale for segments 1, 3, and 6 at startup.
- **Bucket**: Keep.
- **Notes**: `build_segments` is a pure function (testable without subprocess); so is the stage-gate decision `stage_gate_segment`. Phase 4 completion-gate is the third segment (Codex R2). Phase 5 thin-shims for `verify_first` and `completion_gate` are imported inline. Phase 3 R0.1: import inside try-block so ImportError leaves sync-advisory intact (HC-3.6 fail-open). The marker-consumption (4) and verify-log-cleanup (5) side effects are unconditional — no early-exit guard skips them; the stage-gate advisory (6, #269) is conditional (appends only when the gate fires and the shared `mark_fired` exclusive-create claim wins).

### `.codex/hooks/verify_first.py`

- **Current role**: Phase 5 (#124) thin shim — verify-first *policy* (REMINDER_TEXT, marker reader) imported from `.agents/shared/governor/verify.py`. Codex-only runtime adapters retained: `session_id()`, `verify_log_path`, `append_verify_log`, `current_session_latest_verify_ns`, `changed_python_files`, `max_changed_py_mtime_ns`, `should_remind` (Codex-specific verify-log freshness logic).
- **Why it exists**: Codex side cannot trigger reminders on `PostToolUse Bash` because `apply_patch` is invisible there (IC-5). Detection happens at Stop time using `_shared.changed_files()` + per-session verify-log freshness check. The session-tracking machinery is intrinsically Codex-only (depends on `CODEX_THREAD_ID`).
- **Bucket**: Overlay.
- **Notes**: `REMINDER_TEXT` is now imported from the shared module — string-equality is intrinsic. `session_id()` priority: `CODEX_THREAD_ID` (Codex CLI injects this into all hook processes in a session) → `CODEX_SESSION_ID` (fallback alias) → `f"{ppid}-{pid}-{start_ns:016x}"` (non-Codex environments). Verify-log entries store `ts_epoch_ns` for subsecond freshness comparison against `Path.stat().st_mtime_ns`. Phase 5 invariant: no top-level `sys.exit` (R0-A.1).

### `.claude/hooks/completion_gate.py`

- **Current role**: Phase 5 (#124) thin shim. Pillar 7 logic (governor-paths matching, log-entry classification, reminder rendering) imported from `.agents/shared/governor/completion_gate.py`; IC-11 Option A lifecycle imported from `.agents/shared/governor/markers.py::consume_phase2_markers`. The shim manually orchestrates `_changed_files`, `_read_latest_token`, and `pr_number_from_branch` so the existing test suite's monkeypatches keep working.
- **Why it exists**: Phase 4 completion-gate check. Phase 5 consolidation preserves behaviour byte-identically while collapsing the duplicate per-tool implementations.
- **Bucket**: Overlay.
- **Notes**: `GOVERNOR_REMINDER_WITH_PR` / `GOVERNOR_REMINDER_NO_PR` are imported from the shared module — string-equality is intrinsic, no longer asserted via cross-file scrape (R0-C.3). Fail-open per HC-4.7 / HC-5.5. `_within_24h` filter retained inside `read_latest_token`. Phase 5 invariant: no top-level `sys.exit` (R0-A.1).

### `.codex/hooks/completion_gate.py`

- **Current role**: Phase 5 (#124) thin shim. Pillar 7 logic imported from `.agents/shared/governor/completion_gate.py`; IC-11 Option A lifecycle imported from `.agents/shared/governor/markers.py`. `cleanup_stale_verify_logs` retained as Codex-only runtime adapter because it depends on `verify_first.session_id()` to know which verify-log file belongs to the current session.
- **Why it exists**: Phase 4 completion-gate check. Codex side keeps the cleanup helper because session lifecycle is intrinsically Codex-only.
- **Bucket**: Overlay.
- **Notes**: `GOVERNOR_REMINDER_*` imported from shared module. `cleanup_stale_verify_logs` preserves current session's log; only prunes other sessions' 24h-old files. Fail-open per HC-4.7 / HC-5.5. Phase 5 invariant: no top-level `sys.exit` (R0-A.1).

---

## Tier 4 — Rule Files

Seven rule files (5 Claude + 1 Codex + 1 Antigravity). All `Keep` except `commands.md` which becomes `Overlay` because Default Flow rerouting changes its primary use.

| Asset | Bucket | Risk | Impact |
|---|---|---|---|
| `.claude/rules/absolute-prohibitions.md` | Keep | Low | High |
| `.claude/rules/project-overview.md` | Keep | Low | Medium |
| `.claude/rules/project-status.md` | Keep | Low | Medium |
| `.claude/rules/architecture-conventions.md` | Keep | Low | High |
| `.claude/rules/commands.md` | Overlay | Low | Low |
| `.codex/rules/fastapi-agent-blueprint.rules` | Keep | Low | Medium |
| `.antigravity/rules/project-harness.md` | Keep | Low | Medium |

### `.claude/rules/absolute-prohibitions.md`

- **Current role**: Auto-loaded projection of `AGENTS.md § Absolute Prohibitions` for Claude.
- **Bucket**: Keep.
- **Notes**: Default Flow precedence (D1.4) makes Absolute Prohibitions canonical above Default Flow. No edit needed.

### `.claude/rules/project-overview.md`

- **Current role**: Project purpose, app entry-points, dependency direction, infra options, Settings validation, key VOs.
- **Bucket**: Keep.
- **Notes**: Periodic `/sync-guidelines` snapshot.

### `.claude/rules/project-status.md`

- **Current role**: Latest release notes, active domains, recent ADRs, status of "not yet implemented" features.
- **Bucket**: Keep.
- **Notes**: Phase 1 update will record ADR 045 and Default Flow adoption in the Recent Major Changes table.

### `.claude/rules/architecture-conventions.md`

- **Current role**: Structural data-flow + base-class generics + selectors + storage / embedding / LLM choices + structured logging + object roles.
- **Bucket**: Keep.
- **Notes**: Phase 1 edit adds a small "Default Flow" cross-link in the Quality Gate Flow vicinity (no structural change).

### `.claude/rules/commands.md` (Overlay)

- **Current role**: Quick-reference shell commands.
- **Why it exists**: Reduce trial-and-error cost during routine tasks.
- **Replacement feasibility**: Partial. Default Flow steps will reference these commands; the file becomes a *consulted* reference rather than an entry point.
- **Bucket**: Overlay.
- **Phase 1 edit**: Add "Default Flow" pointer near the top.
- **Notes**: Most assets in this bucket are reference rather than process; this is the only Tier 4 example.

### `.codex/rules/fastapi-agent-blueprint.rules`

- **Current role**: Codex prefix rules: forbidden (`git reset --hard`, `git checkout --`, `rm -rf`) + prompt-required (`git push`, `alembic downgrade`).
- **Bucket**: Keep.
- **Phase 1 edit (Codex R6)**: `git push` justification updated to mention "Default Coding Flow verification and self-review steps".
- **Notes**: Default Flow ranks below this file (D1.2). Escape tokens never lift a prefix rule.

### `.antigravity/rules/project-harness.md`

- **Current role**: Antigravity adapter rule file pointing back to `AGENTS.md`, `.agents/skills/`, and `.agents/shared/governor/`.
- **Bucket**: Keep.
- **Notes**: The file deliberately avoids duplicating project architecture rules; it exists to keep Antigravity plugin discovery aligned with the shared source of truth.

---

## Bucket Distribution Summary

| Bucket | Count | Share | Notes |
|---|---|---|---|
| Keep | 66 | ~75% | Project-specific architecture / safety / reference value (incl. admin-design-system.md #193 + 4 design + 3 self-coherence-recovery process-governor artefacts + 2 Phase 2 #121 hooks + `session-start-context.sh` rowed in the #281 sync + Antigravity config assets + Phase 5 #124 shared governor package now extended by ADR 047 PR B-F with `sync_cosmetic.py`; ADR 047 PR B-F also added `tools/check_governor_footer.py` + `.github/workflows/governor-footer-lint.yml` in place of the removed `tools/check_g_closure.py`) |
| Overlay | 21 | ~24% | Process discipline now routed by Default Flow (issue #268 adds the 2 stage-gate hooks; issue #281 / ADR 054 adds the 2 plan→execute block hooks; issue #257 adds `execute-plan`; Phase 3 #122 adds 3 verify-first; Phase 4 #123 adds 2 completion-gate hooks; the Antigravity verify-first / completion-gate / stop advisory shims add 3 Overlay assets; Phase 5 #124 reduces those hooks to thin shims without changing buckets) |
| Replace | 0 | 0% | None in initial inventory; reserved for future passes |
| Drop | 1 | ~1% | `tools/check_g_closure.py` retired by ADR 047 PR B-F (Guard G enforcement target moved to PR-description Governor Footer; `tools/check_governor_footer.py` is the replacement and is counted under `Keep`). |
| **Total** | **88** | 100% | |

Counting note: `Tier 0=14` (tool entry points and top-level governance files), `Tier 1=22` (13 reference incl. `admin-design-system.md` + 3 design living docs + `governor-review-log/` directory + `governor-paths.md` + `.agents/shared/governor/` package + `tools/check_g_closure.py` historical-Drop + `tools/check_governor_footer.py` + `docs/history/047-governor-review-provenance-consolidation.md`), `Tier 2=15` (skill rows; each row covers all 3 wrapper layers), `Tier 3=31` (#281 / ADR 054 added `.claude/hooks/pre-tool-stage-block.sh` + `.claude/hooks/pre_tool_stage_block.py` and rowed the previously-omitted `.claude/hooks/session-start-context.sh`; #268 added `.claude/hooks/stage-gate.sh` + `.claude/hooks/post_tool_stage_gate.py`; #269 folded Codex stage-gate into the existing Stop hook; Antigravity adds 8 Python hook shims; Phase 4 #123 = 18, Phase 3 = 16, Phase 2 = 13, Phase 1 = 10; Phase 5 #124 converted 6 of these to thin shims without changing the count), `Tier 4=7` — sum 89. The 88 figure above excludes `.claude/settings.local.json` from the active-share count because it is `.gitignore`d. The bucket-share percentages use 88 as the denominator. (Tier 1 has 22 quick-table rows — 18 Keep, 3 Overlay, 1 Drop; a prior sync labelled this tier 21 and recorded base Keep as 54, undercounting the total by one Keep row — corrected here.)

This distribution matches the "Mostly Local with Philosophy Overlay" model declared in [ADR 045 §D4](../../history/045-hybrid-harness-target-architecture.md). The `Replace` and `Drop` columns are both empty: no asset's content is being rewritten, and self-verification during cross-link work showed that the only `Drop` candidate identified during the first triage was actually an active component (a sh-wrapper `.py` pair).

If a future `Replace` candidate emerges, the threshold is: Keep+Overlay would otherwise force the asset into structural inconsistency with the Default Flow. None of the current 88 active assets meet that.

## Verification

The following self-checks must pass before this matrix is treated as authoritative.

- [ ] Every asset on the filesystem appears in this matrix exactly once. Verify via:
  ```bash
  # Tier 0
  ls AGENTS.md CLAUDE.md .codex/config.toml .codex/hooks.json \
     .claude/settings.json .claude/settings.local.json .gemini/settings.json \
     .antigravity/plugin.json .antigravity/gemini-extension.json \
     .antigravity/mcp_config.json .antigravity/permissions.json .mcp.json
  # Tier 1
  ls docs/ai/shared/*.md
  ls tools/check_governor_footer.py
  # Tier 2 (3 layers per skill)
  ls docs/ai/shared/skills/*.md .claude/skills/*/SKILL.md .agents/skills/*/SKILL.md
  # Tier 3 (exclude gitignored caches such as __pycache__/*.pyc)
  find .claude/hooks .codex/hooks .antigravity/hooks -type f \
    ! -path '*/__pycache__/*' ! -name '*.pyc'
  # Tier 4
  ls .claude/rules/*.md .codex/rules/* .antigravity/rules/*.md
  ```
- [ ] Every skill has a consistent bucket across its three wrapper layers (Phase 1 update preserves this invariant).
- [ ] No asset is classified `Replace` while other Phase 1 work treats it as `Keep`.
- [ ] Any `Drop` candidate has been verified to have zero callers (`rg <name> .claude/ .codex/ .antigravity/ .gemini/`). Self-verification during cross-link work overturned the only initial Drop candidate; the principle remains: a Drop classification requires positive evidence of zero callers.
- [ ] Bucket-share ratio matches §Bucket Distribution Summary (~75% Keep / ~24% Overlay / 0% Replace / ~1% Drop) within ±10%.

## Update Log

- 2026-04-26 — Initial inventory under ADR 045 / Phase 1.
- 2026-04-26 — Phase 2 (#121): added `.claude/hooks/user-prompt-submit.sh` + `.claude/hooks/user_prompt_submit.py` to Tier 3; updated `.codex/hooks/user-prompt-submit.py` role to include exception-token parsing (behaviour-preserving). Total 56 → 58.
- 2026-04-27 — Phase 3 (#122): added `.claude/hooks/verify-first.{sh,py}` (sibling in existing `PostToolUse Edit|Write` matcher) + `.codex/hooks/verify_first.py` library to Tier 3; extended `.codex/hooks/post-tool-format.py` with verify-class command logger and top-level fail-open (R0.4); extended `.codex/hooks/stop-sync-reminder.py` to merge a verify-first segment (import inside try-block per R0.1). Total 58 → 61. Bucket-share shifted Keep 86% → 82% / Overlay 14% → 18%.
- 2026-04-27 — Phase 4 (#123): added `.claude/hooks/completion_gate.py` + `.codex/hooks/completion_gate.py` to Tier 3 (completion-gate Stop adapter, Pillar 7 + IC-11 Option A). Total 61 → 63. Bucket-share shifted Keep 82% → 79% / Overlay 18% → 21% as both new hooks classify as Overlay.
- 2026-04-27 — Phase 5 (#124): added `.agents/shared/governor/` package to Tier 1 (8 modules consolidating Phase 2~4 duplicates: paths / time_window / tokens / markers / safety / verify / completion_gate / `__init__`). Updated Tier 3 hook role descriptions for the 6 hooks now operating as thin shims (`.claude/hooks/{user_prompt_submit,verify_first,completion_gate}.py` + `.codex/hooks/{user-prompt-submit,verify_first,completion_gate}.py`). Total 63 → 64. Bucket-share Keep 79% → 80% (1 net Keep added) / Overlay 21% → 20%. Closes #117 "Hybrid Harness v1" milestone — escape token vocabulary and hybrid governance remain permanent (target-operating-model §3 / §7).
- 2026-04-29 — #145: added `tools/check_g_closure.py` to Tier 1 as the mechanical AGENTS.md guard G closure-table checker for governor review-log entries. Total 64 → 65. Bucket-share remains ~80% Keep / ~20% Overlay.
- 2026-04-29 — `/sync-guidelines` table parity pass: added `.claude/hooks/completion_gate.py` and `.codex/hooks/completion_gate.py` to the Tier 3 quick-reference table. Detail sections and counts were already present from Phase 4, so there is no count change.
- 2026-05-02 — ADR 047 PR B-F (#159): `tools/check_g_closure.py` retired (Drop); `tools/check_governor_footer.py` + `.github/workflows/governor-footer-lint.yml` added; `docs/history/047-governor-review-provenance-consolidation.md` added to Tier 1; `.agents/shared/governor/sync_cosmetic.py` added to Phase 5 package. `governor-review-log/` relocated to `docs/history/archive/governor-review-log/` (PR #161). Bucket-share ~79% Keep / ~20% Overlay / ~1% Drop.
- 2026-05-06 — PR-B.2: LOC corrections (project-dna.md 906→976, scaffolding-layers.md 295→299, ai-infrastructure-overview.md 117→162, drift-checklist.md 189→220, test-files.md 27→33); governor-paths.md Notes updated to reference Governor Footer model (ADR 047, `governor-review-log/` per-PR obligation retired); stop-sync-reminder.sh Notes updated past-tense for Phase 4 + IC-11 Option A; stop-sync-reminder.py role description refreshed for AGENT_LOCALE 5-responsibility orchestrator (#133).
- 2026-06-02 — #193: added `docs/ai/shared/admin-design-system.md` (Tier 1, Keep) — the admin design-system guide (tokens + component builders + conventions) backing the `/add-admin-page` skill. Total 66 → 67 (Keep 52 → 53); Tier 1 20 → 21. Bucket-share remains ~79% Keep / ~20% Overlay.
- 2026-06-29 — #257: added the `execute-plan` skill triple (Tier 2, Overlay) — native execution workflow consuming plan-feature Execution Packets; work-ledger schema v2 (workflow stage / tasks / review) + advisory-only Stop/SessionStart workflow signals. Total 67 → 68 (Tier 2 14 → 15; Overlay 13 → 14). Bucket-share ~79% Keep / ~21% Overlay.
- 2026-07-03 — #268 (ADR 050): added `.claude/hooks/stage-gate.sh` + `.claude/hooks/post_tool_stage_gate.py` to Tier 3 (mid-task stage-gate advisory, third `PostToolUse Edit|Write` sibling, both Overlay); added `stage_gate.py` to the `.agents/shared/governor/` package (Tier 1 package row unchanged — counted as one asset) and `PLAN_WAIVER_TOKENS` to `tokens.py`; locale key `STAGE_GATE_REMINDER` (EN+KO). Codex counterpart deferred to #269. Total 68 → 70 (Tier 3 18 → 20; Overlay 14 → 16). Bucket-share ~76% Keep / ~23% Overlay.
- 2026-07-04 — #269 (ADR 050): shipped the Codex stage-gate adapter as a Stop-time advisory folded into `.codex/hooks/stop-sync-reminder.py` (`stage_gate_segment`, sixth responsibility, evaluated before Phase 2 marker consumption) — no new hook file (Codex fires one Stop event), reuses the shared `governor.stage_gate` policy unchanged (adapter-only). Flipped the Tier 3 header + `stage-gate.sh` Notes deferred→shipped and the stop-sync-reminder.py role from five to six responsibilities. No asset count change (Total 70 → 70).
- 2026-07-10 — #65 Antigravity 2.0 adapter: added `.gemini/settings.json`, `.antigravity/{plugin.json,gemini-extension.json,mcp_config.json,permissions.json}`, `.antigravity/rules/project-harness.md`, and 8 `.antigravity/hooks/*.py` shims. The adapter maps Gemini / Antigravity events to the shared governor policy without duplicating rules. Total 74 → 88 (Keep 55 → 66; Overlay 18 → 21; Tier 0 9 → 14; Tier 3 23 → 31; Tier 4 6 → 7). The prior total was recorded as 73/Keep 54, undercounting Tier 1 by one Keep row (the tier holds 22 rows: 18 Keep / 3 Overlay / 1 Drop); corrected to a 74/Keep 55 base here. Merged on top of #281 / ADR 054.
