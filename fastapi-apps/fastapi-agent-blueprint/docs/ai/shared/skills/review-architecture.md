# Architecture Compliance Audit

## Default Flow Position

This skill participates in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow) at the **`self-review`** step.

It is invoked after `implement` and `verify` for changes that altered layer interactions, base classes, generics, DI wiring, or cross-domain Protocol contracts. Auto-escapes do **not** apply: a single-file refactor that changed a Service/Repository signature still wants this audit.

After self-review, route to:
- `completion gate` — `/sync-guidelines` if drift candidates were detected, otherwise `/review-pr`

Recursion guard: do **not** invoke `/review-architecture` recursively from within itself, and do not invoke `/plan-feature` from inside this skill.

## Purpose

Use this skill to audit one domain or the full repository against the project's
shared architecture rules, then decide whether the audit also requires
`/sync-guidelines` follow-up.

## Review Contract

This audit emits the shared [Review Protocol §3 output contract](../review-protocol.md#3-output-contract):
`Scope`, `Effect Answer`, `Sources Loaded`, `Findings` (OPEN only), `Coverage` (OK/SKIP),
`Drift Candidates`, `Verdict`, `Next Actions`, `Completion State`, `Sync Required`.

- This skill applies the **`ARCH` dimension** ([Review Protocol §1](../review-protocol.md#1-review-dimensions-concern-based-stable-ids)) in depth via the 10-category checklist below; every `ARCH` finding is `rule-source`-based and cites its checklist category ([Finding Basis §2](../review-protocol.md#2-finding-basis-anti-hallucination-rule)).
- `Verdict` is **`N/A (audit-only scope)`** — a structural audit, not a behavior PASS/FAIL ([Review Protocol §4](../review-protocol.md#4-intent--pass-state)).
- `Effect Answer` is required (Guard H); write `Effect Answer: N/A — process question` for checklist-only process questions.

### Severity Taxonomy

State and severity are defined in [Review Protocol §3](../review-protocol.md#3-output-contract):
review state `OPEN` / `OK` / `SKIP`; severity `BLOCKING` / `HIGH` / `MEDIUM` / `LOW` / `NOTE`.

## Audit Target

- `all` -> audit all domains under `src/`, excluding `_core` and `_apps`
- `{domain}` -> audit only `src/{domain}/`
- `examples/{name}` -> audit `examples/{name}/` against the **examples
  profile** described below

### Examples Profile (vs production)

`examples/` are reference code, not production domains. Two checklist
categories apply differently:

- **§5 Test Coverage**: examples require only the unit test declared in
  `examples/README.md` Contributing, not the full
  `docs/ai/shared/test-files.md` baseline (3 baseline + applicable
  conditional). Missing factories / integration / e2e tests are not
  findings in the examples profile.
- **§2 Auth (security-checklist)**: examples may omit auth dependencies
  on `@router.post|put|delete`. The omission is intentional reference
  simplicity, not a finding, unless the example's stated pattern claims
  to demonstrate auth.

All other categories (layer dependency, conversion, DI, bootstrap,
naming) apply identically to examples and production domains.
**§10 Examples Copy-Flow Compliance** applies *only* in the examples
profile — production `src/` domains are never copied, so absolute
`src.*` imports are correct there.

## Category Coverage

Inspect the 10 architecture checklist categories defined in
`docs/ai/shared/architecture-review-checklist.md`.

1. Layer Dependency Rules
2. Conversion Patterns Compliance
3. DTO / Response Integrity
4. DI Container Correctness
5. Test Coverage
6. Worker Payload Compliance
7. Admin Page Compliance
8. Bootstrap Wiring
9. DynamoDB Domain Compliance
10. Examples Copy-Flow Compliance (applies only to `examples/` targets)

## Phase 0: Resolve Scope and Load Rule Sources

1. Resolve the audit target and enumerate the domains included in the run.
2. Load:
   - `AGENTS.md` — including § Language Policy. If audited files in Tier 1
     contain non-English prose outside the bilingual-token allowlist,
     surface as a `Findings` violation with `Sync Required: true`.
   - `docs/ai/shared/project-dna.md`
   - `docs/ai/shared/architecture-review-checklist.md`
3. Use `docs/ai/shared/security-checklist.md` only when an architecture issue
   overlaps with a security boundary such as auth, logging, or storage.

## Phase 1: Audit Against Severity-Tagged Rules

Apply the checklist category by category.

- use grep-style checks for code-auditable rules first
- read surrounding files when a rule depends on wiring or conversion flow
- mark optional categories such as DynamoDB only when the domain actually uses
  that variant

Do not collapse missing tests, dependency violations, and DTO exposure into a
single issue. Each broken rule gets its own finding.

## Phase 2: Determine Drift Candidates and Sync Requirement

The audit must explicitly decide whether the shared references are still
accurate.

Mark `Sync Required: true` when:
- the audited changes touch shared rule sources, shared skill procedures, or
  wrappers
- the audit reveals that `project-dna`, checklists, or wrapper summaries no
  longer describe the implemented architecture
- the audit reveals a new documented pattern that should be added to the shared
  references

If the code is already correct but the docs are behind, report that as a
`Drift Candidates` item instead of forcing a fake code finding.

## Phase 3: Report Using the Review Contract

Example:

```text
Scope
- Target: docs
- Audited domains: docs

Effect Answer
- The docs domain wires an RDB-backed query path; one service imports infrastructure directly.

Sources Loaded
- docs/ai/shared/review-protocol.md
- docs/ai/shared/architecture-review-checklist.md
- AGENTS.md

Findings
- [OPEN][BLOCKING][ARCH] src/docs/domain/services/docs_service.py:12 — basis: rule-source (architecture-review-checklist §1)
  Impact: domain layer imports infrastructure directly, breaking the layering rule.
  Recommended fix: introduce a Protocol in the domain layer and invert the dependency.

Coverage
- [OK][ARCH] architecture-review-checklist §4 DI container — providers.DeclarativeContainer + providers.Factory used correctly
- [SKIP][ARCH] architecture-review-checklist §9 DynamoDB — no infrastructure/dynamodb/ directory in docs domain

Drift Candidates
- target: docs/ai/shared/project-dna.md
  reason: the current admin page pattern differs from the documented layout.
  auto-fix: yes
  sync-required: true

Verdict
- N/A (audit-only scope)

Next Actions
- Refactor the direct import.
- Run `/sync-guidelines` after the admin page pattern reference is updated.

Completion State
- complete with findings

Sync Required
- true
```

When the audit is clean, still emit every section: `Findings: none`, the `Coverage` records,
`Verdict: N/A (audit-only scope)`, `Drift Candidates: none`, and `Sync Required: false`.

## Cross-Tool Review Prompt Template

Use this template when another tool or reviewer cross-checks a
`/review-architecture` result, an audited domain, or an architecture-related
readiness decision. The purpose is a consistent input and output frame; findings
must remain grounded in shared architecture sources and live code evidence.

```text
Cross-tool review for /review-architecture (read-only). Do not modify files. Do
not run git commands.

Context
- Repo: fastapi-agent-blueprint
- Audit target: <all / domain / examples/name>
- Issue link: <#NNN or none>
- Round: <0 plan / 1 implementation / 2 gate-on-gate / N>
- original user question: <verbatim or concise restatement>
- success metric: <what the user said would count as success>
- Inherited constraints: <list of ADR{NNN}-G{N} consequence IDs from prior governance ADRs (post-ADR-047); for historical context, see governor-review-log/ archive>

What you are reviewing
- Architecture surface: <layers, DTO conversion, DI, repository, worker,
  admin, bootstrap, DynamoDB, or examples profile>
- Prior audit result: <Findings / Drift Candidates / Sync Required summary>
- Important exclusions: <examples profile, inactive optional infra, or none>

Sources Loaded
- AGENTS.md
- docs/ai/shared/project-dna.md
- docs/ai/shared/architecture-review-checklist.md
- docs/ai/shared/security-checklist.md when the architecture issue overlaps a
  security boundary
- Live code evidence from audited files and relevant wiring

Review Angles
1. Layer and dependency rules: did the audit verify Domain, Service,
   Repository, Infrastructure, and Interface boundaries from current code?
2. Conversion and DTO integrity: did it check Request, DTO, Response, Model,
   and DynamoModel flow without inventing mapper or entity patterns?
3. DI and bootstrap correctness: did it inspect container providers, selectors,
   task wiring, and admin/service contracts where applicable?
4. Drift decision: did documented-pattern changes become drift candidates
   instead of being hidden inside a clean architecture verdict?
5. Volatile facts: are domains, file paths, line references, and optional
   feature claims verified from current repository evidence?

Output format
- Scope
- Sources Loaded
- Findings: OPEN issues only, each with severity, dimension ID (ARCH), basis, file:line,
  impact, and recommended fix
- Coverage: OK/SKIP records with evidence
- Drift Candidates: target, reason, auto-fix, sync-required
- R-points: every cross-review point closes as Fixed / Deferred-with-rationale / Rejected
  (AGENTS Guard G vocabulary; no non-canonical labels)
- Verdict: N/A (audit-only scope)
- Final Verdict: clean / minor fixes recommended / still needs architecture
  review / block merge
- Sync Required: true or false
```

## Self-Structured Review Checklist

Use when a cross-tool reviewer is unavailable (single-tool environment). Record
`reviewer: self-structured` in the Governor Footer. Work through each item
below and surface any findings as R-points with the same closure categories
(`Fixed` / `Deferred-with-rationale` / `Rejected`).

**F — Volatile workspace facts**
- [ ] All line numbers, file paths, and domain counts cited in this review have
  been re-verified from current tool output (not from memory or prior snapshots).

**G — Closure discipline**
- [ ] Every question or alternative raised during the review is closed with
  `Fixed`, `Deferred-with-rationale`, or `Rejected`. Non-canonical labels not
  used.

**H — Effect vs process**
- [ ] Architecture-compliance questions ("does this violate the layer rule?")
  are answered with grep/read evidence, not process descriptions.

**I — Self-licensing check**
- [ ] Before defending an "adequate" verdict, the premise was re-verified and
  circular reasoning checked.

**Layer-rule verification**
- [ ] No Domain → Infrastructure imports (grep result: zero matches).
- [ ] No Mapper classes, no Entity pattern remnants.
- [ ] DTO / VO / Model object roles follow `architecture-conventions.md`.

**Test coverage**
- [ ] Domain has at least the baseline test suite (unit, integration, or e2e
  depending on profile — see skill §5 Test Coverage section).
