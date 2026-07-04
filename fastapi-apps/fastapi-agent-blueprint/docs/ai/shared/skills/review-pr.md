# Pull Request Quality Gate Review

## Default Flow Position

This skill participates in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow) at the **`completion gate`** step.

It is invoked at the end of work — after `implement`, `verify`, and `self-review` have settled — to apply a final review against the change set as a whole.

After completion-gate review, route to:
- `/sync-guidelines` if the review reported `Drift Candidates` or `Sync Required: true`

Recursion guard: do **not** invoke `/review-pr` recursively from within itself, and do not invoke `/plan-feature` from inside this skill (the change has already been implemented).

## Core Principle

This skill defines no review rules of its own. It is the **PR-scoped single entry point** that
applies the shared [Review Protocol](../review-protocol.md) to a PR diff, then decides drift and
posting.

- **What to review** — the protocol dimensions in [Review Protocol §1](../review-protocol.md#1-review-dimensions-concern-based-stable-ids): `CORR`, `REG`, `STAB`, `CONTRACT`, `ARCH`, `SEC`, `GOV`.
- **What may become a finding** — the [Finding Basis rule (§2)](../review-protocol.md#2-finding-basis-anti-hallucination-rule): **no finding without a declared basis.** This replaces the old "only shared rule sources may create findings" — correctness / regression / side-effect findings are now in scope **when they carry `diff` / `contract` / `test` / `runtime` evidence**; `ARCH` / `SEC` / `GOV` findings still require a cited shared-rule source.
- **How it is reported** — the [output contract (§3)](../review-protocol.md#3-output-contract), the [intent/PASS verdict (§4)](../review-protocol.md#4-intent--pass-state), and the [posting rules (§5)](../review-protocol.md#5-github-posting--verdict-contract).

This skill depends on the protocol + the shared checklists it references — **never** on the
`review-architecture` or `security-review` skill bodies.

## Difference from `/review-architecture` and `/security-review`

```text
/review-pr            -> apply the whole protocol to the CHANGED files of a PR, decide drift + posting
/review-architecture  -> audit a domain or full repo structure (ARCH dimension in depth), outside PR scope
/security-review      -> audit a file/domain/repo security surface (SEC dimension in depth) with a preflight
```

`review-pr` is the only one of the three that emits a behavior `Verdict` (§4); the other two are
audit-only (`Verdict: N/A`). See [Review Protocol §8](../review-protocol.md#8-skill-scope-boundaries).

## Phase 0: Resolve Target and Collect Evidence + Intent

1. Resolve the review target.
   - If a PR number or URL is given: inspect that PR.
   - If omitted: inspect the current branch diff or current-branch PR.
   - If no review target exists, stop with instructions to create or identify one.
2. Collect the diff, changed filenames, affected domains, and surrounding code when a changed
   file alone is not enough to judge a rule or reproduce an effect.
3. **Collect the intent** (Review Protocol §4): the PR body, the linked issue, or explicit
   acceptance criteria. If none exist, the `Verdict` will be `CANNOT CERTIFY` — do not invent one.
4. Load the rule sources: the [Review Protocol](../review-protocol.md), plus the checklists it
   references — [`architecture-review-checklist.md`](../architecture-review-checklist.md) (ARCH),
   [`security-checklist.md`](../security-checklist.md) (SEC) — and `AGENTS.md` (incl. § Language
   Policy for `GOV`).

## Phase 1: Review Changed Files Against the Protocol Dimensions

Apply the protocol dimensions (§1) to the diff. File location (`domain/`, `infrastructure/`,
…) is only a **navigation** aid now, not the review taxonomy.

- `CORR` / `REG` / `STAB` / `CONTRACT` — evidence-grounded: open only against `diff` / `contract`
  / `test` / `runtime` evidence. Read surrounding code, run a probe, or point at the failing/absent
  test as the basis. An unbased concern is a `Question` in `Next Actions`, not a finding.
- `ARCH` — apply `architecture-review-checklist.md`; cite the category.
- `SEC` — apply `security-checklist.md`; cite the category.
- `GOV` — Tier-1 Language Policy violations (non-English prose in a Tier-1 path outside the
  bilingual-token allowlist), governor-path drift, and edits to shared rule sources.

Every finding carries a stable dimension ID + a declared `basis` (§2). Use surrounding context
whenever a rule or an effect depends on code outside the diff.

## Phase 2: Determine Drift Candidates and Sync Requirement

After findings are collected, decide whether the PR also created or exposed reference drift.

Mark `Sync Required: true` when at least one is true:
- the diff touches `AGENTS.md`, `docs/ai/shared/`, `project-dna`, checklist files, skill
  procedures, or tool wrappers;
- the diff touches shared/base architecture files whose patterns are documented;
- the review discovers a mismatch between code and shared references;
- the review discovers stale feature-detection assumptions that should update `project-dna` or a
  checklist.

When drift exists, create a `Drift Candidates` entry even if the code change itself is acceptable.

## Phase 3: Report Using the Protocol Contract

Emit the [Review Protocol §3](../review-protocol.md#3-output-contract) sections exactly, in order:
`Scope`, `Effect Answer`, `Sources Loaded`, `Findings` (OPEN only), `Coverage` (OK/SKIP),
`Drift Candidates`, `Verdict` (§4), `Next Actions`, `Completion State`, `Sync Required`.

Example:

```text
Scope
- PR #128: Add DynamoDB-backed docs query path
- Affected domains: docs, _core
- Changed files: 7

Effect Answer
- Adds a DynamoDB-backed query path in the docs domain and wires it through the DI container.
  Existing RDB behaviour is unchanged; no security-sensitive surface is touched.

Sources Loaded
- docs/ai/shared/review-protocol.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/security-checklist.md
- AGENTS.md

Findings
- [OPEN][HIGH][ARCH] src/docs/infrastructure/di/docs_container.py:18 — basis: rule-source (architecture-review-checklist §4)
  Impact: container wiring uses the wrong dependency source for DynamoDB mode.
  Recommended fix:
    before: rdb = providers.Singleton(RdbClient, ...)
    after:  dynamo = core_container.dynamodb_client  # keep RDB wiring out of this path
- [OPEN][MEDIUM][CORR] src/docs/application/docs_query.py:44 — basis: diff-evidence
  Impact: empty-result branch returns None but the caller indexes [0] → IndexError on no-match.
  Recommended fix:
    before: return rows[0]
    after:  return rows[0] if rows else None  # caller already handles None

Coverage
- [OK][ARCH] architecture-review-checklist §5 Test coverage — all 3 baseline test files present for docs
- [SKIP][SEC] security-checklist §4.2 File Upload — project-dna §8 and live code both confirm feature inactive

Drift Candidates
- target: docs/ai/shared/architecture-review-checklist.md
  reason: PR introduces DynamoDB-specific guidance the shared checklist does not mention consistently.
  auto-fix: no
  sync-required: true

Verdict
- FAIL — OPEN HIGH (ARCH container wiring) breaks the intended DynamoDB path stated in the PR body.

Next Actions
- Fix the container wiring (ARCH) and the empty-result branch (CORR).
- Run /sync-guidelines after the DynamoDB guidance is updated.
- Post the review to GitHub only after the findings are addressed.

Completion State
- complete with findings; no inline threads posted yet

Sync Required
- true
```

If nothing is open, still emit every section: `Findings: none`, `Coverage:` (the OK/SKIP records),
`Verdict: PASS` (or `CANNOT CERTIFY` when intent evidence is missing), `Drift Candidates: none`,
`Sync Required: false`.

## Phase 4: Post to GitHub (Optional)

Posting follows [Review Protocol §5](../review-protocol.md#5-github-posting--verdict-contract)
exactly — it is not re-decided here:

- **Inline vs summary** — line-anchored findings inside the diff hunks post inline (reviews API,
  `side:RIGHT`, head-SHA anchored, copy-paste `before → after`, English); cross-cutting / out-of-hunk
  findings go in the summary; fallback to summary when an inline anchor cannot attach.
- **Verdict → action** (first match wins) — `FAIL` → request changes; `CANNOT CERTIFY` → comment;
  any remaining `OPEN` finding or `Sync Required: true` → comment; otherwise → approve.
- **Finding key + lifecycle** — reuse the same comment/thread for a still-open finding key, mark
  vanished keys resolved, post new only for new keys.

Ask before posting. If `Sync Required: true`, do not treat the review as fully closed until the
follow-up sync path is acknowledged.

## Cross-Tool Review Prompt Template

Use this template when another tool or reviewer cross-checks a `/review-pr` result, a PR diff, or
a readiness decision. The purpose is a consistent input and output frame; reviewers may disagree
with the original review when the evidence supports it.

```text
Cross-tool review for /review-pr (read-only). Do not modify files. Do not run git commands.

Context
- Repo: fastapi-agent-blueprint
- Review target: <PR number, branch, or diff scope>
- Issue link: <#NNN or none>
- Round: <0 plan / 1 implementation / 2 gate-on-gate / N>
- original user question: <verbatim or concise restatement>
- success metric: <what the user said would count as success>
- Inherited constraints: <list of ADR{NNN}-G{N} consequence IDs from prior governance ADRs (post-ADR-047); for historical context, see governor-review-log/ archive>

What you are reviewing
- Summary: <one-paragraph change summary>
- Changed files: <3-8 highest-signal paths>
- Prior review result: <Findings / Coverage / Verdict / Drift Candidates / Sync Required summary>

Sources Loaded
- docs/ai/shared/review-protocol.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/security-checklist.md
- AGENTS.md; docs/ai/shared/governor-paths.md when the change may be governor-changing
- Relevant changed files and surrounding code

Review Angles
1. Diff-scope correctness: did the review inspect the changed files and enough surrounding code
   to judge the dimensions and reproduce the claimed effects?
2. Dimension + basis grounding: is every finding tagged with a protocol dimension ID and a valid
   `basis` (§2)? Are ARCH/SEC/GOV rule-cited and CORR/REG/STAB/CONTRACT evidence-cited, with no
   unbased "taste" findings?
3. Contract shape: are OPEN issues in `Findings` and OK/SKIP in `Coverage` (never mixed)? Is the
   `Verdict` (§4) correct given the intent evidence?
4. Drift decision: is `Sync Required` correct, especially for shared rule sources, skill
   procedures, wrappers, and documented patterns?
5. Volatile facts: are branch, PR number, changed-file counts, file paths, and line references
   verified from current evidence?

Output format
- Scope
- Sources Loaded
- Findings: OPEN issues only, each with severity, dimension ID, basis, file:line, impact, and fix
- Coverage: OK/SKIP records with evidence
- Drift Candidates: target, reason, auto-fix, sync-required
- R-points: every cross-review point closes as Fixed / Deferred-with-rationale / Rejected (the
  AGENTS Guard G vocabulary; no non-canonical labels)
- Verdict: PASS / FAIL / CANNOT CERTIFY / N/A
- Final Verdict: merge-ready / minor fixes recommended / still needs reinforcement / block merge
- Sync Required: true or false
```

## Self-Structured Review Checklist

Use when a cross-tool reviewer is unavailable (single-tool environment). Record
`reviewer: self-structured` in the Governor Footer. Work through each item below and surface any
findings as R-points with the AGENTS Guard G closure vocabulary
(`Fixed` / `Deferred-with-rationale` / `Rejected`).

**F / G / H / I — Reasoning-Level Consistency Guards** (canonical in
[AGENTS.md](../../../../AGENTS.md#reasoning-level-consistency-guards); see also
[Review Protocol §6](../review-protocol.md#6-reasoning-level-consistency-guards-pointer-only)):
- [ ] **F** — every `file:line`, branch, PR number, and count is re-verified from current tool
  output, not memory.
- [ ] **H** — the `Effect Answer` is evidence-based (grep / test run / diff scan), not a
  restatement of procedure.
- [ ] **I** — before defending a challenged verdict, the premise was re-verified and circular
  reasoning checked.

**Contract shape**
- [ ] `Findings` holds OPEN issues only; OK/SKIP are in `Coverage`. Every finding has a dimension
  ID + a `basis`; no unbased "taste" finding.
- [ ] `Verdict` matches §4: `CANNOT CERTIFY` when no intent evidence exists; `FAIL` when an OPEN
  BLOCKING or intent/contract-breaking HIGH is present.

**External contract (`CONTRACT`)**
- [ ] API response shapes, OpenAPI spec, and `frontend-handoff.md` match the implementation.

**Security surface (`SEC`)**
- [ ] Any new endpoint, auth change, file upload, or external call is checked against
  `docs/ai/shared/security-checklist.md`.

**Test coverage (`REG` / `ARCH §5`)**
- [ ] If the change touches build-out, security, or external-contract paths, a regression test
  exists or the absence is explicitly deferred with rationale.
