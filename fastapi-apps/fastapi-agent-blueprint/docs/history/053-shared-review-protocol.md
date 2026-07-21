# 053. Shared Review Protocol

- Status: Accepted
- Date: 2026-07-04
- Related issue: #274 (PR #275)
- Builds on (does not supersede): ADR [047](047-governor-review-provenance-consolidation.md) and ADR [048](048-independent-review-generalization.md). 047/048 generalize the review *modality and provenance* (Governor Footer, reviewer modes) of ADR [045](045-hybrid-harness-target-architecture.md) Pillar 2; **053 changes the review *substance/contract*** the skills apply. Related lineage, not a supersession.
- Amended by: ADR [055](055-summary-finding-ledger.md) — adds the Summary Finding Ledger contract (out-of-diff finding tracking, complete carry-forward, verdict / completion-gate effects) to the protocol's §5 posting rules.
- Note: this ADR records the decision behind `docs/ai/shared/review-protocol.md`. It documents *why* that protocol exists; it does **not** restate its rules.

## Summary

The three review skills (`review-pr` / `review-architecture` / `security-review`) each embedded their own review contract, which drifted. To fix the divergence at the source, #274 authors **one shared anchor** — `docs/ai/shared/review-protocol.md` — that all three skills reference while staying standalone (**never skill-calls-skill**). The protocol defines concern-based review dimensions, an anti-hallucination finding-basis rule, a deterministic output + GitHub-posting contract, and an intent/PASS verdict. `review-pr` becomes the PR-scoped single entry point; the other two are audit-only.

## Background

### Trigger

