# Governor Review Log

> **Closed historical archive — no new entries are added after PR #158 / [ADR 047](../../047-governor-review-provenance-consolidation.md).**
> Cross-tool review provenance for new governor-changing PRs lives in the PR
> description's ``## Governor Footer`` block (ADR 047 §D2), enforced in CI by
> ``tools/check_governor_footer.py``. Durable inherited constraints live in
> ADR Consequences sections — see ADR 047 §"Durable Governance Constraints
> (ADR047-G1 ~ ADR047-G27)" and the IC Classification Table for the
> historical-id alias map.
>
> The 18 entries below document the Phase 1~5 build-out of the hybrid harness
> governance system. They remain in the repository as a frozen historical
> record; do not edit existing entries except to append append-only English
> errata under an explicit ``Errata YYYY-MM-DD:`` heading. Provenance prefixes
> (``> Original ... (ko, verbatim):``) and ``LOCALE_DATA_FILES`` carve-outs
> stay in force for the existing entries (ADR 047 §D6).
>
> Original purpose (pre-ADR-047): Living archive of cross-tool review trails
> for **governor-changing PRs**, sourced from ADR 045 §Self-Application
> Recovery + AGENTS.md § Default Coding Flow §Cross-Tool Review.

## Purpose

Issue #117 introduced a hybrid local process governor (ADR 045). The review trail that produced ADR 045 — three rounds of Codex `gpt-5.5 --sandbox read-only` review — is *itself* a load-bearing piece of context that subsequent governor-changing PRs (Phase 2~5 of [migration-strategy.md](../../../ai/shared/migration-strategy.md), and any future shared-rule edit) must inherit to avoid re-discovering the same blind spots.

This directory exists so that the trail is not buried in PR descriptions.

## Scope (which PRs need a log entry)

A PR is **governor-changing** — and therefore must add an entry here — if its `changed_files` intersects any glob in [`governor-paths.md`](../../../ai/shared/governor-paths.md) (Tier A / B / C minus Exclusions).

For non-governor-changing PRs (regular feature, bug fix, refactor inside `src/`), no entry is required. The `governor-paths.md` file itself defines the Exclusions (e.g. log-only backfill PRs that extend an existing entry).

## File naming

```
pr-{NNN}-{short-slug}.md
```

Example: `pr-125-hybrid-harness-target-architecture.md`.

The number is the GitHub PR number. The slug is a kebab-cased short title (≤ 60 chars).

## Entry shape

Each entry must contain at minimum:

1. **Summary** — one-paragraph PR description, link to GitHub PR.
2. **Review rounds** — ordered list of Codex review rounds (or equivalent cross-tool review). Each round captures: target, prompt focus, surfaced points (R1, R2, ...), Final Verdict.
3. **Inherited constraints** — the R-points and lessons that future governor-changing PRs must respect. This is the part that is link-cited from follow-up issues.
4. **Self-application proof** — explicit invocation of `/review-architecture` and `/sync-guidelines` on the PR's own changed surface, with their canonical outputs (Findings / Drift Candidates / Sync Required / Remaining). Required so that the governor proves it followed itself.

Each entry must also contain exactly one `## R-points Closure Table` section.
The table is the mechanical record for AGENTS.md guard G: every R-point raised
by cross-review, cross-check, or external verification must be closed as
`Fixed`, `Deferred-with-rationale`, or `Rejected`.

Canonical table shape:

```markdown
## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 1 | R1.1: concise finding title | Fixed | Commit or documentation reference. |
```

The `Closure` cell may use a plain label or bold exact label:
`Fixed`, `Deferred-with-rationale`, `Rejected`, `**Fixed**`,
`**Deferred-with-rationale**`, or `**Rejected**`. Non-canonical labels such as
`Fixed (retracted)`, `Rejected after correction`, `Deferred`, lowercase
variants, italic variants, and labels with extra words are invalid.

