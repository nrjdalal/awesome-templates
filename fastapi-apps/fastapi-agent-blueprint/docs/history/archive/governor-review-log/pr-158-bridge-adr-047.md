# PR #158 — Bridge to ADR 047 (governor-review-log right-sizing)

## Summary

PR [#158](https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/158) introduces [ADR 047](../../047-governor-review-provenance-consolidation.md) as the bridge for a 6-PR phased migration that right-sizes the cross-tool review provenance system. Two rounds of Codex CLI cross-review (gpt-5.5, model_reasoning_effort=xhigh, sandbox=read-only) — plus a third design-stage review on the ADR 047 draft itself — concluded that the build-out trail (Phase 1~5, 5 days, 14 self-referential entries) was right-sized but the surrounding permanent infrastructure (per-PR archive obligation, lifetime retention, broad Tier matching that creates a `/sync-guidelines` self-loop, full-output Self-Application Proof archival) is over-engineered for a solo-developer steady state.

The migration folds durable inherited constraints into ADR Consequences (Nygard pattern: "consequences become context for later ADRs"; MADR 4.0 / Y-Statements) and moves cross-tool review provenance to a CI-linted PR-description Governor Footer. PR A populates the bridge ADR with a 47-row IC classification table covering all 44 historical IC tags across 6 categories (durable-governance / durable-domain / pr-scope / superseded / historical-only / follow-up) plus a `historical_id → adr_clause → status` alias mapping. The PR template gains the Governor Footer pilot block (dual-write with the existing checkboxes); PR B adds the CI linter; PR C populates ADR 047 Consequences; PR D fixes the `/sync-guidelines` self-loop; PR E switches the active source of truth; PR F removes the legacy `tools/check_g_closure.py` after the new linter has cleanly handled at least 2 unrelated governor-changing PRs.

The PR is governor-changing because it introduces a new ADR under `docs/history/**` and edits `.github/pull_request_template.md` (Tier A and Tier B), and it must self-apply the still-current pre-ADR-047 obligation by writing this entry.

## Review Rounds

1. **Round 0 — Architecture comparison cross-review (codex CLI gpt-5.5, model_reasoning_effort=xhigh, sandbox=read-only)**
   - Target: four candidate architectures for replacing `governor-review-log/`.
     - A. Trim — keep the directory, narrow Tier matching, summarize Self-Application Proof.
     - B. Fold to ADR Consequences + PR-description footer.
     - C. Replace entirely — delete the directory, rely on GitHub PR descriptions + ADRs only.
     - D. Single chronological log (`docs/governance-log.md` 5-line append per governor-changing PR).
   - Prompt focus: operational cost / blind-spot regression risk / migration complexity / industry alignment, comparing solo-dev steady-state ergonomics.
   - Surfaced points:
     - R0.1: A scores 4/4 on operational cost (worst) and 4/4 on industry alignment (worst); ceremony continues to grow with each Tier A PR.
     - R0.2: B scores 2/4 / 2/4 / 3/4 / 1/4 on the same axes; matches industry canon (Conventional Commits + ADRs + PR descriptions).
     - R0.3: C strips repository-local cross-review trail, raising blind-spot regression risk in solo + 2-AI-tool settings (4/4 worst on that axis).
     - R0.4: D reproduces a smaller bespoke log; the marginal offline-grep advantage does not justify a fourth artefact format.
   - Final Verdict: B selected (lowest aggregate cost), with D as the strongest counter-argument acknowledged in ADR 047 Alternatives.

2. **Round 1 — Migration stress-test cross-review (codex CLI gpt-5.5, model_reasoning_effort=xhigh, sandbox=read-only)**
   - Target: a 14-step single-PR variant of B proposed in Round 0.
   - Prompt focus: 10 stress angles including IC selection bias, footer-linter-first ordering, Stop-hook-cant-verify-PR-body, self-loop persistence, bootstrapping violation, frozen-archive interaction with future ADR edits.
   - Surfaced points:
     - R1.1 (blocker): IC classification needs a taxonomy before any IC can be promoted; PR #153 vs PR #155 reuse the `IC-153-4` tag with different meanings, indicating semantic drift. Promotion without classification would baked the drift into ADR 047.
     - R1.2 (blocker): "defer the footer linter" is unsafe; Guard G regresses to text-only; closure-label drift recurs in 1~2 PRs (PR #143 history precedent).
     - R1.3 (blocker): Stop hook locally cannot read PR description body; replacement verifier must be CI-side, not local-hook.
     - R1.4 (blocker): the `/sync-guidelines` self-loop persists in B unless explicit `governor-paths.md` Exclusion lands.
     - R1.5 (blocker): the migration PR must not skip the very verifier it is replacing — bootstrapping rule says PR A writes the LAST log entry under old policy.
     - R1.6 (minor): ADR 047 alias mapping must be immutable to keep historical references resolving consistently across future ADRs.
     - R1.7 (minor): single-PR is unsafe; phased dual-write is required; at every merge boundary at least one of {old log gate, new footer linter} must remain active.
   - Outcome: 14-step variant rejected. Codex proposed a 6-PR phased dual-write sequence (PR A bridge → PR B footer linter → PR C IC promotion → PR D self-loop fix → PR E source-of-truth switch → PR F cleanup). Confidence rose from "low" (14-step) to "medium" (6-PR phased).
   - Final Verdict: minor fixes recommended → architecture B retained, migration sequence rewritten as 6 PRs codified in ADR 047 D5.

3. **Round 2 — ADR 047 design-stage cross-review (codex CLI gpt-5.5, model_reasoning_effort=xhigh, sandbox=read-only)**
   - Target: the complete ADR 047 draft authored before this entry.
   - Prompt focus: 9 scrutiny points including IC classification correctness, bootstrapping ordering coherence, D4 carve-out scope, frozen-archive vs future-ADR-edit interaction, PR E/F sequencing, Tier 1 language compliance of ADR 047 itself, missing alternatives, taxonomy completeness, phantom-row handling.
   - Surfaced points:
     - R2.1 (blocker): line 148 of the draft contained literal Korean tokens from quoting `IC-3`'s exception-token regex — `tools/check_language_policy.py` flagged the violation.
     - R2.2 (blocker): IC-8 destination field cited `superseded-by:ADR047-G24`, but `ADR047-G24` was already owned by IC-RG-2; one slot, two meanings.
     - R2.3 (blocker): D1 declares 6 categories but the table introduced a 7th (`reference`) for IC-156-7; future contributors could not apply the taxonomy without redesigning it.
     - R2.4 (minor): IC-156-5 boundary between `durable-governance` (cross-cutting style policy) and `durable-domain` (docs domain) was unclear.
     - R2.5 (minor): D5 PR A row left ambiguous whether PR A's own description must contain a Governor Footer block or only the old-policy log entry.
     - R2.6 (minor): D4 carve-out covered `project-status.md` `Last synced:` only; `/sync-guidelines` also touches `project-overview.md` and `commands.md` `Last synced:` lines.
     - R2.7 (minor): ADR 047's alias mapping needs an explicit immutability invariant — without it, future ADRs that mutate `ADR047-G*` slots silently rewrite historical IC meaning.
     - R2.8 (minor): PR F's "2 normal Tier A/B/C PRs" criterion underspecified — risk of long-tail migration if no qualifying PRs land.
     - R2.9 (minor): Alternatives section missed two natural counter-options ("amend ADR 045 in place" and "wait 2~4 weeks").
     - R2.10 (minor): IC-RG-6/7/8 phantom rows mislabelled as `superseded`; correct treatment is footnote, not table row.
   - Outcome: 3 blockers + 7 minor concerns all addressed in the draft this entry accompanies.
   - Final Verdict: block merge → after fixes → minor fixes recommended → merge-ready.

## Inherited Constraints

This is the LAST entry written under the pre-ADR-047 obligation. From PR B onward, durable-governance constraints are recorded in ADR 047 Consequences as `ADR047-G*` slots (PR C populates them); the cross-tool review trail moves to the PR-description Governor Footer.

This PR introduces no net-new IC tags. It carries forward all 44 existing tags via the IC Classification Table in [ADR 047](../../047-governor-review-provenance-consolidation.md) `### IC Classification Table`. The mapping is alias-only — no semantic change to any historical IC at PR A merge time.

The new `ADR047-G*` slot bodies will be authored in PR C; this PR only records the mapping skeleton.

## Self-Application Proof

PR A satisfies the pre-ADR-047 verifier set:

1. **Cross-tool review trail**: 3 rounds of Codex CLI `gpt-5.5 --sandbox read-only --skip-git-repo-check` with `model_reasoning_effort=xhigh`, captured in the Review Rounds section above. Final Verdict for the merged PR: merge-ready after applying R2.1~R2.10 fixes.
2. **Governor-changing PR template Section**: filled in the PR description with all checkboxes ticked.
3. **R-point closure discipline (Guard G)**: every R-point above closes as `Fixed`, `Deferred-with-rationale`, or `Rejected` (see R-points Closure Table below).
4. **Tier 1 language compliance**: `python3 tools/check_language_policy.py docs/history/047-governor-review-provenance-consolidation.md` returns 0 violations after R2.1 fix.
5. **G-closure linter compliance**: `python3 tools/check_g_closure.py` (current pre-merge linter) passes on this entry.
6. **PR A also writes a Governor Footer block** in its own PR description (D5 row PR A). Documentation-only at PR A — no CI linter exists yet (PR B introduces it). This dual-write seeds the format reviewers will lint from PR B onward.

### Findings

None remaining at merge candidate state. All R0/R1/R2 blockers and minor concerns have been addressed in either ADR 047, the PR template, or this entry.

### Drift Candidates

None introduced by PR A. PR A introduces *new* policy (ADR 047) which itself constitutes governor-changing scope, but does not surface drift in existing shared rule sources beyond what ADR 047 supersedes.

### Sync Required

false — the bridge ADR documents what is being changed; PR E performs the actual `AGENTS.md` / `target-operating-model.md` / `governor-paths.md` / `drift-checklist.md` / `harness-asset-matrix.md` / `migration-strategy.md` / 4 review skill docs / Stop hook source-of-truth switch.

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 0 | R0.1: A scores 4/4 operational cost / 4/4 industry alignment | Fixed | A rejected; B selected. ADR 047 Alternatives section records the rejection. |
| Round 0 | R0.2: B scores best on aggregate (2/2/3/1) | Fixed | B selected as the recommended architecture; codified as ADR 047 D2/D3/D5. |
| Round 0 | R0.3: C strips repository-local cross-review trail | Fixed | C rejected. ADR 047 Alternatives explains the blind-spot regression risk in solo + 2-AI-tool settings. |
| Round 0 | R0.4: D adds a fourth artefact format | Fixed | D rejected. ADR 047 Alternatives records the marginal offline-grep advantage as not sufficient. |
| Round 1 | R1.1: IC classification taxonomy required before promotion | Fixed | ADR 047 D1 adds the 6-category taxonomy; the IC Classification Table classifies all 44 historical IC tags before any promotion happens in PR C. |
| Round 1 | R1.2: footer linter cannot be deferred | Fixed | ADR 047 D5 places the footer linter in PR B (immediately after the bridge), well before PR E switches the active source of truth. |
| Round 1 | R1.3: Stop hook cannot verify PR description body | Fixed | ADR 047 D2 specifies the new verifier as a CI workflow (`governor-footer-lint.yml`), not the local Stop hook. PR E rewords the Stop hook reminder accordingly. |
| Round 1 | R1.4: `/sync-guidelines` self-loop persists in B | Fixed | ADR 047 D4 adds an explicit Exclusion in `governor-paths.md` (PR D), covering `Last synced:` lines on `project-status.md` / `project-overview.md` / `commands.md` plus the `Recent Major Changes` table. |
| Round 1 | R1.5: bootstrapping rule — migration PR must self-apply old verifier | Fixed | PR A writes this entry under the old `governor-review-log/` obligation. The new policy applies from PR B. |
| Round 1 | R1.6: alias mapping immutability | Fixed | ADR 047 D3 + IC Classification Table notes section explicitly state `ADR047-G*` bodies are write-once; future supersession creates new slots, never mutating existing ones. |
| Round 1 | R1.7: single PR unsafe; phased dual-write required | Fixed | ADR 047 D5 codifies the 6-PR phased sequence with the at-least-one-verifier invariant. |
| Round 2 | R2.1: line 148 Tier 1 language violation | Fixed | IC-3 row no longer inlines the exception-token regex; references AGENTS.md § Default Coding Flow → Exception Tokens instead. `tools/check_language_policy.py` returns 0 violations. |
| Round 2 | R2.2: IC-8 destination collides with IC-RG-2's slot | Fixed | IC-8 destination changed to `superseded-by:ADR047-D2`. IC-RG-2 retains `ADR047-G24` exclusively. |
| Round 2 | R2.3: D1 taxonomy violated by 7th category `reference` | Fixed | IC-156-7 reclassified as `historical-only`. IC-RG-6/7/8 phantom rows moved out of the table to a "Phantom citations (informational)" footnote. Table now uses only 5 of the 6 declared categories (follow-up unused, which is allowed by D1). |
| Round 2 | R2.4: IC-156-5 governance/domain boundary unclear | Fixed | IC-156-5 reclassified as `durable-domain` → `domain:docs`. Description updated to note the existing `test_docs_selector_returns_html` is the domain-bound enforcement. |
| Round 2 | R2.5: PR A footer pilot ambiguity | Fixed | D5 PR A row clarified: PR A fills both old "Governor-Changing PR" checklist and the new Governor Footer pilot block; footer is documentation-only at this stage. |
| Round 2 | R2.6: D4 carve-out incomplete | Fixed | D4 expanded to cover `Last synced:` lines on `project-overview.md` and `commands.md` in addition to `project-status.md`. README Index table explicitly excluded from the carve-out. |
| Round 2 | R2.7: alias immutability invariant missing | Fixed | D3 plus IC Classification Table notes both state `ADR047-G*` slots are write-once. |
| Round 2 | R2.8: PR F validation criterion underspecified | Fixed | D5 PR F clarified — at least 2 governor-changing PRs whose primary work is not the migration itself, plus a 30-day soak-window allowance. |
| Round 2 | R2.9: missing Alternatives — ADR 045 amend, wait/observe | Fixed | Alternatives Considered now includes E (amend ADR 045 in place) and F (wait 2~4 weeks). |
| Round 2 | R2.10: phantom rows mislabelled as `superseded` | Fixed | IC-RG-6/7/8 moved out of the IC table to a "Phantom citations (informational)" footnote section after the table. |
| Round 3 | R158-FV-1: Footer `touched-adr-consequences` placeholder grammar inconsistent (`ADR-NNN-CY` vs `ADR047-G{N}`) | Fixed | PR template footer placeholder + ADR 047 D2 example + field guidance all unified on `ADR{NNN}-G{N}` form (e.g. `ADR047-G3`). PR B's CI linter grammar will accept this single canonical form. |
