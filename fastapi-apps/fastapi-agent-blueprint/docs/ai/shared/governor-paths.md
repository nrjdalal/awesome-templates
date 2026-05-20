# Governor-Changing Paths (Canonical Source)

> Last synced: 2026-04-27 (added `CLAUDE.md` to Tier A — auto-loaded into every Claude session, so language drift here propagates fastest; fixed `.pre-commit-config.yaml` filename typo).
> Initial sync: 2026-04-26 (introduced in Round-4 self-coherence review of PR #125 to reconcile path lists across AGENTS.md / target-operating-model.md / migration-strategy.md / drift-checklist.md / .github/pull_request_template.md).
> All references to "governor-changing paths" in any harness document **must** link this file rather than re-declare the list. Drift between copies is the failure mode this file exists to prevent.

## Purpose

ADR 045 introduced the concept of *governor-changing PRs* — PRs whose changed-files intersect a specific glob. Five separate documents reference this concept; before this file existed, each had its own slightly different list. Round 4 of the cross-tool review found the divergence and recommended canonicalisation. The hook and parser implementations of Phase 2~5 will eventually read this file (or its parsed form) as the single source.

## The Path List

A PR is **governor-changing** if its `changed_files` intersects any path below.

### Tier A — Constitutional / Policy Documents (always trigger)

- `AGENTS.md`
- `CLAUDE.md`
- `docs/ai/shared/**` (every file under the shared reference directory)
- `docs/history/**` (every ADR and archive entry, including `archive/governor-review-log/**`)
- `.claude/rules/**`
- `.codex/rules/**`
- `.github/pull_request_template.md`

The doc-only auto-escape (`target-operating-model.md` §3) does **not** apply to Tier A. Even a one-line edit triggers `framing → plan → verify → self-review → completion gate`.

### Tier B — Tool-Specific Harness Surfaces (always trigger)

- `.claude/**` (settings, skills, hooks — entire directory)
- `.codex/**` (config, hooks, settings — entire directory; rules already in Tier A)
- `.agents/**` (skills, future shared modules — entire directory)

Tier B includes Tier A's `.claude/rules/**` and `.codex/rules/**` (those are the policy subset of Tier B). Mentioning both `Tier A` and `Tier B` separately is intentional: Tier A captures the *policy* lens (carve-out from doc-only escape), Tier B captures the *tool surface* lens (full directory triggers independent review).

### Tier C — Other Repo-Level Governance Artefacts (trigger if introduced)

- `.github/workflows/**` (CI as governance)
- `pyproject.toml`'s `[tool.ruff]`, `[tool.mypy]`, or other linting/typing/policy sections
- `.pre-commit-config.yaml`
- Any new file at the repo root that defines policy (future ADR will add)

Tier C is intentionally narrow today; the list grows only when an ADR explicitly extends it.

## Exclusions (NOT governor-changing even though path-glob looks close)

- **Log-only backfill PRs**: a PR whose `changed_files` is **entirely under** `docs/history/archive/governor-review-log/` does **not** require its own new self-log entry. Per ADR 047 D6 the only permitted edit to a frozen entry is appending an `Errata YYYY-MM-DD:` heading with English-only errata; existing sections (Review Rounds / Self-Application Proof / Inherited Constraints) are write-protected. The narrower scope replaces the pre-ADR-047 phrasing that allowed extending those sections inline. This exclusion breaks the recursion that would otherwise require every errata-only PR to log itself.
- **`/sync-guidelines` cosmetic edits (ADR 047 D4)**: a `.claude/rules/**` change is exempt from governor-changing classification when the *governor-matching subset* of `changed_files` is limited to one or more of the three covered files AND each covered file's diff contains only the cosmetic patterns listed below. Other changes outside `.claude/rules/**` are evaluated independently — they may or may not trigger on their own merits.
  - `.claude/rules/project-status.md`: `> Last synced:` line edits + additions / edits of rows in the `## Recent Major Changes` table.
  - `.claude/rules/project-overview.md`: `> Last synced:` line edits.
  - `.claude/rules/commands.md`: `> Last synced:` line edits.
  Semantic edits to those same files (new sections, regenerated bodies, rule additions, anything outside the cosmetic patterns) still trigger. The carve-out is deliberately narrow because `/sync-guidelines` produces these cosmetic edits as a routine closure step on most feature PRs; without the carve-out, every feature PR would inherit the full governor-changing ceremony purely because of its closure step (the original "self-loop" identified in ADR 047 Background).
- **Generated artefact regeneration**: `docs/assets/architecture/*.svg` regenerated via `make diagrams` after a `docs/ai/shared/architecture-diagrams.md` source edit. The source edit itself triggers; the regenerated SVGs do not double-trigger.
- **`.gitignore`d entries**: `.claude/settings.local.json` and similar — never in PR diffs by definition.

## Identification Rules

A reviewer or hook decides "is this PR governor-changing?" by:

1. Compute `changed_files = git diff --name-only main..HEAD` (or the PR diff equivalent).
2. For each path in `changed_files`, test against every Tier A / B / C glob.
3. Apply Exclusions in order; if any rule applies and matches the entire change set, the PR is **not** governor-changing.
4. Otherwise, if at least one Tier A / B / C glob matches, the PR **is** governor-changing.

## Required artefacts when governor-changing

When the rules above classify a PR as governor-changing (and after [ADR 047](../../history/047-governor-review-provenance-consolidation.md) D2/D5), the PR must produce:

- A **`## Governor Footer` block** in the PR description (10-field machine-parseable shape, closure-label vocabulary `Fixed` / `Deferred-with-rationale` / `Rejected`). The `Governor Footer Lint` CI workflow runs `tools/check_governor_footer.py --require-governor-footer` against the PR body and changed-file list and **fails the build** if the footer is missing, mis-shaped, or declares `trigger: no` on a governor-changing change set.
- At least one round of independent review captured in the footer (`rounds: N >= 1`, `reviewer: <mode or comma-list>`, R-points closed). Accepted reviewer modes: a tool name (e.g. `codex-cli`), `self-structured`, or `human:<handle>` — see `AGENTS.md` § Independent Review Trigger.
- Durable governance constraints introduced by the PR added as new `ADR{NNN}-G{N}` slot bodies in the relevant ADR's Consequences section. Durable domain invariants go to `docs/ai/shared/project-dna.md` or the relevant domain doc (e.g. §15 Auth Domain Pattern, §16 Docs Frontend Contract). PR-scope and superseded constraints stay only in the PR description's `pr-scope-notes` field.
- The pre-ADR-047 obligation (`docs/history/archive/governor-review-log/pr-{NNN}-{slug}.md`) is **retired** for new PRs. The directory remains as a frozen historical archive for the 18 entries written before PR #158 — see [`governor-review-log/README.md`](../../history/archive/governor-review-log/README.md) for the alias map.

## Where this file is consumed

| Consumer | Purpose |
|---|---|
| `AGENTS.md` § Default Coding Flow → Self-Review trigger | Mandatory independent review condition |
| `AGENTS.md` § Default Coding Flow → Doc-only carve-out | Auto-escape exclusion |
| `docs/ai/shared/target-operating-model.md` §3 | Auto-escape carve-out |
| `docs/ai/shared/target-operating-model.md` §5 Independent Review Cadence | Trigger detection |
| `docs/ai/shared/migration-strategy.md` Phase 4 acceptance | Hard reminder trigger |
| `docs/ai/shared/drift-checklist.md` §1D | Sync verification |
| `.github/pull_request_template.md` § Governor-Changing PR | Author self-classification |
| Phase 5 shared governor module | Programmatic detection |

If you add a new consumer, add the row above so the canonical surface stays visible.

## Updating this file

This file is itself governor-changing (Tier A, `docs/ai/shared/**`). Any edit must:

- Be reflected by all consumers above (verify their copies are still link-only, not duplicate-list).
- Be captured in the PR description's `## Governor Footer` block (post-ADR-047) — the Footer's `rounds` / `r-points-*` fields cover the Round 1+ independent review of the path-list change. CI's `Governor Footer Lint` workflow validates the Footer shape.
- Add a new `ADR{NNN}-G{N}` slot to the relevant ADR's Consequences section if the edit introduces a durable governance constraint that future PRs must inherit.

This recursion is intentional: a change to the canonical paths definition is a high-impact governor change.
