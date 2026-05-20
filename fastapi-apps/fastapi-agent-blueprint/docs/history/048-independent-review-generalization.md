# 048. Independent Review Generalization — Tool-Agnostic Self-Review Sub-Step

- Status: Accepted
- Date: 2026-05-11
- Related issue: — (initiated from observability audit of Governor Footer era data)
- Supersedes (partial): ADR [045](045-hybrid-harness-target-architecture.md) Pillar 2 — the specific "cross-tool only" reviewer constraint. The independent review trigger itself (Tier A/B/C glob, mandatory sub-step of `self-review`) and the rest of ADR 045 remain in force.
- Constraints: ADR [047](047-governor-review-provenance-consolidation.md) Governor Footer shape and CI lint contract remain unchanged. No new fields added to `FIELD_ORDER`; `reviewer` remains an intentionally open-vocabulary string field.

## Summary

ADR 045 Pillar 2 mandated **cross-tool review** as the only accepted form of independent review for governor-changing PRs. The requirement was correct at build-out time (Phase 1~5, PR #125~#130) but created two downstream problems:

1. **Single-tool environment exclusion.** OSS adoption users who fork the blueprint and use only one AI tool cannot fulfill the CI obligation when customizing governance files. The `Governor Footer Lint` CI workflow fails the build with no **governed escape path** — the only workaround (`[skip-governor-footer]`) bypasses the audit trail entirely, defeating the governance intent.
2. **Spec–practice divergence.** Footer-era data (PR #159 and later) shows `reviewer: self` accounting for 50 % of governor-changing PRs, with 33 % recording 0 R-points under `trigger: yes`. The spec said "cross-tool", the practice was already "self-review".

This ADR generalizes Pillar 2 to accept any of three **independent review modes** without weakening the mandatory trigger or the Governor Footer audit trail.

## Background

### Effectiveness data (ADR 047 archive + Governor Footer era)

> **Data provenance note**: Archive-era numbers are derived from the 18 entries in `docs/history/archive/governor-review-log/` — narrative markdown files authored during review sessions, not machine-parseable records. Totals were tallied manually during this ADR's authoring session and should be treated as **session-level estimates, not repository-verified measurements**. Footer-era numbers were observed from PR description blocks during the same session. The ratios reflect consistent patterns across entries but carry ±5–10 % uncertainty from manual counting.

| Era | PRs | Total R-points | Fixed | Deferred | Rejected |
|---|---|---|---|---|---|
| Archive era (PR #125–#158, 18 entries) | 18 | ~293 | ~84 % | ~7 % | ~10 % |
| Footer era (PR #159+, sampled 18) | 18 | ~45 | ~82 % | ~18 % | 0 % |

Footer-era round count: mean ~1.4 (range 1–2). Reviewer split: `codex-cli` ~8/18, `self` ~10/18. ~6 PRs with `trigger: yes` recorded 0 R-points.

### High-signal cross-tool catches (from archive, not reproducible by self-review alone)

- **PR #130 R0-C.1** — single-entry `safe_parse_exception_token` prevented callable-injection bypass (security regression averted at design stage).
- **PR #141 R1.1** — non-existent `settings.app_name` reference caught before runtime AttributeError at bootstrap.
- **PR #155 R0.4** — admin auth must stay DB-side; role claim must not go into JWT token (security-sensitive design choice).
- **PR #156 R1.1–R1.4** — `frontend-handoff.md` documented `access_token` snake_case unwrapped; live API ships `SuccessResponse(data={"accessToken": ...})` via camelCase alias. Would have shipped misleading documentation.
- **ADR 046 Model D rejection** — cross-tool review prevented an over-broad architectural framing ("OTEL-only" overstates what OTEL replaces).

### Ceremony-cost signals

- PR #143 (reasoning guards): 6 rounds, 43 R-points; rounds 4–6 predominantly bookkeeping (line numbers, count mismatches).
- PR #148 (G closure linter): 39 % Rejected rate — highest false-positive ratio across all archived PRs.
- ADR 047 Background explicitly notes: "The surrounding permanent infrastructure … is over-engineered for a solo-developer steady state."
- Footer-era Rejected rate dropped to 0 % after format change, suggesting tighter input framing — not that the change surface became error-free.

### Conclusion from data

Cross-tool review is **high-signal where it is load-bearing**: new architectural decisions, security-sensitive domains, external contract documentation, and the harness build-out itself. It produces **diminishing returns** in derivative governance-meta PRs and routine harness maintenance. The mandatory trigger (Tier A/B/C) remains correct; the reviewer modality restriction to one tool is not.

## Decision

### D1 — Three independent review modes

Replace the "cross-tool only" requirement with an **independent review** requirement accepting three modes:

| Mode | Definition | `reviewer` field value |
|---|---|---|
| `cross-tool` | Another AI tool (e.g. `codex exec --sandbox read-only`, escalating model/effort only when warranted) reads the change set. Captures the "different model catches different errors" benefit. | Tool name (e.g. `codex-cli`, `claude-code`) |
| `self-structured` | Single-tool environment. The author applies the **Self-Structured Review Checklist** (F / G / H / I guards + contract verification + security surface + test coverage) defined in `docs/ai/shared/skills/review-pr.md` § "Self-Structured Review Checklist". | `self-structured` |
| `human` | A human reviewer (not the PR author) reviews the governor-changing surface. | `human:<github-handle>` |

One mode is sufficient per PR. Multiple modes may be comma-separated.

The `self-structured` checklist encodes the Reasoning-Level Guards (F/G/H/I from ADR #143 / AGENTS.md) as actionable self-verification steps. It is weaker than cross-tool review (same model, same biases) but stronger than unstructured self-review, and it is traceable via the Governor Footer.

### D2 — Round cap guidance (non-enforced)

Resolve each R-point within 2 rounds (initial + follow-up). A third round is a signal to split the PR. This is guidance documented in AGENTS.md and `target-operating-model.md §5`; it is not enforced by `check_governor_footer.py` lint (adding a hard cap would block legitimate complex PRs).

### D3 — `check_governor_footer.py`: reviewer field open-vocabulary + bypass restriction

The `reviewer` field remains intentionally unvalidated against a closed enum. The docstring is updated to document the accepted mode vocabulary explicitly (D1 above) and to clarify that the open-vocabulary design was present from the initial implementation — this ADR formalises it, not changes it. No breaking change to the footer schema.

**Bypass token restriction (CI / `--require-governor-footer` mode)**: `[skip-governor-footer]` is now blocked for governor-changing PRs when the linter runs in CI mode (`--require-governor-footer` flag). Previously the token unconditionally bypassed all footer validation, including for files in Tier A/B/C — directly undermining the ADR048-G1 mandatory requirement. After this change, the bypass token only applies to non-governor-changing PRs in CI mode; attempting to use it on a governor-changing PR produces a hard CI Violation. Ad-hoc local dry-runs (without `--require-governor-footer`) are unaffected — `is_governor` is always `False` in that mode. For path-level exemptions from CI enforcement (e.g. cosmetic-only changes to governance files), the correct mechanism is `docs/ai/shared/governor-paths.md § Exclusions`, not the bypass token.

**Backward compatibility:** Historical `reviewer: self` footers recorded before this ADR defined `self-structured` remain valid. They represent unstructured self-review performed during the transition period. New self-only reviews must use `reviewer: self-structured`. No backfill of existing footers is required.

### D4 — Self-Structured Review Checklist added to four skill docs

`docs/ai/shared/skills/{review-pr,review-architecture,security-review,sync-guidelines}.md` each gain a `## Self-Structured Review Checklist` section at the end, covering:

- **F** — volatile workspace facts re-verification
- **G** — closure category discipline
- **H** — effect vs process question discrimination
- **I** — self-licensing check before defense
- Skill-specific surface checks (layer rules, security, external contracts, test coverage)

### D5 — Terminology alignment across harness

"Cross-tool review" replaced by "independent review" in:
- `AGENTS.md` § Self-Review Step heading and body
- `docs/ai/shared/target-operating-model.md` §5 heading and step 2
- `docs/ai/shared/governor-paths.md` L69 merge condition and consumer table
- `.github/pull_request_template.md` `reviewer` field guidance
- `tools/check_governor_footer.py` error message (rounds validation)

The phrase "Cross-Tool Review Prompt Template" in skill docs is **not renamed** — it describes the prompt format used by `cross-tool` mode and remains accurate for that mode.

## Consequences

### Durable governance constraints (ADR048-G1 ~ ADR048-G5)

**ADR048-G1** — Independent review (any accepted mode from D1) is mandatory for every governor-changing PR (Tier A/B/C, not excluded). "mandatory" means `rounds >= 1` in the Governor Footer. CI lint fails if: (a) the `## Governor Footer` block is absent, (b) `trigger: no` on a governor-changing PR (the linter detects governor-changing files; claiming no trigger is required contradicts that detection), (c) `trigger: yes` with `rounds: 0`, or (d) the `[skip-governor-footer]` bypass token is present (D3). The bypass token is restricted to non-governor-changing PRs; attempting to use it on a governor-changing PR produces a hard CI failure.

**ADR048-G2** — The `reviewer` field in the Governor Footer is intentionally open-vocabulary. The linter does not restrict to a closed enum. Any value is accepted; the three canonical modes are `cross-tool` (tool name), `self-structured`, and `human:<handle>`. New modes do not require an ADR — they require only documentation in AGENTS.md.

**ADR048-G3** — `self-structured` mode must use the checklist defined in `docs/ai/shared/skills/review-pr.md` § "Self-Structured Review Checklist" (or the skill-specific equivalent). The checklist covers F/G/H/I guards and skill-surface items. Using `reviewer: self-structured` without working through the checklist violates this constraint. Evidence of the checklist work (checked items and any deferred rationale) must appear in the PR body; the footer's `reviewer: self-structured` alone is insufficient as an audit trail.

**Enforcement gap (explicit disclosure)**: `check_governor_footer.py` does NOT verify that checklist evidence actually appears in the PR body — this is honor-system enforcement only. The linter accepts `reviewer: self-structured` without inspecting the PR description content. This is a deliberate scope boundary (semantic PR-body verification is out of scope for a shape linter). The capability gap relative to cross-tool review is also intentionally documented: `self-structured` uses the same model with the same context and cannot catch blind spots that a different model would catch. It is structurally weaker than `cross-tool` review for this reason, not merely less convenient.

**ADR048-G4** — Cross-tool review remains the **preferred** mode when another AI tool is available. `self-structured` and `human` are accepted alternatives, not upgrades. For changes touching security-sensitive domains (`src/auth/`, new external endpoints, credential handling) or external contracts (`docs/frontend-handoff.md`, OpenAPI surface), `cross-tool` mode is the **practical default**, not merely strongly recommended. Using `self-structured` for these paths requires explicit rationale (e.g. single-tool environment, documented in PR body).

**ADR048-G5 (backward compatibility)** — Historical Governor Footer entries that record `reviewer: self` (before this ADR defined `self-structured`) remain valid. They represent self-review performed before a structured checklist was available. New self-only reviews must use `reviewer: self-structured`. No backfill of existing footers is required.
