# 055. Summary Finding Ledger — Out-of-Diff Review Findings

- Status: Accepted
- Date: 2026-07-18
- Related issue: #292
- Builds on (does not supersede): ADR [053](053-shared-review-protocol.md). 053 authored the shared review protocol (dimensions / finding basis / output / verdict / posting); **055 amends its §5 posting contract for the summary-routed finding class only**. Inline-thread routing, the finding-key format, and the first-match structure of the verdict table are unchanged.

## Summary

Review-protocol §5 routes findings that reference lines outside the PR diff hunks to the review **summary body**. Summary bodies are not resolvable threads, so these findings escape both the contributor's "resolve the threads" workflow and the `require_conversation_resolution` merge gate on `main` — a reviewed-and-requested change on an out-of-diff file could be silently dropped while the PR became mergeable (observed on PR #287). #292 closes the gap with a **Summary Finding Ledger**: summary-routed findings post as a task-list checklist with deterministic carry-forward across review rounds, any still-`OPEN` ledger key blocks Approve and keeps the completion gate open, and pulling the referenced files into the PR diff is documented as the recommended — but unenforceable — remediation.

## Background

### Trigger

The PR #287 re-review (2026-07-14). The first review round (2026-07-13) posted 7 inline findings plus 3 summary-level findings whose targets sat outside the PR diff (`docs/reference.md` extras row, `examples/README.md` index row, conditional Makefile parity). The contributor's fix commit resolved all 7 inline threads, but 2 of the 3 summary items were never addressed — they never existed as threads, so nothing tracked them — and the merge gate did not block at head `96718f7`. The re-review caught the drop only by ad-hoc manual comparison against the prior summary.

### Evidence that a thread-based workaround does not exist

File-level review comments (`subject_type: file`) cannot anchor paths absent from the PR diff: a live attempt on PR #287 (`path=docs/reference.md`) returned `422 pull_request_review_thread.path could not be resolved`. GitHub anchors review threads — line- or file-level — only to paths present in the diff. Summary posting is therefore the only mechanism for out-of-diff findings, and the gap has to be closed at the contract level, not the API level.

### Decision type

Experience-based correction of ADR 053's posting contract — the same lineage pattern as 047 right-sizing 045 and 053 correcting the per-skill contracts. The design was round-0 cross-reviewed by codex (read-only; verdict "sound-with-adjustments"): R1 ledger authority across rounds, R2 anchor rule for cross-cutting findings, R3 completion-gate closure, R4 ADR-index drift — all four Fixed in the shipped design.

## Problem

§5's summary routing was written as an output-formatting rule and carried no tracking semantics. Inline findings inherit GitHub's thread lifecycle — resolvable, enumerable, merge-blocking via branch protection; summary findings inherited nothing: no state, no carry-forward across rounds, no verdict effect once posted. The protocol's own determinism goal ("the same review never lands as inline one time and summary the next") made the failure systematic: every out-of-diff finding deterministically lands in the untracked channel.

## Alternatives Considered

### A. Checklist + re-review gate only (issue #292 Option 1)

Make the summary checklist the binding contract and the prior-round diff a mandatory re-review step. Sound and API-independent, but leaves contributors without the one remediation that restores real thread tracking.

### B. Pull-into-diff guidance only (issue #292 Option 2)

Ask contributors to include the referenced files in the PR so findings anchor as normal resolvable threads. **Rejected as the sole fix:** guidance-only — the protocol cannot force it, so the gap stays open whenever it does not happen.

### C. Both — A as the contract, B as the recommended remediation (issue #292 Option 3) — chosen

A closes the gap unconditionally; B documents the escape hatch that upgrades ledger items to real threads when practical.

A fourth shape — automation (a CI check parsing review bodies for unchecked ledger items) — was not a candidate: project-dna §0 lists hard-blocking automation gates as a non-goal; the harness nudges, humans and CI decide.

## Decision

