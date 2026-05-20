# 045. Hybrid Harness Target Architecture — Process Governor + Asset Triage

- Status: Accepted
- Date: 2026-04-26
- Related issue: #117
- Related PRs: #115 / #116 (first philosophy port — `/plan-feature` Approach Options Phase)
- Precursor memo: [archive/044](archive/044-superpowers-gstack-process-governor-evaluation.md) (superpowers / gstack / process-governor evaluation)
- Constraints: ADR [040](040-rag-as-reusable-pattern.md), [042](042-optional-infrastructure-di-pattern.md), [043](043-responsibility-driven-refactor.md) — the architecture / DI / responsibility layers are **immutable** for this ADR

## Summary

This ADR records the top-level decisions that resolve issue #117 (`Design a hybrid superpowers adoption model with harness asset triage`). It commits the project to a **local process governor inspired by superpowers' philosophy**, not to adopting an external superpowers package. The three design outputs required by #117 (Asset Inventory Matrix, Target Operating Model, Migration Strategy) are split into separate living docs under `docs/ai/shared/` and indexed from this ADR.

Four decisions:

1. **D1 — 7-step Default Coding Flow** added to `AGENTS.md` as a new shared-constitution section, with explicit precedence rules below sandbox / approval / `.codex/rules` / safety hooks / Absolute Prohibitions.
2. **D2 — Hybrid graduated enforcement**: guidance + skill-body mandatory phases now (Phase 1) + minimal hooks later (Phase 2~5). Critical gates remain hard; trivial work escapes via explicit tokens.
3. **D3 — Machine-readable exception token vocabulary** (English + Korean) recognised only as a leading token on prompt line 1, never overriding safety.
4. **D4 — Output split** across one ADR (decisions) and three living docs (matrix / operating-model / migration-strategy).

## Background

[archive/044](archive/044-superpowers-gstack-process-governor-evaluation.md) diagnosed the real problem as **weak routing**, not missing skills: the repo already ships a shared constitution (`AGENTS.md`), a 3-layer Hybrid C skill split (14 skills × 3 layers), 11 hooks (Claude + Codex), and a shared reference layer (`docs/ai/shared/`). What is missing is a default execution flow that *routes* most coding tasks through framing → planning → verification → self-review by default.

