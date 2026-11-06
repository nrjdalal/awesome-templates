## Review Packet

- Intent / ticket: <one sentence + issue; Fixes # only for satisfied criteria>
- Risk floor: <low/medium/high + reasons from `uv run python tools/review_packet.py --base origin/main`; raise for semantic risk>
- Files to review first: <ranked paths + why; remaining files in details>
- Verification: <exact commands → observed concise output and exit status>
- Not verified / limits: <what remains unknown, or none with evidence>

<details>
<summary>Change details and review evidence</summary>

## Change Summary

- <behavior, compatibility, and relevant design decisions; for an affected choice,
  link the ticket/packet's scoped Decision Basis and explain the governing clause's
  effect on the choice with current code/test evidence or an explicit unknown>

Use the [scoped ADR evidence contract](../docs/ai/shared/adr-evidence.md) inside this
change summary; an ID list or Accepted status is not implementation proof. If no
architectural decision is affected, one scope-based reason is enough.

## Type of Change

- [ ] feat
- [ ] fix
- [ ] refactor
- [ ] docs
- [ ] chore / test / ci / perf / style

## Review and Sync

- Review mode / precision-filter result / verified finding closures:
- Fallback reason, if applicable:
- Sync in this PR / release or post-merge exception:
- Measurement evidence / unobserved fields (see [ticket workflow](../docs/ai/shared/ticket-workflow.md)):

## Checklist

- [ ] Architecture rules followed
- [ ] Tests pass; executed commands and observed output are recorded above
- [ ] Lint and formatting pass (`uv run ruff check` / `uv run ruff format --check` for the relevant scope)
- [ ] Verification evidence above reflects commands actually run
- [ ] Required review and sync completed; unresolved findings explicitly recorded

### Governor Footer guidance

Required for governor-changing paths in [governor-paths](../docs/ai/shared/governor-paths.md),
with exclusions applied: set `trigger: yes` and fill every field. Otherwise keep the
default `trigger: no`; the linter then ignores the remaining lines, so leave or delete
them, or delete the footer. [AGENTS.md](../AGENTS.md#default-coding-flow) defines review obligations.
The real footer below stays outside this collapsed block and outside code fences.

Use one field per line, the exact order and single space after the colon. The
reviewer is the actual tool, `self-structured` (include checklist evidence here),
or `human:<handle>`. Count all independent rounds honestly. Findings close as
`Fixed`, `Deferred-with-rationale`, or `Rejected`; give rationale/evidence here.
`touched-adr-consequences` contains existing `ADR{NNN}-G{N}` IDs or `none`.
`final-verdict` is `merge-ready`, `minor-fixes`, `needs-reinforcement`, or `block`.
`links` is comma-separated http(s) URLs, with optional `n/a` entries.
Policy/harness docs do not receive the general doc-only escape. Validate the
completed body with `python3 tools/check_governor_footer.py <body.md>`.

</details>

## Governor Footer
- trigger: no
- reviewer: <actual tool or fallback>
- rounds: N
- r-points-fixed: N
- r-points-deferred: N
- r-points-rejected: N
- touched-adr-consequences: none
- pr-scope-notes: <one-line scope>
- final-verdict: merge-ready/minor-fixes/needs-reinforcement/block
- links: <PR URL>, n/a