**(Historical)** `tools/check_g_closure.py` enforced this table shape via the `governor-review-log-g-closure` pre-commit hook for `docs/ai/shared/governor-review-log/pr-*.md`. ADR 047 PR B-F (issue #157) removed the tool and the hook; the closure-table shape requirement is preserved on the 18 frozen entries by the historical record itself, and the canonical Guard G enforcement target moved to the PR-description `## Governor Footer` block (`tools/check_governor_footer.py`).

## Retention

Closed historical archive — see banner above. The 18 entries below are preserved for the lifetime of the repository as a frozen build-out record. The active equivalents are the PR-description Governor Footer block (`tools/check_governor_footer.py`) and ADR Consequences (`ADR{NNN}-G{N}` slots in [ADR 047](../../047-governor-review-provenance-consolidation.md) and successor ADRs).

## Drift discipline

`docs/ai/shared/drift-checklist.md` §1D (rewritten by ADR 047 PR B-F) verifies that every governor-changing PR merged into `main` had a passing `Governor Footer Lint` CI run and that any new `ADR{NNN}-G{N}` durable constraints landed in the same merge. The pre-ADR-047 sync check enumerated this directory; the new check enumerates merged PR descriptions instead.

## Cross-Tool Review Prompt Template

Use the template below as a starting point when invoking `codex exec -m gpt-5.5 --sandbox read-only "<prompt>"`. Adapt the bullets to the specific phase or change set; do not include sections that do not apply.

```
**Cross-tool review of <PR / plan / change-set name>** (read-only). markdown only; no file modification, no git commands.

## Context
- Repo: fastapi-agent-blueprint
- PR / branch: <link or branch name>
- Issue link: <#NNN>
- ADR(s) governing this change: <e.g. ADR 045>
- Inherited constraints carried from prior PRs: <link governor-review-log entries; cite IC-N tags>
- Round number: <1 plan / 2 implementation / 3 readiness / N>

## What you are reviewing
- <one-paragraph summary of the change set>
- Key files: <list 3~5 critical files>

## Review angles (per item: OK / needs fix / reconsider / block merge)

1. Self-coherence — does this PR follow the governor it modifies?
2. Path-list / trigger glob consistency — do AGENTS.md / TOM / migration / drift-checklist / PR template all link `governor-paths.md` correctly without re-declaring?
3. Hand-off readiness — can a new contributor with cold context start the next phase from issue body + governor-review-log + ADR?
4. Cross-tool symmetry — Claude vs Codex hook surfaces; `apply_patch` blind spot (R7); NFKC normalisation (R3); precedence rules (R1).
5. Cascade risk — what new false-negatives or false-positives does this PR introduce?
6. Friction vs governance balance — issue #117 Non-Goals (heavy ceremony / false-positive blocking).
7. New gaps not seen in earlier rounds — what does fresh eyes catch?

## Output format

Each review angle: assessment + 1~3 paragraph analysis citing file:line where possible. Then:
- **Final Verdict**: merge-ready / minor fixes recommended / still needs reinforcement / block merge
- **Top recommendations** (priority order)
- **Open questions** for the user
```

The prompt is a starting point; phase-specific reviews (Phase 2 token parser,
Phase 3 verify adapter, Phase 4 completion gate, Phase 5 shared module) extend
it with phase-specific angles. For quality-gate skills, use the per-skill
specialisations in
`docs/ai/shared/skills/{review-pr,sync-guidelines,security-review,review-architecture}.md`.

## Index

| PR | Title | Issue | Entry |
|---|---|---|---|
| #125 | hybrid harness target architecture + Phase 1 | #117 | [pr-125-hybrid-harness-target-architecture.md](pr-125-hybrid-harness-target-architecture.md) |
| #126 | Phase 2: UserPromptSubmit exception-token parser | #121 | [pr-126-userpromptsubmit-token-parser.md](pr-126-userpromptsubmit-token-parser.md) |
| #127 | Phase 3: verify-first adapters (Claude PostToolUse + Codex Stop) | #122 | [pr-127-verify-first-adapters.md](pr-127-verify-first-adapters.md) |
| #128 | Phase 4: completion-gate Stop adapter (IC-11 Option A + Pillar 7) | #123 | [pr-128-completion-gate-stop-adapter.md](pr-128-completion-gate-stop-adapter.md) |
| #130 | Phase 5: shared governor module + thin shims (Hybrid Harness v1 closure) | #124 | [pr-130-shared-governor-module.md](pr-130-shared-governor-module.md) |
| #132 | Tier 1 language policy + Korean prose cleanup + 3-layer enforcement | #131 | [pr-132-language-policy.md](pr-132-language-policy.md) |
| #134 | AGENT_LOCALE: localized hook reminders + locale data exception | #133 | [pr-134-agent-locale.md](pr-134-agent-locale.md) |
| #138 | ADR 046 follow-up: Status Accepted + issue backfill #136/#137 + project-status sync | #74 / #135 | [pr-138-adr-046-followup.md](pr-138-adr-046-followup.md) |
| #141 | OTEL core: `[otel]` extra + settings + bootstrap wiring + recipe doc | #136 | [pr-141-otel-core.md](pr-141-otel-core.md) |
| #143 | Reasoning-Level Consistency Guards (F / G / H / I) — Tier 1 Layer 2 governor | — | [pr-143-reasoning-guards.md](pr-143-reasoning-guards.md) |
| #147 | Cross-tool prompt template standardisation for review skills | #144 | [pr-147-cross-tool-prompt-standardisation.md](pr-147-cross-tool-prompt-standardisation.md) |
| #148 | G closure linter for governor review-log entries | #145 | [pr-148-g-closure-linter.md](pr-148-g-closure-linter.md) |
| #151 | Architecture review follow-up | — | [pr-151-architecture-review-followup.md](pr-151-architecture-review-followup.md) |
| #152 | CRUD Data Validation Sync | #10 | [pr-152-crud-data-validation-sync.md](pr-152-crud-data-validation-sync.md) |
| #153 | JWT authentication domain | #4 | [pr-153-jwt-auth-domain.md](pr-153-jwt-auth-domain.md) |
| #155 | NiceGUI admin JWT RBAC migration | #154 | [pr-155-nicegui-admin-jwt-rbac.md](pr-155-nicegui-admin-jwt-rbac.md) |
| #156 | `/docs` selector revamp + frontend handoff guide + closing-gate sync | — | [pr-156-docs-selector-revamp-handoff.md](pr-156-docs-selector-revamp-handoff.md) |
| #158 | Bridge to ADR 047 — governor-review-log right-sizing (last entry) | #157 | [pr-158-bridge-adr-047.md](pr-158-bridge-adr-047.md) |