[#115 / #116](https://github.com/anthropics/claude-code/issues/28310) ported the first piece of that flow (Approach Options as Phase 1 of `/plan-feature`), but did not generalise it to other implementation skills, and added no enforcement beyond skill-body text.

Issue #117 asked for three explicit deliverables — an Asset Inventory Matrix, a Target Operating Model, and a Migration Strategy — together with answers to eight key design questions. This ADR records the meta-decisions; the deliverables themselves are in `docs/ai/shared/`.

A read-only Codex review (gpt-5.5, sandbox=read-only, run via `profiles.research`) on 2026-04-26 contributed seven cross-tool consistency corrections that are now baked into the design.

## Decision

### D1 — Default Coding Flow with explicit precedence

Seven steps, added as a new top-level section of `AGENTS.md`:

```
problem framing → approach options → plan → implement
                → verify → self-review → completion gate
```

Mandatory-by-default for implementation-class work: `framing`, `plan`, `verify`, `self-review`.
Conditionally mandatory (architecture commitment present): `approach options`.

**Precedence (Codex R1).** Default Coding Flow ranks **below** the following four layers, in order:

1. Active sandbox / approval policy / explicit user scope (e.g. read-only, review-only)
2. `.codex/rules/*` prefix rules (`forbidden` / `prompt`)
3. Safety hooks (security checks, destructive-command guards)
4. `AGENTS.md` § Absolute Prohibitions

Escape tokens (D3) reduce process burden only. They never override any of the four layers above.

### D2 — Hybrid graduated enforcement

Three layers of strength, introduced incrementally:

- **(a) Guidance** — `AGENTS.md` § Default Flow, `CLAUDE.md` cross-link, `docs/ai/shared/skills/{name}.md` mandatory-phase text. Phase 1 (this PR).
- **(b) Skill body** — 14 skills × 3 wrapper layers (`docs/ai/shared/skills/`, `.claude/skills/`, `.agents/skills/`) gain a "Default Flow Position" section + Phase/Step overview update. Phase 1 (this PR).
- **(c) Minimal hooks** — `UserPromptSubmit` (Phase 2), `PostToolUse` / `Edit|Write` for Claude + `Stop` / changed-files for Codex (Phase 3), `Stop` completion gate (Phase 4), shared parser/policy module (Phase 5). Each as a separate follow-up issue.

Critical gates remain hard in (c); the hybrid label refers to the explicit escape lane, not to weakened blocking. False-positive cost (which silently normalises hook bypass and thus disables the governor) is the reason hard-only enforcement is rejected. See `target-operating-model.md` §3.

### D3 — Exception token vocabulary

English: `[trivial]` / `[hotfix]` / `[exploration]`. Korean (matching contributor language preference): `[자명]` / `[긴급]` / `[탐색]`.

Recognition rules (Codex R3):

- Tokens are recognised **only as a leading token on the first line** of a prompt. Body occurrences are ignored, preventing accidental matches in natural Korean text.
- Prompts are NFKC-normalised before matching.
- Regex: `^\s*\[(trivial|hotfix|exploration|자명|긴급|탐색)\](?:\s|$)` (case-insensitive).
- Token use carries a follow-up obligation: the next commit message must record the rationale.

Auto-escapes (no token required): `changed_files == 0`, doc-only changes, comment-only changes.

### D4 — Output split

| Doc | Location | Target length | Role |
|---|---|---|---|
| ADR 045 (this) | `docs/history/` | 150~220 lines | Decisions + navigator + design-question resolutions |
| `harness-asset-matrix.md` | `docs/ai/shared/` | 600~800 lines | Living inventory: ~50 assets across 5 tiers, 9 columns |
| `target-operating-model.md` | `docs/ai/shared/` | 400~500 lines | §1~§7 of the operating model + workstream / sample-trace / Q&A appendices |
| `migration-strategy.md` | `docs/ai/shared/` | 200~300 lines | Phase 0~5 spec, rollback, dual-system window, ordering |

The matrix is a *living* inventory and must not be embedded in an ADR (which is immutable). The operating model carries the long-form workflow traces that a navigator-style ADR cannot host without bloating.

## Eight Design Questions (issue #117) — Resolution Map

1. **Project-specific value vs commodity scaffolding** → resolved by the matrix Tier classification (Tier 0/1 = project-specific; parts of Tier 2 = commodity process scaffolding).
2. **Stay local / overlay / replace / drop** → matrix bucket column. Final Phase 1 distribution (post Round-7): ~86% Keep / ~14% Overlay / 0% Replace / 0% Drop. The first triage flagged one Drop candidate (`.claude/hooks/pre_tool_security.py`); self-verification during cross-link work overturned it because the file is the active body invoked by `pre-tool-security.sh`. Future passes may re-introduce Replace or Drop candidates; the matrix is living.
3. **Minimum viable process governor** → the 7-step Default Coding Flow + mandatory-by-default subset + explicit escape lane.
4. **Mandatory by default for coding work** → framing + plan + verify + self-review. `approach options` mandatory only when the change is an architecture commitment.
5. **Where enforcement lives** → (i) shared rules: `AGENTS.md` § Default Flow; (ii) shared workflow docs: `target-operating-model.md`; (iii) skill wrappers: 3-layer mandatory-phase + Default Flow Position; (iv) session-start guidance: deferred to Phase 2; (v) prompt-submit hooks: Phase 2; (vi) stop-time completion gates: Phase 4.
6. **Valid exception** → leading-line escape tokens (D3) + auto-escapes (no-change, doc-only, comment-only). Safety / sandbox / prefix rules are never escapable.
7. **Claude / Codex alignment** → `AGENTS.md` is canonical. Tool-specific adapters are split per phase: Codex enforcement is **prompt-time routing + changed-file completion checks**, not Bash-only `PostToolUse` (Codex R7). Phase 5 consolidates parsers and policies into a shared module so neither side duplicates harness logic.
8. **Rigor without friction** → hybrid graduated (D2). Hard at critical gates, escape lane for trivial work. Aligned with #117 Non-Goals (no heavy ceremony) and Constraints (narrow exceptions).

## Consequences

**Positive**

- Resolves the "weak routing" diagnosis from archive/044 with a concrete, phased mechanism rather than further documentation increase.
- Preserves ADR 040 / 042 / 043 architecture and DI decisions intact; this ADR sits strictly above them in the process layer.
- Phase 2~5 are independently revertable. Single-PR rollback per phase.
- The `/sync-guidelines` skill already detects 3-layer skill drift, so Phase 1's wrapper-synchronisation requirement is enforceable without new tooling.

**Negative**

- This PR touches ~50 files. The 14 × 3 wrapper edits are a repeated pattern (review burden ≈ 10 files), but the surface is still wide.
- Escape-token vocabulary widens hook complexity in Phase 2. Mitigated by leading-token-only recognition (D3).
- Adds a new top-level section to `AGENTS.md`. Future contributors must respect the precedence ordering (D1) when proposing further enforcement.

**Neutral**

- Phase 0.5 Codex cross-tool review is now a documented step that any future cross-tool design change should follow. Not a binding rule, but a referenced precedent.

## Self-Application Recovery (Pillar set, post-Round-3)

A fourth Codex round (read-only, focused on self-coherence) surfaced that PR #125 itself, while introducing the governor, did not fully follow the governor it was introducing — `self-review` (`/review-architecture`) and `completion gate` (`/sync-guidelines`) skills were not explicitly invoked; the Codex review chain had filled those roles only because the user manually requested it. The diagnosis was *self-application proof is weak*, not *self-contradiction*: Phase 1 is the rule-creating phase, and Phase 2~4 hooks that would have made the rule self-enforcing did not yet exist.

To prevent the gap from cascading into Phase 2~5, the following Pillars are added to this PR (Pillar 1~8). All are additive; no behaviour change to non-governor-changing PRs:

| # | Pillar | Where it lives |
|---|---|---|
| 1 | PR #125 self-application proof — `/review-architecture` and `/sync-guidelines` outputs captured for the PR's own surface | [`governor-review-log/pr-125-...md`](archive/governor-review-log/pr-125-hybrid-harness-target-architecture.md) §Self-Application Proof |
| 2 | Self-review step gains a *conditional* cross-tool review sub-step, triggered by governor-changing trigger glob | [`AGENTS.md` § Self-Review Step](../../AGENTS.md#default-coding-flow), [`target-operating-model.md` § Cross-Tool Review Cadence](../ai/shared/target-operating-model.md) |
| 3 | `auto-escape: doc-only` carve-out so that policy/harness docs are **not** escaped | [`AGENTS.md` § Doc-only carve-out](../../AGENTS.md), [`target-operating-model.md` §3](../ai/shared/target-operating-model.md) |
| 4 | `governor-review-log/` directory permanently archives review trails | [`docs/history/archive/governor-review-log/`](archive/governor-review-log/) |
| 5 | `.github/pull_request_template.md` adds Governor-Changing PR checklist (artefact-locks the cross-tool review and self-application proof) | [`.github/pull_request_template.md`](../../.github/pull_request_template.md) |
| 6 | Follow-up issues #121~#124 bodies link the log entry under "Inherited Review Constraints" | gh issue bodies |
| 7 | Phase 4 completion-gate Stop adapter checks for missing governor-review-log entry | [`migration-strategy.md` §1 Phase 4 Acceptance](../ai/shared/migration-strategy.md) |
| 8 | Optional supplemental — claude-code memory `feedback_codex_cross_review.md` generalised to phase-level review (helpful for the user's own claude-code sessions; not a load-bearing artefact because it is not repo-visible) | claude-code memory feedback file (per-user, per-machine) |

The substantive enforcement lives in Pillars 4 + 5, both repo-visible. Pillar 8 was originally counted equally; Round-4 review (R4.2) downgraded it because a memory file outside the repo is not transmitted to new contributors or to CI. The downgrade does not weaken the system; it relabels honestly.

The Pillars together close the bootstrapping gap: from Phase 1 onward the governor produces evidence of its own application, and any subsequent governor-changing PR encounters the trigger via PR template (Pillar 5) → review-log requirement (Pillar 4) → drift-checklist §1D verification → Phase 4 hard reminder (Pillar 7), so user vigilance is no longer the only enforcement layer.

Round-4 also introduced the canonical [`governor-paths.md`](../ai/shared/governor-paths.md) so that the trigger glob has a single source. Without it, the five consumer documents (AGENTS.md, target-operating-model.md, migration-strategy.md, drift-checklist.md, PR template) would drift over time as they did during Round 4. Future governor-changing PRs must update `governor-paths.md` and **never** redeclare the path list inline.

## Alternatives Considered

- **Full superpowers adoption** — Rejected in archive/044. Replaces our shared constitution and project-specific architecture canon; collides with ADR 040 / 042 / 043 boundaries.
- **Soft enforcement only (guidance, no skill-body / no hooks)** — Reproduces the archive/044 diagnosis ("good rules ≠ good default behavior"). Reverting the disease is not a fix.
- **Hard enforcement only (every task hook-blocks)** — Violates #117 Non-Goals (heavy ceremony, false-positive blocking) and Constraints (narrow exceptions). False-positive cost normalises bypass and disables the governor.
- **Single ADR carrying matrix + model + strategy** — Living inventory cannot live in an immutable ADR. Length would exceed 1000 lines. Rejected for both shape and decay reasons.

## Related Documents

- [`docs/ai/shared/harness-asset-matrix.md`](../ai/shared/harness-asset-matrix.md) — issue #117 Required Output #1
- [`docs/ai/shared/target-operating-model.md`](../ai/shared/target-operating-model.md) — issue #117 Required Output #2
- [`docs/ai/shared/migration-strategy.md`](../ai/shared/migration-strategy.md) — issue #117 Required Output #3
- [`AGENTS.md` § Default Coding Flow](../../AGENTS.md) — Phase 1 constitutional addition
- [archive/044](archive/044-superpowers-gstack-process-governor-evaluation.md) — antecedent evaluation memo
