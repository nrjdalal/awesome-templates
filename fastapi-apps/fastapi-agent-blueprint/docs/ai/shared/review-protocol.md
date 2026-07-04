# Review Protocol

> Canonical for **review dimensions, finding basis, output/coverage contract, intent/PASS
> state, and GitHub posting/verdict rules** shared by the review-skill family. The
> Reasoning-Level Consistency Guards (F/G/H/I) and the `Effect Answer` requirement remain
> canonical in [`AGENTS.md` § Reasoning-Level Consistency Guards](../../../AGENTS.md#reasoning-level-consistency-guards); this doc references them, it does not redefine them.
>
> Consumed by: [`review-pr`](skills/review-pr.md), [`review-architecture`](skills/review-architecture.md),
> [`security-review`](skills/security-review.md). Skills depend on this protocol + the shared
> checklists — **never on each other's skill bodies**.

## Purpose

The review skills previously each embedded their own contract, which drifted and left three
gaps: non-deterministic output (inline vs summary decided ad hoc), file-location review
categories instead of concern-based ones, and a rule (`review-pr` "only shared rule sources
may create findings") that structurally forbade correctness / regression / side-effect
findings.

This protocol fixes all three in one place: **what** to review (§1 dimensions), **what may
become a finding** (§2 finding basis), **how** it is reported (§3 output contract, §5 posting),
and **whether the change passes** (§4 intent/PASS). Each skill applies this protocol at its own
scope; it does not invent review rules of its own.

## §1 Review Dimensions (concern-based, stable IDs)

Every finding is tagged with a stable dimension ID. IDs are the answer to "which points am I
reviewing against?" — they replace the old file-location categories (`domain/`,
`infrastructure/`, …), which are now only a *navigation* aid, not the review taxonomy.

| ID | Dimension | What it asks | Rule source / evidence |
|----|-----------|--------------|------------------------|
| `CORR` | Correctness | Does the change do what it intends? Logic, off-by-one, wrong branch, bad default, mis-wired DI. | evidence (diff / test / runtime) |
| `REG` | Regression / side-effects | Does it break or alter existing behavior outside its stated scope? Shared base classes, container wiring, migrations, cross-domain contracts. | evidence (diff / test / contract) |
| `STAB` | Stability | Error handling, boundary/empty/None cases, exception translation, concurrency, resource cleanup, timeouts. | evidence (diff / runtime) |
| `CONTRACT` | External contract | API request/response shapes, OpenAPI, status codes, event/task payloads, DB schema/migration compatibility. | evidence (contract / diff) |
| `ARCH` | Architecture compliance | Layering, conversion patterns, DTO/VO/Model roles, DI, bootstrap, naming. | [`architecture-review-checklist.md`](architecture-review-checklist.md) (10 categories) |
| `SEC` | Security | AuthN/Z, secrets, input validation, sensitive-data exposure, logging, storage, worker, AI provider. | [`security-checklist.md`](security-checklist.md) (12 categories) |
| `GOV` | Governance / process | Tier-1 language policy, governor-path drift, edits to shared rule sources, review-process rules. | [`AGENTS.md`](../../../AGENTS.md) + [`governor-paths.md`](governor-paths.md) |

- `ARCH`, `SEC`, and `GOV` are **rule-grounded**: they exist only to apply a shared rule source
  (a checklist, `AGENTS.md`, or `governor-paths.md`) — no tool-local rule invention.
- `CORR` / `REG` / `STAB` / `CONTRACT` are **evidence-grounded**: they are opened only against
  concrete evidence (§2), never against taste or a hunch.
- A single physical issue gets one finding under its most specific dimension. Do not split one
  defect across dimensions, and do not merge distinct defects into one finding.

## §2 Finding Basis (anti-hallucination rule)

This replaces `review-pr`'s old "only shared rule sources may create findings" while keeping
its intent: **no finding without a declared basis.**

Every finding line MUST carry `basis: <type>` and cite the concrete anchor:

| `basis` | Valid for | Must cite |
|---------|-----------|-----------|
| `rule-source` | `ARCH`, `SEC`, `GOV` | the checklist / `AGENTS.md` / `governor-paths.md` rule + section (e.g. `architecture-review-checklist §1`) |
| `diff-evidence` | `CORR`, `REG`, `STAB`, `CONTRACT` | the changed `file:line` and what the code does |
| `contract-evidence` | `CONTRACT`, `REG` | the schema / OpenAPI / payload / migration that conflicts |
| `test-evidence` | `CORR`, `REG` | a failing test (name + expected vs actual). An **absent** test is a finding only when tied to a changed contract, a concrete regression risk, or a checklist rule (e.g. `architecture-review-checklist §5`) — never "untested, therefore a finding" |
| `runtime-evidence` | `CORR`, `STAB` | the command run + observed output (e.g. a failing probe) |

Rules:
- If a concern cannot be tied to one of the bases above, it is **not a finding**. Record it as a
  `Question` in `Next Actions` (to be resolved), not as a finding. This is what stops
  speculative "looks unstable" / taste-refactor findings.
- `ARCH` / `SEC` findings without a citable shared-rule section are invalid — downgrade to a
  `Drift Candidate` if the rule itself is missing/stale.
- Severity (§3) is independent of basis: a `diff-evidence` `CORR` finding can be `BLOCKING`.

Evidence examples (valid finding vs `Question`):
- Valid `CORR` / `diff-evidence`: "`src/x/service.py:42` returns `None` on the empty-list
  branch, but the caller indexes `[0]` → `IndexError`." (cites code + the concrete failure)
- Not a finding → record as a `Question`: "this could be more robust" / "there's probably a
  race here" / "no tests for this file" (no changed contract, no cited regression, no rule).

## §3 Output Contract

Every review result emits these sections, in order. `review-pr`, `review-architecture`, and
`security-review` share this contract; only `Scope` phrasing differs by skill.

- **`Scope`** — target (PR #/branch, domain, or file), affected domains, changed-file count,
  important exclusions.
- **`Effect Answer`** — 1–3 sentence, evidence-based summary of what the change *actually* does
  or exposes (Guard H; see [`AGENTS.md`](../../../AGENTS.md#reasoning-level-consistency-guards)).
  Grounded in the diff/code read, never a restatement of procedure. For a process-only question,
  write `Effect Answer: N/A — process question`.
- **`Sources Loaded`** — the exact shared rule sources + checklists actually used.
- **`Findings`** — **OPEN issues only.** Each line:
  `[OPEN][<SEVERITY>][<DIM-ID>] <file:line> — basis: <type> (<citation>)`
  then `Impact:` and `Recommended fix:` on following lines. For line-anchored code findings,
  `Recommended fix` includes a copy-paste `before → after` block (§5).
- **`Coverage`** — the `OK` / `SKIP` records that used to be mixed into `Findings`. Each line:
  `[OK|SKIP][<DIM-ID>] <what was checked> — <evidence for OK, or why SKIP>`. Keeps `Findings`
  purely actionable while still proving what was inspected.
- **`Drift Candidates`** — shared docs / checklists / wrappers / `project-dna` that may need
  sync; each with `target`, `reason`, `auto-fix`, `sync-required`.
- **`Verdict`** — the intent/PASS decision (§4).
- **`Next Actions`** — code fixes, `Question`s (unbased concerns), follow-up review, sync
  request, optional GitHub posting.
- **`Completion State`** — concise closure status, including any unresolved review threads (§5).
- **`Sync Required`** — explicit `true` / `false`.

### Severity + review state

Keep the two axes separate (do not mix):

- Review state: `OPEN`, `OK`, `SKIP`
- Severity: `BLOCKING`, `HIGH`, `MEDIUM`, `LOW`, `NOTE`

## §4 Intent & PASS State

"Did it pass?" is only answerable against a stated intent. The review takes an **intent input**
— the PR body, the linked issue, or explicit acceptance criteria — and emits one `Verdict`:

- **`PASS`** — intent evidence exists AND there is no `OPEN` `BLOCKING` finding, nor any `OPEN`
  `HIGH` finding that breaks the stated intent or an external contract.
- **`FAIL`** — an `OPEN` `BLOCKING` finding, or an `OPEN` `HIGH` finding that breaks the stated
  intent or an external contract.
- **`CANNOT CERTIFY (intent evidence missing)`** — no PR body / issue / acceptance criteria to
  judge against. Do **not** emit a false `PASS`; list exactly what intent evidence is needed.
- **`N/A (audit-only scope)`** — the run audits a single dimension with no behavior intent to
  certify (`review-architecture`, `security-review`). Emit `Findings`/`Coverage` normally, but a
  behavior `PASS`/`FAIL` does not apply.

`CORR`/`REG`/`STAB` findings feed `PASS`/`FAIL`; a clean architecture or security audit alone is
never a behavior `PASS`.

## §5 GitHub Posting & Verdict Contract

Posting is **deterministic** — the same review never lands as inline one time and summary the
next.

### Inline vs summary (routing)

- A finding is posted **inline** (GitHub reviews API, `side:RIGHT`, anchored to the head SHA)
  when it has a concrete `file:line` **that falls inside the PR diff hunks**. Inline comments
  include a copy-paste `before → after` block and are written in **English** (Tier-1 review
  surface), and state explicitly when something must **not** be changed.
- A finding goes into the **summary** body when it is cross-cutting, whole-file, or references a
  line **outside** the diff hunks.
- **Fallback:** if an inline anchor cannot attach (line not in the diff, API rejects the
  position), demote the finding to the summary with the `file:line` quoted verbatim. Never drop
  it.

### Verdict → GitHub review action

Evaluate the rules **in order; the first match wins**, so any concrete review state resolves to
exactly one action (severity feeds the §4 verdict; the verdict + remaining-`OPEN`-findings + sync
state decide the action — never the reviewer's discretion):

1. `Verdict: FAIL` → **Request changes**.
2. `Verdict: CANNOT CERTIFY` → **Comment** (state the missing intent evidence; never Approve).
3. Any `OPEN` finding remains, or `Sync Required: true` → **Comment**.
4. No `OPEN` findings, `Sync Required: false`, and `Verdict` is `PASS` or `N/A` → **Approve**.

### Comment lifecycle (deterministic identity)

- Every finding has a stable **finding key**:
  `<DIM-ID> | <basis> | <file:line | summary-target> | <stable short title>`.
- On re-review of the same PR: a key that still resolves → **update** the existing comment/thread
  (never duplicate); a key that no longer appears → mark the thread **resolved/obsolete**; a new
  key → **new** comment. This identity rule is what makes the same PR reviewed twice produce the
  same comment set.
- Posting always requires user confirmation first (the review is produced first; publishing is a
  separate, explicit step). This protocol **reports** thread state; it does not auto-resolve or
  merge (out of scope).

### Merge-gate reality (report, do not automate)

- The completion gate is **not** closed while `OPEN` `BLOCKING` inline threads remain unresolved,
  or while branch protection (`require_conversation_resolution`) still blocks merge. Surface open
  threads and blocked status in `Completion State`.
- This protocol **reports** merge-gate status; it does not auto-resolve threads or merge (out of
  scope).

## §6 Reasoning-Level Consistency Guards (pointer only)

The F/G/H/I guards apply to every review and are **canonical** in
[`AGENTS.md` § Reasoning-Level Consistency Guards](../../../AGENTS.md#reasoning-level-consistency-guards).
This protocol does not restate or re-label them. Two review-facing anchors:

- The `Effect Answer` field (§3) is the enforcement point for Guard **H** (effect before
  process).
- Cross-review R-points close with the Guard **G** closure vocabulary defined in that AGENTS
  section — use those exact tokens; do not invent variants.

## §7 Independent Review & Fallback

- Governor-changing changes require an independent review (cross-tool by default) per
  [`AGENTS.md` § Default Coding Flow → Independent Review Trigger](../../../AGENTS.md#default-coding-flow).
- Each skill keeps a **Cross-Tool Review Prompt Template** (input/output frame for a reviewing
  tool) and a **Self-Structured Review Checklist** (single-tool fallback) specialized to its
  scope; both produce R-points closed with the Guard G vocabulary and reference this protocol
  for dimensions, basis, and output shape.

## §8 Skill Scope Boundaries

| Skill | Scope | Default Flow step |
|-------|-------|-------------------|
| `review-pr` | changed files of a PR / branch; the PR-scoped single entry point that applies this whole protocol, then decides drift + posting | `completion gate` |
| `review-architecture` | a domain or the full repo structure, **outside** PR scope; applies the `ARCH` dimension in depth | `self-review` |
| `security-review` | a file / domain / repo security surface; applies the `SEC` dimension in depth with a feature-freshness preflight | `self-review` |

- The built-in generic `/code-review` is **not** project-aware; it may serve as an optional
  extra `CORR` lens but is never an authoritative source of findings under this protocol.
- Fan-out to project-aware sub-agents (seeded with this protocol + the shared checklists) is an
  optional escalation for heavy reviews (security-sensitive, multi-domain, large diff,
  concurrency/worker/provider changes) — not the default path, and never skill-calls-skill.