1. **Summary Finding Ledger** — the review summary body carries a `Summary Finding Ledger` section: one GitHub task-list item (`- [ ]`) per summary-routed finding, preserving the same content contract as an inline comment (finding key, severity, dimension ID, `basis`, impact, recommended fix).
2. **Anchor rule** — an out-of-hunk or fallback-demoted finding cites its `file:line` verbatim; a cross-cutting / whole-file finding cites its normalized `summary-target` (path or section + stable short title). No pseudo line anchors for findings that have no single line.
3. **Deterministic carry-forward + authority** — the ledger in the latest posted review round is the single authoritative state. Each re-review posts a complete ledger; every prior-round key carries forward as `OPEN` unless that round verifies it `FIXED` (checked, with a verification note) or withdraws it as `OBSOLETE` (checked **and** struck through with the `OBSOLETE:` tag, with rationale — the tag overrides the checkbox reading). Items are never silently deleted.
4. **Verdict effect** — §5 verdict rule 3 counts any still-`OPEN` key in the latest ledger as a remaining `OPEN` finding → **Comment**; rule 4 (Approve) is reachable only when no ledger key is `OPEN`.
5. **Completion gate** — the completion gate is not closed while any latest-ledger key is `OPEN`; `Completion State` lists the `OPEN` keys and states `summary-ledger: clean | unresolved`.
6. **Re-review gate** — `review-pr` Phase 0 gains a mandatory step: when the PR carries prior review rounds, extract their ledgers and diff every key against the new head before any verdict.
7. **Remediation guidance** — reviewers recommend pulling the referenced files into the PR diff when practical; re-anchored findings become normal inline threads and their ledger items close as `OBSOLETE (superseded by inline thread)`.

## Rationale

- The ledger reuses §5's existing finding-key identity rule instead of inventing a parallel tracking scheme — re-reviews diff keys, exactly as they already do for inline threads.
- Making the **latest** round's ledger authoritative resolves the multi-round / multi-reviewer ambiguity (codex R1): old checkboxes in superseded review bodies carry no state; one place is always current.
- The deterministic verdict rule turns the PR #287 failure ("resolve inline threads → mergeable") into a first-match table outcome: an unresolved summary finding yields **Comment**, never Approve, with no reviewer discretion involved.
- The contract stays procedural — human-applied posting and verdict rules, no hooks or CI — consistent with project-dna §0 (advisory-first; the harness nudges, humans and CI decide).

## Consequences

- Enforcement surface: `docs/ai/shared/review-protocol.md` §3/§5 + `docs/ai/shared/skills/review-pr.md` (Phase 0 / Phase 4 / both review templates) + the two `review-pr` wrappers. No `src/` change, no hook, no CI change.
- `require_conversation_resolution` continues to govern inline threads only; the ledger is the compensating procedural control for summary findings. If a reviewer ignores the ledger contract, the #292 bypass reappears — that residual risk is accepted (advisory-first) and mitigated by the deterministic verdict rule and the mandatory Phase 0 re-review diff.
- Reviews on PRs with prior rounds now require fetching prior review bodies (e.g. `gh api repos/{owner}/{repo}/pulls/{n}/reviews`) — a small, bounded cost paid only on re-review rounds.
- ADR-index drift fixed in passing (codex R4): the missing ADR 054 row and the stale next-free-number note in `docs/history/README.md`.

### Durable Governance Constraints

- **ADR055-G1** — The ledger in the **latest posted review round** is the single authoritative state, and every re-review posts a **complete** ledger: each prior-round key carries forward as `OPEN` unless that round verifies it `FIXED` or withdraws it as `OBSOLETE`. Posting a partial ledger (dropping keys) re-enters this ADR.
- **ADR055-G2** — Any still-`OPEN` key in the latest ledger blocks **Approve** (§5 verdict rule 3) and keeps the **completion gate** open. Both effects are deterministic table outcomes, not reviewer discretion; weakening either re-enters this ADR.
- **ADR055-G3** — The ledger contract is a **human-applied procedure**. Introducing automation that hard-blocks on ledger state (CI parsing of review bodies, hooks) re-enters this ADR and the project-dna §0 non-goal ("hard-blocking automation gates").
- **ADR055-G4** — The item-state encoding is canonical: `- [ ]` = `OPEN`; `- [x]` + verification note = `FIXED`; `- [x] ~~<item>~~ OBSOLETE: <rationale>` = `OBSOLETE` (tag overrides checkbox). Changing the encoding is a governor change — it breaks re-review parsing of prior rounds' ledgers.
