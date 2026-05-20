# 047. Governor-Review Provenance Consolidation — ADR Consequences + PR Footer

- Status: Proposed
- Date: 2026-05-01
- Related issue: [#157](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/157)
- Related PRs: PR A (this PR — bridge + footer pilot + IC classification), PR B (footer CI linter), PR C (durable IC promotion), PR D (`/sync-guidelines` self-loop fix), PR E (active source-of-truth switch), PR F (cleanup)
- Supersedes (partial): ADR [045](045-hybrid-harness-target-architecture.md) Pillars 4 and 7 — the per-PR `governor-review-log/` archive obligation and Self-Application Proof archival format. The cross-tool review trigger itself (Tier A/B/C glob) and the rest of ADR 045 remain in force.
- Constraints: ADR [040](040-rag-as-reusable-pattern.md), [042](042-optional-infrastructure-di-pattern.md), [043](043-responsibility-driven-refactor.md), [045](045-hybrid-harness-target-architecture.md) — architecture / DI / responsibility / process-governor layers below this ADR are immutable for this change.

## Summary

This ADR right-sizes the cross-tool review provenance system introduced 5 days ago by ADR 045 / PR #125. The build-out trail (Phase 1~5) was load-bearing — it caught real bugs and produced inherited constraints (IC-1~IC-16) that genuinely propagated across follow-up PRs. The surrounding permanent infrastructure — per-PR archive obligation, lifetime retention, broad Tier matching that creates a `/sync-guidelines` self-loop, and a Self-Application Proof full-output archive section — is over-engineered for a solo-developer steady state.

Six decisions:

1. **D1 — IC durability classification** added as a 6-category taxonomy (`durable-governance` / `durable-domain` / `pr-scope` / `superseded` / `historical-only` / `follow-up`) so future ICs are sorted by lifetime at declaration time, not retroactively.
2. **D2 — Cross-tool review provenance moves to PR-description Governor Footer**, machine-parseable and CI-linted (PR B). Existing `governor-review-log/` becomes a frozen historical archive.
3. **D3 — Durable inherited constraints move to ADR Consequences sections** (Nygard pattern: "consequences become context for later ADRs"; MADR 4.0 Consequences slot). Forty-four historical IC tags receive the classification + new-home mapping below.
4. **D4 — `/sync-guidelines` cosmetic edits** (`Last synced:` line + `Recent Major Changes` table rows in `.claude/rules/project-status.md`) are excluded from governor-changing classification (PR D), breaking the self-loop where every feature PR's closure step pulled it into governor-changing.
5. **D5 — Phased multi-PR migration** with dual-write guarantee: at any merge, at least one of {old log gate, new footer linter} is active.
6. **D6 — Existing 18 entries are preserved as a closed historical archive.** No retroactive editing. The Korean-provenance carve-out in `tools/check_language_policy.py` and `LOCALE_DATA_FILES` remain in force for the frozen archive.

## Background

ADR 045 (PR #125, 2026-04-26) introduced a hybrid local process governor. Pillar 4 created `docs/ai/shared/governor-review-log/` as a per-PR permanent archive of cross-tool review trails. Pillar 7 added a Stop-hook completion gate that emits a reminder when a Tier A/B/C PR has no matching log entry.

Five days later, the directory holds 18 entries, of which 14 are governance-meta self-references from the harness build-out itself (Phase 1~5, language policy, locale, reasoning guards, G linter). The remaining 4 are feature PRs (#152 / #153 / #155 / #156) that were pulled into governor-changing classification not by their primary changes but by their own `/sync-guidelines` closure step editing `.claude/rules/project-status.md` (Tier A). PR #156's entry [explicitly notes this](archive/governor-review-log/pr-156-docs-selector-revamp-handoff.md) self-loop.

A two-round audit was commissioned:

- **Round 1 audit** (Codex CLI gpt-5.5, model_reasoning_effort=xhigh, sandbox=read-only). Compared four candidate architectures: A (trim) / B (fold to ADR + PR footer) / C (replace entirely) / D (single chronological log). B scored best on operational cost (2/4), industry alignment (1/4), and migration complexity (3/4); A and D were dominated; C was flagged for blind-spot regression risk in solo + 2-AI-tool settings.
- **Round 2 stress-test** (Codex CLI gpt-5.5, xhigh, sandbox=read-only). Stress-tested the 14-step single-PR migration sequence proposed in Round 1. Five blockers surfaced: IC selection bias (semantic drift between PR #153 and PR #155 over `IC-153-4`); footer linter deferral risk (Guard G regresses to text-only); Stop hook cannot verify PR description body locally; `/sync-guidelines` self-loop persists in B without explicit carve-out; bootstrapping violation if migration PR skips the very verifier it removes. Confidence rating dropped from "B is correct" to **"B is correct but the original 14-step sequence cannot ship as one PR"**. Codex's revised 6-PR phased dual-write sequence raises confidence to medium.

Industry research (general-purpose agent, web search) confirmed Codex's direction: the canonical lightweight stack is **Conventional Commits + PR descriptions + ADRs in `docs/decisions/`** with **Nygard's chaining mechanic** ("consequences become context for later ADRs"). MADR 4.0 and Y-Statements formalize the `Consequences` / `accepting that` slot future decisions inherit. No public AI-assisted dev tooling (Cursor `.cursorrules`, Aider chat history, Continue config, AGENTS.md ecosystem 2,500+ repos) ships a permanent per-PR cross-review trail; the academic cross-AI-review work (AutoReview FSE 2025; arxiv 2404.18496) does not persist trails per PR either. The absence is itself evidence the steady-state cost is not worth paying.

The Phase 1~5 build-out was an exception that made temporary sense: 5 days of harness-on-harness construction with cross-tool review challenging every step, and IC carry-forward from PR #125 → #130 was actively used. That phase ended at PR #130 ("Hybrid Harness v1 closure"). The system that supported the build-out was retained as if it were the steady state. ADR 047 acknowledges this and reverts to the canonical lightweight stack for steady state, while preserving the build-out evidence.

## Decision

### D1 — IC durability classification

Six categories. Every IC (existing or future) is classified at declaration time, not retroactively guessed:

| Classification | Definition | Lifetime | New home |
|---|---|---|---|
| `durable-governance` | Process / harness rule that future PRs must respect (e.g. precedence ordering, hook adapter spec, no-inline-redeclaration boundaries, language policy, marker lifecycle, reasoning guards). | Repository lifetime, until superseded by another ADR. | ADR Consequences (this ADR or a successor governance ADR). |
| `durable-domain` | Code / data invariant in the running system that a domain or cross-cutting test enforces (e.g. refresh-token hashing, JWT claim shape, session storage scope, selector renderer contract). | Repository lifetime, until refactored. | `docs/ai/shared/project-dna.md`, the relevant domain document, or a domain-specific ADR. |
| `pr-scope` | Self-imposed contract of a single PR ("this PR keeps env-var admin", "minimal RBAC for this PR"). Loses meaning the moment a follow-up PR ships. | One PR. | Historical-only — stays in the frozen archive entry; not promoted. |
| `superseded` | A later IC redefines or replaces this one. May or may not have been forward-looking when declared. | Until superseded. | Historical-only with a "superseded by ICX" note in the mapping table below. |
| `historical-only` | Records the build-out process itself; not intended to bind future work (e.g. Phase 4 marker lifecycle resolution closing a Phase 2 deferral). | Build-out artifact. | Frozen archive only. |
| `follow-up` | Forward-looking work delegated to a separate issue or PR. | Until the follow-up ships. | Cited in the follow-up issue body, then closed when that work merges. |

**Forward rule.** New ICs emerging from cross-tool review of a Tier A/B/C PR must be classified at PR time. `durable-governance` ICs go directly into the ADR being created or amended; `durable-domain` ICs go into project-dna or the domain doc; `pr-scope` ICs may live in the PR description Governor Footer's "PR-scope notes" line and are not inherited.

### D2 — Cross-tool review provenance moves to PR-description Governor Footer

PR B introduces `tools/check_governor_footer.py` plus `.github/workflows/governor-footer-lint.yml`. The footer block is machine-parseable:

```
## Governor Footer
- trigger: yes/no
- reviewer: codex-cli/claude-code/...
- rounds: N
- r-points-fixed: N
- r-points-deferred: N
- r-points-rejected: N
- touched-adr-consequences: ADR{NNN}-G{N}, ADR{NNN}-G{N} / none
- pr-scope-notes: <one-line summary or "none">
- final-verdict: merge-ready/minor-fixes/needs-reinforcement/block
- links: <PR url>, <prior-log url or "n/a">
```

Closure-category vocabulary is preserved exactly: `Fixed`, `Deferred-with-rationale`, `Rejected` (Guard G remains in force; AGENTS.md § Reasoning-Level Consistency Guards body is unchanged). The CI linter validates the block shape; non-canonical labels fail the build.

The Stop-hook completion-gate (PR E step 9) drops the "missing governor-review-log entry" reminder and instead emits "PR description Governor Footer required; verified in CI" — local hook does not pretend to validate PR body.

### D3 — Durable inherited constraints move to ADR Consequences

PR C populates the **Consequences** section of this ADR with promoted `durable-governance` IC bodies (renamed `ADR047-G1` … `ADR047-GNN`). `durable-domain` ICs are added to `docs/ai/shared/project-dna.md` or relevant domain docs. The historical-id mapping (§ "IC Classification Table" below) preserves the old IC tags so existing log-entry prose like `IC-1 ~ IC-16` does not dangle — the table is an alias map.

**Alias immutability invariant.** `ADR047-G*` slot bodies are write-once after PR C lands them. Future ADRs that change an underlying constraint create a new `ADR(N+1)-G*` slot and update the alias table to add `superseded-by:ADR(N+1)-G*` against the historical IC row. They never mutate the existing `ADR047-G*` body in place. This guarantees that when a frozen archive entry like pr-130 cites "IC-1 ~ IC-16", a reader following the alias table back to the constraints in force at pr-130 merge time gets a consistent snapshot, not the silently-updated current version.

### D4 — `/sync-guidelines` cosmetic edits exempt from governor-changing

PR D adds an explicit Exclusion to `governor-paths.md` covering the three `.claude/rules/*.md` files that `/sync-guidelines` routinely refreshes with timestamp-only content:

```
- /sync-guidelines closure step edits limited to:
  - .claude/rules/project-status.md `Last synced:` line + `Recent Major Changes` table rows
  - .claude/rules/project-overview.md `Last synced:` line
  - .claude/rules/commands.md `Last synced:` line
  do NOT trigger governor-changing classification.
```

The carve-out covers only the `Last synced:` timestamp line on `project-overview.md` and `commands.md` — semantic edits (new sections, regenerated content) still trigger governor-changing. The `governor-review-log/README.md` Index table is **not** in this carve-out: after PR E it stops growing (closed historical archive), so future Index edits are themselves governance changes worth reviewing. The `/sync-guidelines` skill emits a structured Tier-classification line on closure, so reviewers can verify the exemption applies. `tests/unit/agents_shared/test_completion_gate.py` adds a regression test for each path covered by the carve-out.

### D5 — Phased multi-PR migration with dual-write guarantee

Six PRs, in order. **Invariant: at any merge boundary, at least one of {old `governor-review-log/` artefact requirement, new Governor Footer linter} is active.** No "naked" interval.

| PR | Scope | Active verifier at merge |
|---|---|---|
| **PR A (this PR)** | Bridge ADR 047 (Status: Accepted after merge), IC Classification Table populated for all 44 historical IC tags, PR template Governor Footer pilot section added (dual-write: old checkboxes retained), LAST `governor-review-log/pr-{N}-bridge-adr-047.md` written under old policy (bootstrapping). PR A's own description **fills both** the old "Governor-Changing PR" checklist section and the new Governor Footer pilot block — the footer is documentation only at this point (no CI linter yet); it is captured to demonstrate the new shape and to seed the format reviewers will lint in PR B. | Old log gate (active). |
| **PR B** | `tools/check_governor_footer.py` + `.github/workflows/governor-footer-lint.yml` + tests. PR body Governor Footer is now CI-validated. PR B itself writes both old log entry and new footer (dual-write). | Old log gate + new footer linter (both active). |
| **PR C** | Promote `durable-governance` IC bodies into this ADR's Consequences section (D3). `durable-domain` ICs into project-dna or domain docs. PR-scope / superseded / historical-only stay in frozen archive. | Old log gate + new footer linter. |
| **PR D** | Self-loop fix in `governor-paths.md` Exclusions + `/sync-guidelines` Tier-classification line + regression test. | Old log gate + new footer linter. |
| **PR E** | Switch active source of truth: AGENTS.md / target-operating-model.md / governor-paths.md (Required artefacts) / drift-checklist.md (§1D) / harness-asset-matrix.md (reclassify) / migration-strategy.md (Phase 4 acceptance) / 4 review skill docs / PR template (drop old checkboxes) / Stop hook reminder rewording / `governor-review-log/README.md` ("closed historical archive" banner). | New footer linter only (old log gate retired). |
| **PR F** | Cleanup: remove `tools/check_g_closure.py` + pre-commit hook + `tests/unit/agents_shared/test_g_closure.py`. Simplify `tools/check_language_policy.py::TOKEN_LITERALS_BY_FILE` (frozen-archive provenance prefixes + `LOCALE_DATA_FILES` are kept). | New footer linter; gates apply only to active surfaces. |

PR F runs only after the new footer linter has cleanly handled **at least 2 governor-changing PRs whose primary work is not the migration itself** (i.e. PRs that touch Tier A/B/C as their main purpose, not just `/sync-guidelines` closure or PR A~E follow-ups). Each of those PRs must merge with the linter green — no skipped check, no force-merge. If 30 days pass after PR E merge without 2 such qualifying PRs landing, PR F may proceed under a "soak-window-met" allowance, recorded explicitly in PR F's own Governor Footer.

### D6 — Existing 18 entries preserved as closed historical archive

`governor-review-log/README.md` gains a banner at the top after PR E:

> **Closed historical archive.** No new entries after PR #{N} (ADR 047). The 18 entries below document the Phase 1~5 build-out of the hybrid harness governance system. Cross-tool review provenance for new PRs lives in the PR description's `## Governor Footer` block (see ADR 047 D2) and durable inherited constraints live in ADR Consequences (D3).

The directory remains under Tier 1 language policy. The Korean-provenance prefix carve-out (`> Original user/owner statement (ko, verbatim):` etc.) and `LOCALE_DATA_FILES` remain in force. Future appendices to existing entries — for example, a correction note discovered later — must be **append-only English errata under the entry's last section** with explicit `Errata YYYY-MM-DD:` heading; original Korean provenance text is never edited or deleted.

## Consequences

**Positive**

- Steady-state operational cost drops sharply. Tier A/B/C PRs no longer require a bespoke per-PR archive file or README index update; the PR description's Governor Footer carries the entire trail and is CI-validated.
- Industry alignment improves from 4/4 (current bespoke archive) to 1/4 (Nygard ADR Consequences + Conventional Commits + PR description). Future contributors find a familiar shape.
- Self-loop is broken at the `governor-paths.md` Exclusions layer (D4); future feature PRs are not pulled into governor-changing classification by their own `/sync-guidelines` closure step.
- Build-out evidence is preserved (18 entries frozen) so the cross-tool review insight that produced IC-1~IC-16 does not disappear.
- Phased dual-write migration (D5) is rollback-safe — every intermediate state retains either the old or new verifier.

**Negative**

- One-time migration cost across 6 PRs touching most Tier A files. PR E in particular is wide (~10 cross-document edits), but each is a small mechanical change.
- Forty-four historical IC tags must be classified in PR A; some borderline calls (e.g. `IC-153-4` semantic drift between PR #153 and PR #155) require owner judgment captured in the table notes.
- Adds ~150 lines of CI workflow + linter code in PR B that did not exist before. Mitigated by removing ~280 lines of `tools/check_g_closure.py` in PR F.
- Cross-tool review provenance now lives in PR description, which is GitHub-only (not in `git clone` output). Some readers prefer the offline grep affordance of in-repo files; the trade-off is explicit.

**Neutral**

- The cross-tool review obligation itself (Tier A/B/C trigger → Codex review → R-point closure) is unchanged. Only the capture location moves.
- Existing 18 entries continue to satisfy `tools/check_g_closure.py` semantics until PR F. After PR F, they are read-only archive material.

### Durable Governance Constraints (ADR047-G1 ~ ADR047-G27)

These slots are the **canonical home** for inherited governance constraints carried forward from Phase 1~5. Each slot is the promotion of one historical IC declared in `governor-review-log/pr-*.md`; the alias mapping in the IC Classification Table below ties each `ADR047-G{N}` back to its source `IC-N`. **Slot bodies are write-once** (D3 alias-immutability invariant): future ADRs that change a constraint create a new `ADR(N+1)-G{N}` slot, never mutate an existing one.

- **ADR047-G1** — Default Coding Flow ranks **below** sandbox / approval / `.codex/rules/*` / safety hooks / Absolute Prohibitions. Escape tokens never lift any of these. (From IC-1, PR #125.)
- **ADR047-G2** — Each migration phase splits *shared policy* from *Claude adapter* and *Codex adapter*. The two adapters are not symmetric: Codex `PostToolUse` matcher is `^Bash$` only and does NOT see `apply_patch` / non-Bash edits. (From IC-2, PR #125.)
- **ADR047-G3** — Exception-token regex canonical form lives in `AGENTS.md` § Default Coding Flow → Exception Tokens (post-NFKC). Never short-circuits safety / `.codex/rules` / Absolute Prohibitions. (From IC-3, PR #125.)
- **ADR047-G4** — A skill addition or change requires updating **all three wrapper layers** (`docs/ai/shared/skills/{name}.md`, `.claude/skills/{name}/SKILL.md`, `.agents/skills/{name}/SKILL.md`) with consistent information density, including the `Default Flow Position` block. (From IC-4, PR #125.)
- **ADR047-G5** — Codex verification reminders rely on **changed-files state at Stop time**, not on `PostToolUse Bash`. (From IC-5, PR #125.)
- **ADR047-G6** — Phase acceptance criteria must not reference deliverables produced by later phases. (From IC-6, PR #125.)
- **ADR047-G7** — Bucket-share denominator across the four design docs reconciles to the matrix; `.gitignore`d entries are excluded from the share denominator but recorded for completeness. (From IC-7, PR #125.)
- **ADR047-G9** — The `auto-escape: doc-only` rule does NOT apply to policy / harness docs (Tier A carve-out from `governor-paths.md`). (From IC-9, PR #125.)
- **ADR047-G10** — Trigger-glob list lives in a single canonical document — `governor-paths.md`. All consumer docs (AGENTS.md, target-operating-model, migration-strategy, drift-checklist, PR template) **link** the file, never redeclare the list. Phase 5 shared module reads the same file. Log-only backfill PRs are explicitly excluded. (From IC-10, PR #125.)
- **ADR047-G11** — Phase 2 marker schema `{matched, token, rationale_required, ts}` plus safety-block-first ordering (Codex). Phase 4 resolution: read-and-delete on Stop with 24h defensive filter. Phase 5 implementation enforced inside `.agents/shared/governor/markers.py` (lifecycle as `MarkerLifecycle` enum) + `.agents/shared/governor/safety.py` (single-entry `safe_parse_exception_token` returning `Blocked | ParsedToken`). (From IC-11, PR #126/#128.)
- **ADR047-G12** — `MarkerLifecycle` is a closed `Literal` enum (`READ_ONLY` / `READ_AND_DELETE`); future variants are guarded by `tests/unit/agents_shared/test_marker_lifecycle_exhaustive.py::test_marker_lifecycle_enum_has_exactly_known_variants`. (From IC-12, PR #128/#130.)
- **ADR047-G13** — No top-level `sys.exit` / `raise SystemExit` in shim modules under `.{claude,codex}/hooks/`. They are imported by `.codex/hooks/stop-sync-reminder.py` inside `contextlib.suppress(Exception)`, which does NOT catch `SystemExit`. Top-level exits would crash the Stop hook. Enforced by `tests/unit/agents_shared/test_fail_open.py::test_tier3_*`. (From IC-13, PR #130.)
- **ADR047-G14** — Hooks must not redeclare reminder strings, governor-paths globs, or token vocabulary inline. The shared module `.agents/shared/governor/` is the single source of truth. Enforced by `tests/unit/agents_shared/test_governor_boundary.py`. (From IC-14, PR #130.)
- **ADR047-G15** — `.agents/shared/governor/__init__.__all__` is contract. Removing a name requires a deliberate test update (failing build by default). Adding names is free. (From IC-15, PR #130.)
- **ADR047-G16** — Future governor additions belong in `.agents/shared/governor/`, not in per-tool hook scripts. Tool-specific runtime adapters (Codex session tracking, Codex `_shared.py` git utilities, the verify-log writer/reader) stay per-tool — they depend on `CODEX_THREAD_ID` or process-lifetime state that is intrinsically tool-bound. (From IC-16, PR #130.)
- **ADR047-G17** — Tier 1 paths block Korean (Hangul) prose at commit time; English is the intended writing language elsewhere. Enforced by the `tier1-language-policy` pre-commit hook plus `tests/unit/agents_shared/test_language_policy.py`. AGENTS.md § Language Policy is the canonical text. Scope today is Korean only; other CJK and encoded payloads (base64, HTML entities) are explicitly out of the checker's enforcement surface. (From IC-17, PR #132.)
- **ADR047-G18** — `governor-review-log/` Korean-provenance prefix carve-out. The three exact blockquote prefixes (`> Original user/owner statement (ko, verbatim):`, `> Original reviewer verdict (ko, verbatim):`, `> Historical Korean excerpt (ko, verbatim):`) preserve original Korean lines as provenance. The next non-blank line after each provenance line must be Hangul-free (the English normalised meaning). After ADR 047 the carve-out applies only to the frozen historical archive; new entries are not added, so this is read-only enforcement for the existing 18 entries. (From IC-18 PR #132.)
- **ADR047-G19** — No hidden Korean rationale in Tier 1 paths in line-visible forms — HTML comments, backtick-quoted attribute values, or any Korean text the line-grep checker can read. The checker intentionally does NOT decode base64 / HTML entities / other encodings today; smuggling Korean through those layers still violates the policy intent and will be removed if found, but enforcement is best-effort. (From IC-19 PR #132.)
- **ADR047-G20** — `governor.locale` may import from `governor.verify` and `governor.completion_gate`, but neither of those modules may import from `.locale`. Cycle prevention is enforced by `tests/unit/agents_shared/test_locale.py::test_no_locale_import_in_canonical_modules`. (From IC-18 PR #134, renamed to avoid collision with G18 above.)
- **ADR047-G21** — Every hook callsite of the locale resolver must combine the result with the canonical English fallback **before** any further operation (`format`, `echo`, etc.). Acceptable forms: Python `_resolve_locale_string("KEY") or KEY`; Python `_loc("KEY", "fallback text")` (positional only; keyword form rejected); Bash `_resolve_locale KEY 'fallback text'` (single-quoted to avoid `set -u` expansion). Direct `.format(...)` on the resolver result is forbidden. Enforced by `test_python_resolver_callsites_have_or_fallback` and `test_shell_resolver_callsites_have_single_quoted_fallback`. (From IC-19 PR #134, renamed to avoid collision with G19 above.)
- **ADR047-G22** — Adding a new entry to `LOCALE_DATA_FILES` requires a 5-step sync: (1) register the path in `tools/check_language_policy.py::LOCALE_DATA_FILES`; (2) add a bullet in AGENTS.md § Language Policy → Exemptions; (3) extend `tests/unit/agents_shared/test_locale.py::_EXPECTED_KEYS` if new keys are introduced; (4) drift-guard test — every key emitted from a hook must have an explicit substring or AST equality check against `_LOCALE_EN`; (5) Governor Footer entry on the introducing PR (replaces the original Step 5 "new governor-review-log entry" once PR E lands). (From IC-20, PR #134; Step 5 updated by ADR 047.)
- **ADR047-G23** — Reasoning-guard body stays in `AGENTS.md` only. Visibility surfaces (`CLAUDE.md`, `.codex/hooks/session-start.py`) carry pointers only; never duplicate the body. (From IC-RG-1, PR #143.)
- **ADR047-G24** — New reasoning guards must be sourced from a documented failure mode in the review-log, not from speculation. (From IC-RG-2, PR #143.)
- **ADR047-G25** — Reasoning-guard triggers must be narrow enough not to fire on general or exploratory questions. (From IC-RG-3, PR #143.)
- **ADR047-G26** — Guard G's closure categories are exactly three (`Fixed` / `Deferred-with-rationale` / `Rejected`). Adding a fourth category requires its own governor-changing PR with explicit rationale. (From IC-RG-4, PR #143.)
- **ADR047-G27** — By default, mechanical enforcement and text rule changes ship in separate PRs to keep review surfaces distinct. Bundling them in a single PR is acceptable when explicitly justified in the PR description and the bundled scope stays narrow enough for a single coherent review. (From IC-RG-5, PR #143.)

Numbering note: G8 is intentionally vacant. IC-8 (the original "governor-changing PR must produce a `governor-review-log/` entry" rule) is **superseded by D2** of this ADR — its replacement is the PR-description Governor Footer enforced by `tools/check_governor_footer.py` in CI, not a slot in the Consequences body. The IC Classification Table records this as `superseded-by:ADR047-D2`.

## IC Classification Table

The 44 historical IC tags from `docs/ai/shared/governor-review-log/pr-*.md` (as of 2026-05-01), classified per D1. Mapping convention: `historical_id → adr_clause_or_destination → status`.

`adr_clause_or_destination` reserves `ADR047-G{N}` slots for `durable-governance` ICs that PR C will populate this ADR's Consequences section with. `domain:project-dna` / `domain:auth` / `domain:docs` mark `durable-domain` destinations PR C will write into. `archive-only` means the tag stays only in the frozen log entry. `superseded-by:X` cites the replacing IC.

| Historical ID | Source PR | Classification | Destination | Note |
|---|---|---|---|---|
| IC-1 | #125 | durable-governance | ADR047-G1 | Default Flow precedence ranks below sandbox / approval / `.codex/rules` / safety hooks / Absolute Prohibitions. |
| IC-2 | #125 | durable-governance | ADR047-G2 | Codex `PostToolUse` matcher is `^Bash$` only and does not see `apply_patch` / non-Bash edits. |
| IC-3 | #125 | durable-governance | ADR047-G3 | Exception-token regex (canonical form in `AGENTS.md` § Default Coding Flow → Exception Tokens, post-NFKC). Never short-circuits safety / `.codex/rules` / Absolute Prohibitions. |
| IC-4 | #125 | durable-governance | ADR047-G4 | Skill addition / change requires updating all three wrapper layers. |
| IC-5 | #125 | durable-governance | ADR047-G5 | Codex verification reminders rely on changed-files state at Stop time. |
| IC-6 | #125 | durable-governance | ADR047-G6 | Phase acceptance criteria must not reference deliverables produced by later phases. |
| IC-7 | #125 | durable-governance | ADR047-G7 | Bucket-share denominator across the four design docs reconciles to the matrix; `.gitignore`d entries are excluded. |
| IC-8 | #125 | superseded | superseded-by:ADR047-D2 | Was: "governor-changing PR must produce a `governor-review-log/` entry". Replaced by ADR 047 D2 (PR Governor Footer) for new PRs. Frozen archive still satisfies the original phrasing for the 18 historical entries. |
| IC-9 | #125 | durable-governance | ADR047-G9 | The `auto-escape: doc-only` rule does NOT apply to policy / harness docs (Tier A carve-out). |
| IC-10 | #125 | durable-governance | ADR047-G10 | Trigger-glob list lives in a single canonical document — `governor-paths.md`. Consumers link, never redeclare. |
| IC-11 | #126 (resolved by #128) | durable-governance | ADR047-G11 | Phase 2 marker schema `{matched, token, rationale_required, ts}`. Read-and-delete on Stop with 24h defensive filter. |
| IC-12 | #128 / #130 | durable-governance | ADR047-G12 | `MarkerLifecycle` is a closed `Literal` enum; future variants guarded by `test_marker_lifecycle_exhaustive.py`. |
| IC-13 | #130 | durable-governance | ADR047-G13 | No top-level `sys.exit` / `raise SystemExit` in shim modules under `.{claude,codex}/hooks/`. Enforced by `test_fail_open.py::test_tier3_*`. |
| IC-14 | #130 | durable-governance | ADR047-G14 | Hooks must not redeclare reminder strings, governor-paths globs, or token vocabulary inline. Shared module is single source. Enforced by `test_governor_boundary.py`. |
| IC-15 | #130 | durable-governance | ADR047-G15 | `.agents/shared/governor/__init__.__all__` is contract — removing a name requires a deliberate test update. |
| IC-16 | #130 | durable-governance | ADR047-G16 | Future governor additions belong in `.agents/shared/governor/`, not in per-tool hook scripts. |
| IC-17 | #132 | durable-governance | ADR047-G17 | Tier 1 paths block Korean (Hangul) prose at commit time; English is the intended writing language elsewhere. Enforced by `tier1-language-policy` pre-commit hook. |
| IC-18 (PR #132) | #132 | durable-governance | ADR047-G18 | `governor-review-log/` Korean-provenance prefix carve-out (3 categories). Scope after ADR 047: applies only to the frozen historical archive; new entries are not added, so the carve-out is read-only enforcement for existing 18 entries. |
| IC-19 (PR #132) | #132 | durable-governance | ADR047-G19 | No hidden Korean rationale (HTML comments, attribute values, line-visible forms). Best-effort enforcement; encoded payloads remain out of scope. |
| IC-18 (PR #134, COLLISION) | #134 | durable-governance | ADR047-G20 | RENAME from "IC-18" — `governor.locale` may import from `governor.verify` / `governor.completion_gate` but not vice versa. Cycle prevention enforced by `test_locale.py::test_no_locale_import_in_canonical_modules`. |
| IC-19 (PR #134, COLLISION) | #134 | durable-governance | ADR047-G21 | RENAME from "IC-19" — Hook callsites of the locale resolver must combine result with English fallback before any further operation. `_resolve_locale_string("KEY") or KEY` form. Enforced by `test_python_resolver_callsites_have_or_fallback`. |
| IC-20 | #134 | durable-governance | ADR047-G22 | Adding a new entry to `LOCALE_DATA_FILES` requires a 5-step sync. Step 5 ("new governor-review-log entry") is **simplified** by ADR 047 to "PR Governor Footer entry" once PR E lands; until then the original 5-step is in force for backward compatibility. |
| IC-RG-1 | #143 | durable-governance | ADR047-G23 | Reasoning-guard body stays in AGENTS.md only; visibility surfaces carry pointers. |
| IC-RG-2 | #143 | durable-governance | ADR047-G24 | New guards must be sourced from a documented failure mode, not speculation. |
| IC-RG-3 | #143 | durable-governance | ADR047-G25 | Guard triggers must be narrow enough not to fire on general or exploratory questions. |
| IC-RG-4 | #143 | durable-governance | ADR047-G26 | G's closure categories are exactly three (`Fixed` / `Deferred-with-rationale` / `Rejected`). Adding a fourth requires its own governor-changing PR. |
| IC-RG-5 | #143 | durable-governance | ADR047-G27 | By default mechanical enforcement and text rule changes ship in separate PRs. Bundling acceptable when explicitly justified. |
| IC-153-1 | #153 | durable-domain | domain:auth (project-dna) | `auth` remains a non-CRUD domain; do not force `AuthService` into `BaseService`. |
| IC-153-2 | #153 | durable-domain | domain:auth (project-dna) | Refresh tokens are stored as keyed HMAC-SHA256 hashes plus `jti`, `user_id`, expiry, revocation timestamps. |
| IC-153-3 | #153 | durable-domain | domain:auth (project-dna) | Access tokens remain stateless for serverless compatibility. |
| IC-153-4 (PR #153 version) | #153 | pr-scope | archive-only | "This PR keeps env-var admin login; JWT/RBAC migration is follow-up". Lost meaning when PR #155 shipped JWT admin migration. Frozen-archive entry retains this text. |
| IC-153-4 (PR #155 version) | #155 (re-numbered same tag) | durable-domain | domain:auth (project-dna) | Distinct constraint reusing the same tag — JWT claim shape `sub / jti / type / iat / exp / iss / aud`. PR C must record the historical-id collision in the destination doc to avoid future readers conflating the two. |
| IC-153-5 (PR #153) | #153 | durable-domain | domain:auth (project-dna) | Existing `user` API routes are Bearer-protected; `/v1/auth/register` stays the public signup path. |
| IC-153-5 (PR #155 version) | #155 (re-numbered same tag) | superseded | superseded-by:ADR047-G17 | "Tier 1 edits are English-only and governor-review-log closure categories must be exactly Fixed/Deferred-with-rationale/Rejected" — already covered by IC-17 (G17) and IC-RG-4 (G26). |
| IC-153-6 | #153 | durable-domain | domain:auth (project-dna) | Future RBAC, rate limiting, RS256/key rotation, FastMCP auth integration must inherit this PR's JWT claim shape and refresh-token persistence unless a later ADR supersedes. |
| IC-153-7 | #153 | superseded | superseded-by:ADR047-G17 | "Tier 1 edits English-only" — already covered by IC-17 (G17). |
| IC-155-1 | #155 | durable-domain | domain:auth (project-dna) | NiceGUI admin session storage may contain only `authenticated`, `user_id`, `username`, `role`. Never tokens. |
| IC-155-2 | #155 | durable-domain | domain:auth (project-dna) | NiceGUI admin authorization is DB-role based. Non-admin and wrong-password both surface as "invalid credentials". |
| IC-155-3 | #155 | durable-domain | domain:auth (project-dna) | `ADMIN_BOOTSTRAP_*` is seed-only; never a primary login authority. |
| IC-155-4 | #155 | pr-scope | archive-only | "Minimal RBAC for this PR is limited to `user.role` admin authorization" — follow-up may extend. |
| IC-156-1 | #156 (in flight) | durable-domain | domain:docs | Selector renderer is a single `_render_selector` helper; theme toggle / FOUC / aria belong to production surface. |
| IC-156-2 | #156 (in flight) | durable-domain | domain:docs | `DOCS_CARDS` and `_handoff_cards()` carry an `icon` field with `.get("icon", "")` fallback. |
| IC-156-3 | #156 (in flight) | durable-domain | domain:docs | `kind` discrimination (`primary` / `secondary`) is the canonical Recommended-vs-rest hierarchy carrier. |
| IC-156-4 | #156 (in flight) | durable-domain | domain:docs | `/openapi-download.json` is dev-only; exposing in stg/prod requires an ADR. `TestDocsUrlGating` is the regression guard. |
| IC-156-5 | #156 (in flight) | durable-domain | domain:docs | AI-pattern clichés (`linear-gradient`, `-webkit-background-clip`, `backdrop-filter`, ChatGPT-style purple gradient) MUST stay out of the docs selector renderer. Captured as a docs-domain test (`test_docs_selector_returns_html`) — domain-bound enforcement, not a cross-cutting governance rule. |
| IC-156-6 | #156 (in flight) | pr-scope | archive-only | "Three-place sync invariant for current 5-viewer browser docs UI list (`docs_router.py` mounts + `frontend-handoff.md` §3 + selector card list)". Loses meaning the moment the viewer list changes. |
| IC-156-7 | #156 (in flight) | historical-only | archive-only | Carried-from citation of IC-155-3; not a new constraint. The IC-155-3 invariant itself migrates per its own row above (durable-domain → domain:auth). |

**Notes on the table:**

- All `pr-scope` and `historical-only` rows stay in the frozen archive entries. PR C does not migrate them.
- PR #156 (currently open) entries are classified provisionally. If PR #156 merges before PR A, the table is canonical as written. If PR A merges before PR #156 (less likely), PR C re-runs the classification step over PR #156's IC declarations after merge.
- **Alias immutability** — `ADR047-G*` slot bodies are **write-once**. Future ADRs that change an underlying constraint create a new `ADR(N+1)-G*` slot and update this table to add a `superseded-by:ADR(N+1)-G*` status; they never mutate an existing `ADR047-G*` body in place. This preserves the historical IC alias as a frozen snapshot of meaning at PR A merge time, so existing prose like "IC-1 ~ IC-16 from pr-130" continues to resolve to the constraints actually in force when pr-130 was authored.

**Phantom citations (informational):**

The strings `IC-RG-6`, `IC-RG-7`, and `IC-RG-8` appear nowhere as declarations. They surface only inside the over-broad citation form `IC-1 through IC-RG-8` used in [pr-148](archive/governor-review-log/pr-148-g-closure-linter.md) and [pr-151](archive/governor-review-log/pr-151-architecture-review-followup.md); only IC-RG-1 through IC-RG-5 were actually declared (in [pr-143](archive/governor-review-log/pr-143-reasoning-guards.md)). They are recorded here so future readers do not search for non-existent tags. They have no classification — they are not ICs, they are citation noise.

## Self-Application Recovery (PR A bridge)

PR A is itself a Tier A change touching `docs/history/**` and `.github/pull_request_template.md`. Per existing policy (ADR 045 Pillar 4), this PR is governor-changing and must produce a `governor-review-log/pr-{N}-bridge-adr-047.md` entry. PR A complies. The new policy (ADR 047 D2/D5) takes effect from PR B onward; PR B is the first PR to write a Governor Footer block as a primary cross-tool review trail (alongside its dual-write log entry).

The bootstrapping rule — "the migration PR satisfies the verifier it is replacing" — is preserved by writing the LAST governor-review-log entry under old policy. After PR A merges, ADR 047 status changes from `Proposed` to `Accepted`, and PR B begins under dual-write semantics.

## Alternatives Considered

- **A. Trim** — keep `governor-review-log/` and narrow Tier matching + summarize Self-Application Proof. Rejected: operational cost stays at 4/4 per Round 1 audit; ceremony continues to grow with each Tier A PR; doesn't solve the self-loop without explicit `governor-paths.md` carve-out (the same fix needed in B). Industry alignment 4/4 (worst).
- **C. Replace entirely** — delete `governor-review-log/` after IC migration, no per-PR provenance archive in repo, rely on GitHub PR descriptions + ADRs only. Rejected: solo + 2-AI-tool setting cannot afford to drop the cross-tool review trail entirely; gate-on-gate evidence (e.g. PR #125 Round 4 finding the path-list drift) would have been lost without an in-repo capture point.
- **D. Single chronological log** (`docs/governance-log.md` 5-line append per governor-changing PR). Rejected: re-creates a smaller bespoke log that ADRs + PR descriptions already subsume; counter-argument from Round 1 audit acknowledges its mild advantage as offline grep affordance, but the marginal benefit does not justify a fourth artefact format alongside ADRs / PR descriptions / frozen archive.
- **B. 14-step single-PR migration** (Codex Round 1 original). Rejected by Round 2 stress-test: violates phased-and-additive principle of `migration-strategy.md`, removes both verifiers simultaneously at one merge, low confidence.
- **E. Amend ADR 045 in place** — keep ADR 045 as the single record and rewrite Pillars 4 + 7 to describe the new architecture. Rejected: ADRs document a decision at a point in time; the case for right-sizing only became clear after 5 days of operation, which is itself a new decision deserving its own ADR. In-place amendment also erases the historical signal that the original architecture was over-engineered, making future readers think Pillars 4 + 7 always meant the new behaviour.
- **F. Wait 2~4 weeks before migrating** — observe the system longer before acting. Rejected: the self-loop is actively pulling feature PRs (#152 / #155 / #156) into governor-changing ceremony every week; each delay adds entries that PR C will then have to classify. The audit signal (Round 1 + Round 2 stress-test) is already concrete, not speculative. Waiting also normalises the current pattern as "the way things are" and makes future migration harder.

## Related Documents

- ADR [045](045-hybrid-harness-target-architecture.md) — introduced the system this ADR right-sizes. Pillars 4 + 7 partially superseded.
- `docs/ai/shared/governor-paths.md` — Tier A/B/C path list (PR D adds an Exclusion).
- `docs/history/archive/governor-review-log/README.md` — frozen archive (PR E adds the closure banner; relocated from `docs/ai/shared/` per the post-decision note below).
- `docs/ai/shared/target-operating-model.md` §3 §5 §7 — cross-tool review cadence (PR E updates the capture location).
- `docs/ai/shared/drift-checklist.md` §1D — sync verification rule (PR E removes or replaces).
- `docs/ai/shared/harness-asset-matrix.md` — asset Tier classifications (PR E reclassifies `governor-review-log/` and `tools/check_g_closure.py`).
- `tools/check_g_closure.py` — closure-table linter (PR F removes; replaced by `tools/check_governor_footer.py` in PR B).
- `tools/check_language_policy.py` — Tier 1 enforcer (PR F simplifies the per-file allowlist; provenance-prefix carve-out + `LOCALE_DATA_FILES` retained).

## Post-Decision Note 2026-05-03 — D2 Location Revisited (#160)

**Scope.** Physical location of the closed historical archive moved from
`docs/ai/shared/governor-review-log/` to
`docs/history/archive/governor-review-log/`. Content preservation is
honoured at the spirit of D6 — markdown-link form `[text](path)` inside
the 18 frozen entries was rewritten so external link targets remain
valid after the move (the previous form `../../history/045-...` already
resolved to a non-existent `docs/ai/history/...` path; the rewrite
incidentally fixes pre-existing broken links). Prose / fenced-code-block
path quotes are preserved verbatim as historical evidence of the rule
in force when each entry was written. No `Errata YYYY-MM-DD:` headings
are added inside frozen entries.

**Operational decisions preserved verbatim.** D2 frozen-archive
contract, D3 alias-immutability invariant, D4 sync-cosmetic carve-out,
D5 phased dual-write completion, D6 append-only errata. ADR047-G1~G27
slot bodies and the IC Classification Table (lines 175-241) are not
amended.

**Trigger.** Visual noise in the active `docs/ai/shared/` reference
tree. The 18 frozen entries' value is historical / audit-trail, not
operational, and `docs/history/archive/` is the canonical home for
"preserved-for-history-but-not-required-reading" archives (precedent:
PR #83, 2026-04-20, moved 29 superseded ADRs from `docs/history/` to
`docs/history/archive/`).

**Bundling justification (ADR047-G27).** This is a *location contract
change*, not a mechanical move: the `REVIEW_LOG_GLOB` carve-out in
`tools/check_language_policy.py` and the shared completion-gate
`GOVERNOR_REVIEW_LOG_PREFIX` move with the directory. Splitting would
leave the language-policy provenance carve-out demoting Korean-provenance
lines to Hangul violations between commits. G27's narrow-scope
explicit-justification clause is honoured.

**Hook-local dead-constant cleanup (Codex round-1 R2).**
`.claude/hooks/completion_gate.py` and `.codex/hooks/completion_gate.py`
declared a local `GOVERNOR_REVIEW_LOG_PREFIX` constant that was
unreachable in the normal import path — the shared
`is_log_only_backfill()` from `.agents/shared/governor/completion_gate.py`
is the actual decision point. The dead constants are removed in this
PR. A boundary test
(`tests/unit/agents_shared/test_governor_boundary.py::test_hook_shims_do_not_redeclare_governor_review_log_prefix`)
prevents resurrection.

**README banner correction (Codex round-1 R3).**
`docs/history/archive/governor-review-log/README.md` previously declared
"17 entries below" while the index already listed 18 (#125 ~ #158).
Corrected to "18 entries" — banner-meta only; the 18 entries themselves
remain frozen.

**Self-application proof.** This PR is governor-changing (touches
`docs/history/**`, AGENTS.md, governor-paths.md, the shared governor
module, and the language-policy enforcer). Cross-tool review provenance
lives in the PR description's `## Governor Footer` block per D2, with
two rounds: (1) plan-stage on the implementation plan, three R-points
all closed `Fixed`; (2) implementation-stage on the actual diff, R-points
recorded in the footer. No new `governor-review-log/` entry is
written — that artefact format was retired by D2.
