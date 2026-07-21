# 056. Zero-Downtime Migration Safety — No-Downtime Playbook + Unsafe-DDL Advisory

- Status: Accepted
- Date: 2026-07-20
- Related issue: none (maintainer-initiated from a recurring operational pain point)
- Builds on (does not supersede): [ADR 045](045-hybrid-harness-target-architecture.md) — the advisory-first Default Coding Flow. Reuses the advisory→hard-block promotion path demonstrated by [ADR 050](050-midtask-scope-expansion-gate.md) → [ADR 054](054-plan-execute-boundary-hard-gate.md).

## Summary

To reduce the deployment risk of routine schema changes in a zero-downtime
deployment environment, we add (1) a **no-downtime migration playbook** to the
RDB migration runbook and (2) an **advisory checker** that scans Alembic
revisions for unsafe DDL. Both are advisory-first (non-blocking). Plan-time
data-model contracts and plan-vs-implementation conformance checks were
considered and are explicitly **out of scope**.

## Background

### Trigger

A maintainer working question: *"I keep getting table structures I did not
intend, and every deploy carries another migration."* The framing evolved
across the discussion. It started as a plan↔implementation mismatch ("the
generated schema differs from what I planned"), but re-framing surfaced the
real pain: schema changes are **frequent and expected** (a new feature or an
upgrade almost always touches tables), the deployment target is
**zero-downtime**, and the actual cost is the **deployment risk** of a change
(locks / downtime / non-reversible migrations), not the change frequency
itself.

The current harness has **no migration-safety surface at all**:
`docs/ai/shared/skills/migrate-domain.md` covers `alembic revision
--autogenerate` plus a manual diff review; `docs/operations/rdb-migrations.md`
covers the first rollout and a rollback note. Neither mentions locking, online
DDL, expand-contract, or app/schema compatibility windows.

### Decision type

Experience-based correction driven by an operational pain point. The scope was
narrowed twice during design (see Alternatives) — an honest record of "we first
reached for a heavier plan-time contract, then cut it back to the surface that
actually addresses the stated pain."

## Problem

In a zero-downtime environment, the assumption "frequent migrations are fine as
long as they do not affect live deploys" only holds if **each** migration is
actually deploy-safe. That precondition is unverified today:

- Unsafe DDL (a `NOT NULL` add without a safe default, a non-`CONCURRENTLY`
  index build, a column drop/rename, a type change, a blocking constraint) can
  take a table lock and stall reads/writes during a rolling deploy.
- App code and schema must stay mutually compatible across a rolling window
  (expand-contract); a drop/rename that lands in one step breaks the old app
  version still serving traffic.
- Nothing in the harness tells the author which category a given revision falls
  into, so the safety judgement is made ad hoc, per person, per PR.

Frequency is not the defect. A perfectly planned schema still changes as
requirements evolve; the target is to make each change **safe**, not to make
changes rare.

## Alternatives Considered

### A. Plan-time data-model contract + plan-vs-implementation conformance

Fix the data model as a plan-time artefact (Mermaid `erDiagram` + constraint
table), carry it into the Execution Packet as a contract, and add a
`review-architecture` category that compares the planned spec against the
implemented `Model` (advisory). **Rejected.** It targets plan↔implementation
*agreement*, which the re-framing showed is not the real pain: a schema that
matches the plan can still be near-sighted and still be unsafe to deploy. It
adds a review category (10→11 fan-out) whose weight is not justified by the
stated problem.

### B. Plan-time design-evolution review (near-sightedness prevention)

Add a plan-time checkpoint that reviews whether the design can absorb expected
change without a rewrite. **Rejected as not harness-solvable.** Extensible
data-model design is a judgement problem (domain knowledge, normalization
trade-offs, index strategy) already classified L3 in
`planning-checklists.md` §4. A harness can add more questions but cannot make
the answers good; it adds weight without moving the outcome.

### C. No-downtime playbook + unsafe-DDL advisory checker — chosen

Document the safe/unsafe DDL rules (playbook) and detect the unsafe subset
automatically at revision-review time (checker). The unsafe-DDL rule set is
**well defined** (see the reference linters in Rationale), which is exactly why
it automates well — the highest value-per-weight of the three options.

### D. Hard-blocking gate on unsafe DDL

Same detection as C, but fail the commit/CI when an unsafe pattern is found.
**Deferred.** `project-dna.md` §0 lists hard-blocking automation gates as a
non-goal (the harness nudges; humans and CI decide), and a hard block would
false-positive on legitimate, deliberately-staged changes. We start advisory
and reserve promotion to a hard gate for a future ADR once the advisory is
shown to be repeatedly ignored — the same advisory→hard-block path ADR 050 →
ADR 054 already walked.

## Decision

1. **No-downtime playbook** — extend `docs/operations/rdb-migrations.md` with
   the expand-contract (parallel-change) pattern in three stages
   (expand → backfill → contract), a per-engine safe/unsafe DDL table
   (PostgreSQL / MySQL / SQLite), and backfill + rollback guidance.
2. **Unsafe-DDL advisory checker** — `tools/check_migration_safety.py` scans
   `migrations/versions/*.py` at the Alembic-`op` level (AST-based, mirroring
   `tools/check_examples_copyflow.py`) and reports the unsafe patterns in the
   playbook. Each finding carries *why it is unsafe*, the *safe alternative*,
   and a *playbook link*. Advisory by default (exit 0); a `--strict` flag
   (exit 1) exists for opt-in CI hardening but is not wired into any gate here.
3. **pre-commit hook** — register the checker as a `verbose`, non-blocking
   advisory hook over `migrations/versions/*.py`, in the same spirit as the
   existing warn-only `state-lifecycle-check`.
4. **Skill integration** — `migrate-domain`'s review step consults the checker
   output and the playbook before applying a revision.
5. **Scope boundary** — plan-time data-model contracts (Alternative A) and
   plan-vs-implementation conformance are **not** adopted. The gap being closed
   is deployment safety of the change, not agreement between plan and code.

## Rationale

- The unsafe-DDL rule set is an established, cross-ecosystem body of knowledge
  ([squawk](https://squawkhq.com/docs/rules) for PostgreSQL SQL,
  [strong_migrations](https://github.com/ankane/strong_migrations) for the
  Rails ecosystem, the MySQL
  [online-DDL operations matrix](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html)).
  Encoding a conservative subset of it is deterministic and low-false-positive
  — the property that makes an advisory worth having.
- Advisory-first keeps the harness consistent with `project-dna.md` §0 and
  avoids blocking the legitimate, deliberately-staged migrations that a
  zero-downtime workflow relies on. The `--strict`/CI promotion path stays open
  without being taken prematurely.
- The blueprint supports three RDB engines whose online-DDL guarantees differ
  (PostgreSQL fast-default + `CONCURRENTLY` + `NOT VALID`; MySQL
  `ALGORITHM=INSTANT/INPLACE`; SQLite's rebuild-heavy `ALTER`). The playbook
  and checker treat **PostgreSQL as the first-class target** (the common
  production engine) and annotate engine differences, rather than assuming one
  deployment model.
- Narrowing away Alternatives A/B keeps the change smaller than the initially
  proposed plan-time contract while directly addressing the stated pain — the
  right altitude for a harness that is already gate-dense.

### Self-check

- [x] Addresses the root cause (deploy-safety of each change), not the symptom
  (migration frequency).
- [x] Right altitude for current scale — advisory doc + checker, no new
  hard gate, engine-neutral.
- [x] A reader in six months can see why plan-time contracts were rejected and
  why advisory (not hard block) was chosen.
- [x] Records the decision process (two scope narrowings) rather than
  justifying a pre-made conclusion.

## Consequences

- Enforcement surface: `docs/operations/rdb-migrations.md` (playbook),
  `tools/check_migration_safety.py` (+ `tests/unit/tools/`), `.pre-commit-config.yaml`
  (advisory hook), `docs/ai/shared/skills/migrate-domain.md` + its Claude and
  Codex (`.agents/skills/migrate-domain/`) wrappers, `.claude/rules/commands.md`,
  `.claude/rules/project-status.md`. No `src/` runtime change.
- The checker is **not** rowed in `docs/ai/shared/harness-asset-matrix.md`: that
  matrix inventories governor-provenance assets, and general `tools/` checkers
  (`check_examples_copyflow.py`, `check_language_policy.py`,
  `check_state_lifecycle.py`) are not rowed there either.
  `check_migration_safety.py` follows that precedent — no matrix count change.
- The checker is advisory: a maintainer can still commit and deploy an unsafe
  revision. The residual risk is accepted (advisory-first) and mitigated by the
  playbook, the pre-commit warning, and the `migrate-domain` review step.
- Governor-changing (Tier A `docs/history/**` + `docs/ai/shared/**`, Tier B
  `.claude/**`, Tier C `.pre-commit-config.yaml`): requires an independent
  review recorded in the PR's `## Governor Footer`.

### Durable Governance Constraints

- **ADR056-G1** — The migration-safety checker is **advisory** (non-blocking,
  exit 0 by default). Promoting any condition to a hard block (failing
  pre-commit or CI without opt-in `--strict`) requires a new ADR and evidence
  that the advisory is repeatedly ignored — the ADR 050 → ADR 054 path. This
  honors the `project-dna.md` §0 non-goal on hard-blocking automation gates.
- **ADR056-G2** — The unsafe-DDL rule set has a **single source of truth**: the
  per-engine table in `docs/operations/rdb-migrations.md`. The checker's
  detected patterns must stay aligned with that table; changing one without the
  other re-enters this ADR.
- **ADR056-G3** — Scope boundary is durable: plan-time data-model contracts and
  plan-vs-implementation conformance checks are **non-goals** of this decision.
  Reintroducing either re-enters this ADR (they were deliberately cut, not
  overlooked).
- **ADR056-G4** — Engine neutrality: the checker and playbook treat PostgreSQL
  as the first-class target and **annotate** MySQL/SQLite differences rather
  than hard-coding a single deployment model. Removing the engine annotations
  or assuming one deploy strategy re-enters this ADR.
