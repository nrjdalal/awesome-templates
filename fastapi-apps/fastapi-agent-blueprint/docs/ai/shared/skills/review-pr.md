# Pull Request Quality Gate Review

## Default Flow Position

This skill participates in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow) at the **`completion gate`** step.

It is invoked at the end of work — after `implement`, `verify`, and `self-review` have settled — to apply a final architecture- and security-aware review against the change set as a whole.

After completion-gate review, route to:
- `/sync-guidelines` if the review reported `Drift Candidates` or `Sync Required: true`

Recursion guard: do **not** invoke `/review-pr` recursively from within itself, and do not invoke `/plan-feature` from inside this skill (the change has already been implemented).

## Core Principle

This skill does not define custom review rules.
It applies the project's shared rule sources to the PR diff and decides whether
the quality gate can close or must continue into `/sync-guidelines`.

Only shared rule sources may create findings:
- `AGENTS.md`
- `docs/ai/shared/project-dna.md`
- `docs/ai/shared/architecture-review-checklist.md`
- `docs/ai/shared/security-checklist.md`

Tool-specific convention files, if available, may help with wording or
navigation, but they must not introduce findings that are not already backed by
the shared rule sources above.

## Review Contract

Every result must include the sections below.

- `Scope` - PR number/title, base/head refs, affected domains, changed file count
- `Effect Answer` - 1-3 sentence evidence-based summary of what this PR *actually* does or exposes.
  Must be grounded in the diff read, not a restatement of the review procedure.
  Purpose: Guard H (AGENTS.md § Reasoning-Level Consistency Guards) — effect questions must be
  answered with evidence first, before process/procedure content. If the question is process-only
  (e.g. "was the review checklist followed?"), write `Effect Answer: N/A — process question`.
- `Sources Loaded` - exact shared rule sources used for the review
- `Findings` - only open issues; each item includes `severity`, `rule source`,
  `file:line`, `impact`, and `recommended fix`
- `Drift Candidates` - shared docs, checklists, wrappers, or `project-dna`
  targets that may need sync; each item includes `target`, `reason`,
  `auto-fix`, and `sync-required`
- `Next Actions` - code fixes, follow-up review, sync request, optional GitHub
  posting
- `Completion State` - concise closure status for the review
- `Sync Required` - explicit `true` or `false`

### Severity Taxonomy

Use a separate review state and severity. Do not mix them.

- Review state: `OPEN`, `OK`, `SKIP`
- Severity: `BLOCKING`, `HIGH`, `MEDIUM`, `LOW`, `NOTE`

## Difference from `/review-architecture`

```text
/review-pr            -> review only changed files, then decide whether sync is required
/review-architecture  -> audit a domain or the full repo structure outside PR scope
```

## Phase 0: Resolve Target and Collect Evidence

1. Resolve the review target.
   - If a PR number or URL is given: inspect that PR
   - If omitted: inspect the current branch diff or current branch PR
   - If no review target exists, stop with instructions to create or identify one
2. Collect the diff, changed filenames, affected domains, and surrounding code
   when a changed file alone is not enough to judge the rule.
3. Load the shared rule sources listed above before forming findings.
4. AGENTS.md § Language Policy (cross-ref): if the diff inserts non-English
   prose into Tier 1 paths, surface as a `Findings` violation and a
   `Sync Required: true` candidate. Bilingual escape tokens are exempt.

## Phase 1: Review Changed Files Against Shared Rules

Walk through changed files and apply only the relevant checklist categories.

- `domain/` -> layer dependency, conversion patterns, DTO integrity
- `application/` -> orchestration, dependency boundaries
- `infrastructure/` -> DI, repository, provider, storage, worker, logging rules
- `interface/` -> router, response exposure, admin, auth, validation rules
- `migrations/` -> upgrade/downgrade completeness and compatibility concerns
- shared docs / skill wrappers -> drift risk, source-of-truth alignment, quality
  gate follow-up

Use surrounding context whenever a rule depends on code outside the diff.

## Phase 2: Determine Drift Candidates and Sync Requirement

After findings are collected, determine whether the PR also created or exposed
reference drift.

Mark `Sync Required: true` when at least one of the following is true:
- the diff touches `AGENTS.md`, `docs/ai/shared/`, `project-dna`, checklist
  files, skill procedures, or tool wrappers
- the diff touches shared/base architecture files whose patterns are documented
- the review discovers a mismatch between code and shared references
- the review discovers stale feature detection assumptions that should update
  `project-dna` or a checklist

When a drift exists, create a `Drift Candidates` entry even if the code change
itself is otherwise acceptable.

## Phase 3: Report Using the Review Contract

Use the contract sections exactly and keep the result action-oriented.

Example:

```text
Scope
- PR #128: Add DynamoDB-backed docs query path
- Affected domains: docs, _core
- Changed files: 7

Effect Answer
- This PR adds a new DynamoDB-backed query path in the docs domain and
  wires it through the DI container. It does not change existing RDB behaviour.
  No security-sensitive surfaces are touched.

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/security-checklist.md

Findings
- [OPEN][HIGH] Architecture checklist - src/docs/infrastructure/di/docs_container.py:18
  Impact: container wiring uses the wrong dependency source for DynamoDB mode.
  Recommended fix: switch to `core_container.dynamodb_client` and keep RDB wiring out.
- [OK][MEDIUM] Architecture checklist §5 - Test coverage: all 3 baseline test files present for docs domain
- [SKIP] Security checklist §4.2 - File Upload input validation: project-dna §8 and live code both confirm feature inactive

Drift Candidates
- target: docs/ai/shared/architecture-review-checklist.md
  reason: PR introduces DynamoDB-specific guidance that the shared checklist does not mention consistently.
  auto-fix: no
  sync-required: true

Next Actions
- Fix the container wiring issue.
- Run `/sync-guidelines` after the DynamoDB guidance is updated.
- Post the review to GitHub only after the findings are addressed.

Completion State
- complete with findings

Sync Required
- true
```

If no issues are found, still emit all sections and explicitly state
`Findings: none`, `Drift Candidates: none`, and `Sync Required: false`.

## Phase 4: Post to GitHub (Optional)

Ask before posting.

- `BLOCKING` findings present -> request changes
- only `HIGH` / `MEDIUM` / `LOW` / `NOTE` findings -> comment
- no findings and `Sync Required: false` -> approve or leave a clean comment

If `Sync Required: true`, do not treat the review as fully closed until the
follow-up sync path is acknowledged.

## Cross-Tool Review Prompt Template

Use this template when another tool or reviewer cross-checks a `/review-pr`
result, a PR diff, or a readiness decision. The purpose is a consistent input
and output frame; reviewers may disagree with the original review when the
evidence supports it.

```text
Cross-tool review for /review-pr (read-only). Do not modify files. Do not run
git commands.

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
- Prior review result: <Findings / Drift Candidates / Sync Required summary>

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/security-checklist.md
- docs/ai/shared/governor-paths.md when the change may be governor-changing
- Relevant changed files and surrounding code

Review Angles
1. Diff-scope correctness: did the review inspect the changed files and enough
   surrounding code to judge the shared rules?
2. Architecture and security rule grounding: are all findings backed by the
   shared sources above, with no tool-local rule invention?
3. Drift decision: is `Sync Required` correct, especially for shared rule
   sources, skill procedures, wrappers, and documented patterns?
4. Volatile facts: are branch, PR number, changed-file counts, file paths, and
   line references verified from current evidence?
5. Completion-gate closure: does the review distinguish open findings,
   resolved items, and follow-up sync work without masking risk?

Output format
- Scope
- Sources Loaded
- Findings: open issues only, each with severity, rule source, file:line,
  impact, and recommended fix
- Drift Candidates: target, reason, auto-fix, sync-required
- R-points: every cross-review point must include one closure category:
  Fixed, Deferred-with-rationale, or Rejected. Do not use non-canonical labels.
- Final Verdict: merge-ready / minor fixes recommended / still needs
  reinforcement / block merge
- Sync Required: true or false
```

## Self-Structured Review Checklist

Use when a cross-tool reviewer is unavailable (single-tool environment). Record
`reviewer: self-structured` in the Governor Footer. Work through each item
below and surface any findings as R-points with the same closure categories
(`Fixed` / `Deferred-with-rationale` / `Rejected`).

**F — Volatile workspace facts**
- [ ] All line numbers, file paths, branch names, and PR numbers cited in this
  review have been re-verified from current tool output (not from memory or
  prior-session snapshots).

**G — Closure discipline**
- [ ] Every question or alternative I raised during planning is closed with
  `Fixed`, `Deferred-with-rationale`, or `Rejected`. Labels such as "preserve",
  "maintain", or "leave as-is" are not used.

**H — Effect vs process**
- [ ] Effect questions ("does this break X?") are answered with evidence
  (grep, test run, diff scan), not substituted by process descriptions
  ("I followed the steps").

**I — Self-licensing check**
- [ ] Before defending any challenged conclusion, I re-verified the premise
  and checked for circular reasoning (concluding what I set out to prove).

**Contract verification**
- [ ] External interfaces (API response shapes, OpenAPI spec, `frontend-handoff.md`)
  match the implementation.

**Security surface**
- [ ] Any new endpoint, auth change, file upload, or external call has been
  checked against `docs/ai/shared/security-checklist.md`.

**Test coverage**
- [ ] If the change touches build-out, security, or external-contract paths,
  a regression test exists or the absence is explicitly deferred with rationale.
