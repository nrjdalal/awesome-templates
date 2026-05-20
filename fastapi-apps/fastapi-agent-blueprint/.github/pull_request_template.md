## Related Issue
- Fixes #
- Closes #

## Change Summary
-

## Type of Change
- [ ] feat: New feature
- [ ] fix: Bug fix
- [ ] refactor: Code restructuring
- [ ] docs: Documentation
- [ ] chore: Build/tooling
- [ ] test: Tests
- [ ] ci: CI/CD
- [ ] perf: Performance
- [ ] style: Code style

## Checklist
- [ ] Architecture rules followed (no Domain -> Infrastructure imports)
- [ ] Tests pass
- [ ] Linting passes (`ruff check src/`)

## How to Test
-

---

## Governor Footer (required for governor-changing PRs — ADR 047)

Required if your PR is *governor-changing* per [`docs/ai/shared/governor-paths.md`](../docs/ai/shared/governor-paths.md) (Tier A / B / C minus exclusions). Otherwise set `trigger: no` and the rest of the block is optional (or delete the section entirely).

Source of truth: [`AGENTS.md` § Default Coding Flow](../AGENTS.md#default-coding-flow) + [`docs/ai/shared/governor-paths.md`](../docs/ai/shared/governor-paths.md) + [ADR 047 §D2](../docs/history/047-governor-review-provenance-consolidation.md).

The block below is parsed by `tools/check_governor_footer.py` (run via the `Governor Footer Lint` CI workflow). Fill it verbatim and replace the placeholder values. Lint shape: each field on its own line, exact field name, single space after the colon, no extra fields, no duplicates, declared order. The closure-category labels in `r-points-*` counts must be exactly `Fixed`, `Deferred-with-rationale`, or `Rejected` (Guard G — closure labels are documented in the PR body for human readers and counted in this footer for the linter).

```
## Governor Footer
- trigger: yes/no
- reviewer: codex-cli/self-structured/human:<handle>/...
- rounds: N
- r-points-fixed: N
- r-points-deferred: N
- r-points-rejected: N
- touched-adr-consequences: ADR{NNN}-G{N}, ADR{NNN}-G{N} / none
- pr-scope-notes: <one-line summary or "none">
- final-verdict: merge-ready/minor-fixes/needs-reinforcement/block
- links: <PR url>, <prior-log url or "n/a">
```

Field guidance:

- `trigger` — `yes` if `changed_files` matches any Tier A/B/C glob in [`governor-paths.md`](../docs/ai/shared/governor-paths.md) and no full-set Exclusion applies; otherwise `no` (and you may delete this footer).
- `reviewer` — the independent reviewer mode: a tool name (e.g. `codex-cli`, `claude-code`), `self-structured` (single-tool structured checklist), or `human:<github-handle>`. Multiple modes comma-separated. When using `self-structured`, include a checklist evidence summary (checked items + any deferred rationale) in the PR body above the footer.
- `rounds` — total independent review rounds run on this PR (plan stage + implementation stage counts as 2; aim for ≤ 2).
- `r-points-fixed/deferred/rejected` — closure counts using exactly the three Guard G categories.
- `touched-adr-consequences` — list `ADR{NNN}-G{N}` slot IDs (the canonical form used by ADR 047 IC Classification Table; e.g. `ADR047-G3`, `ADR048-G1`) this PR amends; `none` if no durable-governance constraint changed. Comma-separated.
- `pr-scope-notes` — short prose for `pr-scope` invariants this PR self-imposes (e.g. "minimal RBAC scope; permission tables follow-up"). They are **not** promoted to ADR Consequences.
- `final-verdict` — last independent review verdict.
- `links` — PR URL plus any companion artefact URL (e.g. a related issue or, for historical context, a frozen `docs/history/archive/governor-review-log/pr-{N}-*.md` entry). Use `n/a` if there are no extra links.

Doc-only escape hygiene: if your PR is doc-only, confirm the changes do **not** touch policy / harness docs listed in [`governor-paths.md`](../docs/ai/shared/governor-paths.md) Tier A. Touching those files disqualifies the doc-only auto-escape — see [`target-operating-model.md` §3](../docs/ai/shared/target-operating-model.md).