Three embedded per-skill contracts drifted into three concrete owner pains (#274):

1. **Non-deterministic output** — inline line-comments vs. a single summary was decided ad hoc, so the same PR reviewed twice produced different comment sets.
2. **File-location review categories** (`domain/`, `application/`, `infrastructure/`, `interface/`) instead of concern-based ones, so "which points am I reviewing against?" had no crisp answer.
3. **A finding-basis rule that forbade correctness findings** — `review-pr`'s old "only shared rule sources may create findings" (AGENTS.md / project-dna / the two checklists) *structurally* banned evidence-grounded correctness / regression / side-effect findings. The review could certify architecture compliance but not "does it work, is it stable, does it break anything" — the thing a reviewer most needs.

The old output contract also mixed review *state* into severity — `[OK]` / `[SKIP]` records sat inside `Findings` next to real issues, making `Findings` non-actionable — and had no notion of "did it pass against a stated intent", so a clean architecture audit could read as a behavior `PASS`.

### Decision type

**Experience-based correction**, not upfront design: the skills had shipped and been used; the three gaps are observed drift/inadequacy of the duplicated contracts. Same correction pattern as ADR 047 (right-sizing after 045) and ADR 048 (generalizing after footer-era data) — 053 is the substance/contract counterpart in that lineage. The design was round-0 cross-reviewed by codex (gpt-5.5, xhigh; verdict "sound with adjustments"); protocol rounds 1–2 fixed 6 R-points and a whole-set review fixed 2 more (8 total, 0 deferred, 0 rejected — PR #275 Governor Footer).

## Problem

Each review skill independently defined **what** to review, **what** may become a finding, **how** it is reported, and **whether** a change passes. Because that contract was duplicated three ways it drifted and left three structural gaps: non-deterministic posting; a file-location taxonomy that could not name a concern; and a finding-basis rule that made evidence-grounded correctness/regression/stability/contract findings literally out-of-contract. The result was reviews that were inconsistent run-to-run and blind to the failure modes a PR reviewer most needs to catch.

## Alternatives Considered

### A. Keep three embedded per-skill contracts (status quo)

Leave each skill defining its own contract and patch gaps skill-by-skill. **Rejected:** this *is* the source of the drift — three copies diverged, producing the non-determinism and the correctness blind spot. Patching each separately re-opens the same divergence over time.

### B. Skill-calls-skill orchestration

Make `review-pr` a god-skill that invokes `review-architecture` / `security-review` at runtime to assemble a unified PR review. **Rejected** (explicit #274 non-goal, validated by codex round-0): orchestration re-introduces exactly the cross-skill coupling and inconsistency being fixed. The rule is **skill-depends-on-protocol-never-on-another-skill's-body**; recursion guards in each skill body also forbid it.

### C. Adopt the built-in generic `/code-review` as the authoritative PR gate

Use Claude Code's built-in skill as the correctness gate instead of a project-specific protocol. **Rejected:** the built-in is **not project-aware** — it does not know the layering rules, DTO/VO roles, DI conventions, or the checklists. It may serve as an optional extra `CORR` lens but is never an authoritative source of findings under this protocol.

### D. Amend AGENTS.md / the checklists in place instead of a new shared doc *(inferred alternative)*

Fold dimensions, finding-basis, and posting rules into existing canonical files rather than creating a new doc. **Rejected:** the review contract is a distinct concern (dimensions + basis + output + verdict + posting) that all three skills consume; spreading it across the checklists would recreate the fragmentation, and AGENTS.md keeps the F/G/H/I guards + Effect Answer canonical (the protocol references them, §6 pointer-only). A single registered anchor doc is the deterministic single source of truth. *(This option is inferred from the doc's structure and the harness-asset-matrix "why it exists" note; #274/#275 do not record it as an explicitly weighed option.)*

## Decision

Author one shared anchor, `docs/ai/shared/review-protocol.md`, that all three review skills reference; keep the skills standalone. The protocol defines:

- **D1 — Seven concern-based dimensions with stable IDs:** `CORR`, `REG`, `STAB`, `CONTRACT`, `ARCH`, `SEC`, `GOV` — replacing file-location categories (now a navigation aid only). `ARCH`/`SEC`/`GOV` are **rule-grounded** (must cite a checklist / AGENTS.md / governor-paths.md); `CORR`/`REG`/`STAB`/`CONTRACT` are **evidence-grounded**.
- **D2 — Finding-basis anti-hallucination rule:** every finding carries `basis: <rule-source | diff-evidence | contract-evidence | test-evidence | runtime-evidence>` with a cited anchor. No basis → it is a `Question` in `Next Actions`, not a finding. An absent test is a finding only when tied to a changed contract, a concrete regression risk, or a checklist rule — never "untested, therefore a finding."
- **D3 — Output contract:** splits `Findings` (OPEN only) from a new `Coverage` section (OK/SKIP), removing the old self-contradiction, and requires the `Effect Answer` field (the Guard H enforcement point).
- **D4 — Intent/PASS verdict:** `PASS` / `FAIL` / `CANNOT CERTIFY (intent evidence missing)` / `N/A (audit-only)`.
- **D5 — Deterministic GitHub posting:** inline vs. summary decided by whether a finding's `file:line` falls inside the diff hunks (fallback to summary, never dropped); a stable **finding-key** drives update-vs-new-vs-resolve on re-review; the review action is first-match-wins over verdict + open-findings + sync-state (FAIL→request-changes / CANNOT CERTIFY→comment / any OPEN or Sync Required→comment / else→approve).
- **D6 — Skill roles:** `review-pr` is the PR-scoped **single entry point** that applies the whole protocol then decides drift + posting, and is the only skill emitting a behavior verdict; `review-architecture` (ARCH in depth) and `security-review` (SEC in depth, with a feature-freshness preflight) are **audit-only** (`Verdict: N/A`). No `src/` runtime change — docs/harness only.

## Rationale

The three gaps share one root cause — the contract was duplicated per skill and drifted — so the architectural fix is to make the contract a **single shared source**, not patch three copies.

- **Concern-based dimensions** answer "which points am I reviewing against?" crisply, because a defect is intrinsically about correctness/regression/…/governance, not about which folder the file lives in. File location is orthogonal (a `CORR` bug can live in `interface/`, an `ARCH` violation in `domain/`), so it could never be the review taxonomy.
- **The finding-basis rule preserves the old principle's genuine intent** (stop hallucinated/taste findings — "no finding without a declared basis") while removing its overreach: the old wording achieved anti-hallucination by whitelisting only rule-source findings, which as a side effect banned the entire evidence-grounded correctness family. Splitting basis into rule-source (for `ARCH`/`SEC`/`GOV`) vs. diff/contract/test/runtime evidence (for `CORR`/`REG`/`STAB`/`CONTRACT`) keeps hallucination out **and** lets an evidence-backed correctness finding be raised.
- **Verdict-driven deterministic posting** matters because the same PR reviewed twice must land the same comment set; making inline-vs-summary a mechanical function of "is the `file:line` inside a diff hunk" plus a stable finding-key, and the GitHub action a first-match-wins function, removes reviewer discretion as a source of run-to-run variance.
- **`review-pr` is the single PR entry point** because a PR review needs all seven dimensions together *plus* a behavior PASS/FAIL, whereas architecture/security audits are single-dimension, non-PR, and have no behavior intent to certify.
- **Skill-depends-on-protocol-never-on-another-skill** is load-bearing: orchestration would re-introduce exactly the coupling and inconsistency the ADR set out to remove.

## Consequences

### Durable constraints

**ADR053-G1 (durable-governance)** — The review contract (dimensions, finding basis, output/coverage sections, intent/PASS verdict, posting rules) is canonical in `review-protocol.md`. The three review skills and their `.claude/` + `.agents/` mirrors **reference** it; they do not redefine any of it, and they never depend on each other's skill bodies. The F/G/H/I guards and `Effect Answer` stay canonical in AGENTS.md — the protocol is pointer-only for those (§6).

**ADR053-G2 (durable-governance)** — Every finding declares a `basis` and cites an anchor; a concern without a valid basis is a `Question`, not a finding. `ARCH`/`SEC`/`GOV` findings without a citable shared-rule section are invalid (downgrade to a Drift Candidate if the rule is missing).

**ADR053-G3 (durable-governance)** — GitHub posting is deterministic: inline-vs-summary by diff-hunk membership, a stable finding-key for the update/new/resolve lifecycle, and a first-match-wins verdict→action map. The protocol **reports** merge-gate/thread state; it does **not** automate merge or thread resolution.

### Enforcement gaps (explicit disclosure)

- **Honor-system, not linted:** nothing verifies that a finding actually carries a valid `basis`, that `OK`/`SKIP` were not smuggled into `Findings`, or that the intent/PASS verdict was applied — correctness relies on the skill following the protocol (the same class of gap ADR 048 disclosed for self-structured checklist evidence).
- **Broader findings raise the reviewer-discipline bar:** a `CORR`/`REG` finding without cited diff/test/runtime evidence must be demoted to a `Question`, and mis-tagging `basis` is now a possible failure mode that did not exist when only rule-source findings were allowed.
- **Deferred extension point:** the optional project-aware **sub-agent fan-out** (protocol §8) is deferred, so heavy multi-domain / concurrency reviews get no built-in escalation path yet. This is a documented follow-up, not an omission.
- **A fourth Tier-1 governor doc to keep in sync** — `review-protocol.md` joins AGENTS.md and the two checklists; editing it is English-only and requires a Governor Footer + independent review.

### Where the rules already live (point here, do not re-document)

- `docs/ai/shared/review-protocol.md` — the protocol itself (§1 dimensions, §2 basis, §3 output, §4 verdict, §5 posting).
- AGENTS.md § Reasoning-Level Consistency Guards — F/G/H/I + `Effect Answer` (canonical; protocol §6 is pointer-only).
- `architecture-review-checklist.md` (10 categories) and `security-checklist.md` (12 categories) — the `ARCH`/`SEC` rule sources.
- `governor-paths.md` — the `GOV` rule source / Tier classification.
- `harness-asset-matrix.md` — the asset-level record for `review-protocol.md`.
- PR #275 `## Governor Footer` — the cross-tool review provenance (ADR 047 D2 audit-trail home, not the ADR).

### Self-check

- [x] Addresses the root cause (a per-skill contract duplicated three ways) rather than the symptoms.
- [x] Right-sized: one shared anchor + standalone skills, no orchestration engine.
- [x] A reader in 6 months learns why dimensions are concern-based, why the old rule-source-only rule was replaced, and why posting is deterministic.
- [x] Honest about relationship to 047/048 (builds-on, not supersedes), the inferred alternative D, and the honor-system enforcement gaps.
