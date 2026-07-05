# Target Operating Model

> Last synced: 2026-04-26 (initial draft, ADR 045 + Phase 1)
> Source of truth for the workflow, mandatory steps, exception handling, Claude/Codex alignment, and sample-workflow traces. The shared-constitution summary lives in [`AGENTS.md` § Default Coding Flow](../../../AGENTS.md); this document is the long-form companion.
> Sibling docs: [ADR 045](../../history/045-hybrid-harness-target-architecture.md) · [harness-asset-matrix.md](harness-asset-matrix.md) · [migration-strategy.md](migration-strategy.md)

## Purpose

This document answers issue #117 Required Output #2: define the hybrid Target Operating Model that the harness should converge to. Asset triage (the matrix) determines *what* exists; this document determines *how it operates*.

## §1 Default Coding Flow (7-Step)

Coding work proceeds through seven steps by default:

```
problem framing → approach options → plan → implement
                → verify → self-review → completion gate
```

| Step | Purpose | Owner skills (per layer) | Mandatory? |
|---|---|---|---|
| problem framing | Confirm the actual problem, scope, edge cases. Distinguish change-of-the-day vs. systemic issue. | `/plan-feature` Phase 0 (Requirements); `/fix-bug` Phase 1 (Reproduce); ad hoc | Mandatory by default |
| approach options | Compare 2~3 design-level candidates with trade-offs. Recommend exactly one. | `/plan-feature` Phase 1 (Approach Options) | Conditionally mandatory (architecture commitment present) |
| plan | Produce the implementation plan: tasks, ordering, validation. | `/plan-feature` Phase 4 (Tasks); `/fix-bug` Phase 2 (Trace) | Mandatory by default |
| implement | Write the code following project patterns. | `/new-domain`, `/add-api`, `/add-worker-task`, `/add-admin-page`, `/add-cross-domain`, `/migrate-domain`; `/execute-plan` (multi-task orchestration) | n/a (this *is* the work) |
| verify | Confirm the change does what it claims via tests, runs, or schema validation. | `/test-domain run`, `pytest`, `make demo`, `make demo-rag`, `alembic upgrade head` | Mandatory by default |
| self-review | Audit the change against project constraints before declaring done. | `/review-architecture`, `/security-review` (when applicable) | Mandatory by default |
| completion gate | Cross-check drift, generate ADR/follow-up if needed, signal end-of-work. | `/review-pr`, `/sync-guidelines` | Mandatory-by-default; non-blocking reminder via Phase 4 hook + Governor Footer Lint CI |

Steps are sequential. Returning to an earlier step is permitted (e.g. `verify` failure may force re-`plan`); skipping a mandatory step requires either an exception token (§3) or an automatic escape condition (§3 auto-escapes).

### Step interaction with skills

Each shared-procedure skill carries a `Default Flow Position` section that pins which step(s) the skill participates in. Implementation skills (Tier 2 Keep) belong to `implement`; review skills belong to `self-review` or `completion gate`; planning skills span `framing`/`approach options`/`plan`; `execute-plan` consumes an approved Execution Packet and orchestrates `implement` → `verify` → `self-review` → `completion gate` for complex / governor-changing / multi-task work (§4 Native execution workflow). See [harness-asset-matrix.md §Tier 2](harness-asset-matrix.md#tier-2--skills-3-layer-hybrid-c) for the per-skill mapping.

A skill must not invoke itself recursively. `/plan-feature` calling `/plan-feature` is forbidden; the recursion guard sits in each skill body.

## §2 Mandatory by Default

### What "implementation-class work" means

The mandatory-by-default rule applies when at least one of the following is true:

- The user requests a code change that will produce one or more committed files.
- The user requests creation of a new domain, endpoint, worker task, admin page, or cross-domain wiring.
- The user requests a migration, bug fix, or refactor that touches non-trivial code.

The rule does *not* apply when:

- The session is read-only investigation (no commit will be produced).
- The change is a doc-only edit (no source-file change).
- The change is a comment-only edit (logical equivalence preserved).
- The user has supplied a leading exception token on prompt line 1.

### Mandatory subset

`framing`, `plan`, `verify`, `self-review` are mandatory by default. `approach options` is conditionally mandatory: it must be performed when the change introduces or reshapes any of the following:

- A new domain or service boundary
- A cross-domain dependency (Protocol contract, etc.)
- A new optional infrastructure (RAG / Vector / LLM provider, etc.)
- A non-additive refactor that changes the responsibility matrix

If unsure, `approach options` is performed.

`completion gate` is mandatory-by-default (Phase 4 Stop hook shipped in #123 / PR #128). Non-blocking: the hook emits a reminder; the Governor Footer Lint CI enforces presence + shape when governance paths are touched.

### Mid-Task Scope Expansion (ADR 050)

The mandatory-by-default rule is evaluated **per unit of implementation-class work, not per prompt**. Discovering mid-execution that a needed capability does not exist is *new* implementation-class work — even though no new prompt was submitted. The agent must:

1. **Stop** implementing the discovered capability.
2. **Report** the gap to the user (what is missing, why the current task surfaced it).
3. **Route** to `/plan-feature` / `$plan-feature` (or ask the user to choose deferral) before any implementation edit for the new capability.

The distinguishing test: *is this change required by the approved plan's success criteria, or is it a capability the plan never mentioned?* Small gap-fixes that the current task's success criteria genuinely require are in-scope work, not expansions. Exception tokens keep their §3 semantics — a token that licensed skipping `plan` for the original prompt covers same-scope work only, not a mid-task capability addition.

Enforcement is advisory-first (ADR 050) and ships as a tool-specific adapter over one shared `governor.stage_gate` policy: on Claude a `PostToolUse Edit|Write` reminder (#268, `.claude/hooks/post_tool_stage_gate.py`); on Codex a Stop-time `systemMessage` segment (#269, `.codex/hooks/stop-sync-reminder.py` — Codex has no `PostToolUse`, so it bridges the Stop-time changed-file set to the shared single-file decision). Either fires once per session when a `.py` file under `src/` or `examples/` is edited while the work ledger's `workflow.stage` is `idle`/`complete`/`blocked` and no *plan-waiver* token marker (`[trivial]`/`[hotfix]`, incl. Korean equivalents) is active — `[exploration]` does not suppress it, since an implementation edit inside a declared read-only session is itself a signal (ADR 050 D6). Missing or unreadable ledger state stays silent (fail-open) — contributors without the maintainer workflow never see it.

## §3 Allowed Exceptions

Exceptions never override safety. The four-layer precedence from `AGENTS.md` § Default Coding Flow applies:

```
sandbox / approval policy
  > .codex/rules/* (forbidden / prompt)
    > safety hooks
      > Absolute Prohibitions
        > Default Coding Flow + exceptions
```

### Exception token vocabulary

Tokens appear only as the **leading bracketed token on the first line** of a prompt, followed by whitespace or end-of-line. NFKC normalisation is applied before matching.

```
^\s*\[(trivial|hotfix|exploration|자명|긴급|탐색)\](?:\s|$)
```

| Token | Meaning | Skips |
|---|---|---|
| `[trivial]` / `[자명]` | Self-evident change (typo, comment, rename in single file). | framing, approach, plan |
| `[hotfix]` / `[긴급]` | Urgent fix where time-cost of full flow is unjustifiable. | approach options only. `verify` and `self-review` still mandatory. |
| `[exploration]` / `[탐색]` | Read-only investigation, spike, or learning session. | All steps; nothing produces a commit. |

### Token use obligations

Using an exception token carries a follow-up obligation: the next commit message must record the rationale (one line is sufficient). Example:

```
fix: correct typo in user_service docstring

[trivial] used: doc-comment fix in single file, no logic change.
```

This obligation is enforced informally in Phase 1 (skill bodies request it) and may be checked by the Phase 4 completion gate hook.

### Auto-escapes (no token required)

The Default Flow does not impose mandatory steps when:

- `changed_files == 0` (read-only review, planning-only)
- All changed files are *general* docs (`README.md`, `CHANGELOG.md`, contributor guides, ordinary content under `docs/` outside the carve-out below), or contain only comment / whitespace edits
- The session was opened with read-only sandbox mode (e.g. `codex exec --sandbox read-only`)

Auto-escape detection is best-effort; the user may always restate their intent via an explicit token if the auto-detection fails.

#### Policy / harness doc carve-out (governance-loosening guard)

The doc-only auto-escape **does not apply** to policy or harness docs as defined in [`governor-paths.md`](governor-paths.md) Tier A. When any Tier-A path is in `changed_files`, the change is treated as governor-changing: full `framing` → `plan` → `verify` → `self-review` (with independent review sub-step, see §5) → `completion gate`. The rationale (Codex review R8): a governor that is strict on code but lax on its own rule sources will silently drift away from its own discipline.

The canonical path list and the small set of exclusions (e.g. log-only backfill PRs) live in [`governor-paths.md`](governor-paths.md). Do **not** duplicate the list here.

### What exceptions cannot do

Exception tokens never lift any of the following:
- Sandbox or approval-policy restrictions
- `.codex/rules/*` `forbidden` or `prompt` rules
- Safety-hook checks (security, destructive command, secret-leak)
- Absolute Prohibitions in `AGENTS.md`
- Pre-existing PR-time gate requirements (CI, reviewer approval)

If a workflow requires bypassing one of the above, the answer is to escalate to the user, not to add a token vocabulary.

## §4 Superpowers (Philosophy) Responsibility vs Local Overlay

This is the primary cross-tool clarification: what comes from the upstream "superpowers" inspiration, and what is project-specific overlay?

### Superpowers (philosophy) is responsible for

- The shape of the 7-step Default Coding Flow itself (brainstorm → plan → TDD-style verification → review).
- The discipline of "mandatory by default + narrow explicit exceptions".
- The recognition that strong default routing matters more than adding new skills.

### Local overlay is responsible for

- Each step's *concrete* skill mapping (Tier 2 Keep skills are project-specific).
- The 3-tier hybrid architecture, optional-infra DI pattern, error-mapper ACL, and every other ADR-level decision (040 / 042 / 043).
- The exception-token vocabulary, including Korean tokens.
- Tool-specific hook adapters (Claude vs Codex; see §5).
- All `harness-asset-matrix.md` content.
- Every skill body under `docs/ai/shared/skills/` and the wrappers under `.claude/skills/` and `.agents/skills/`.

### What this rules out

- Importing an external "superpowers" package and treating it as a dependency. The repo carries no such dependency.
- Substituting any project-specific skill with a generic philosophy reference.
- Allowing the philosophy port to weaken any architectural ADR.

### Native execution workflow (issue #257)

The native harness owns the execution workflow after the design phase. Upstream
superpowers may be used as a design lens while shaping the harness, but routine
project operation remains local: `/plan-feature` / `$plan-feature` produces an
Execution Packet, then `/execute-plan` / `$execute-plan` executes complex,
architecture-changing, governor-changing, or multi-task work.

The Execution Packet is the boundary between planning and implementation. It
contains Goal, Scope, Success Criteria, Selected Approach, Architecture Impact,
Task List, Verification Gates, and Review Gates. The packet is recorded in the
shared work ledger so Claude and Codex can resume with the same current task,
verification state, and review state.

Enforcement is advisory-first. Stop hooks may remind the agent when native
harness workflow state is missing, verification is pending, or governor-changing
work lacks recorded review state. Future PRs may promote only high-confidence
conditions to hard gates or CI failures after tests prove the detection avoids
exploration, trivial edits, and single-skill work.

### Model identity

This is **Mostly Local with Philosophy Overlay**, matching the bucket distribution in [harness-asset-matrix.md](harness-asset-matrix.md): ~80% Keep / ~20% Overlay / 0% Replace / 0% Drop (Phase 5 #124 closure; matrix is canonical). The philosophy port adds the framing / governance layer; the substantive content is and remains local.

## §5 Claude / Codex Alignment

`AGENTS.md` is canonical. Tool-specific adapters expose the shared rules in each tool's runtime model. The two tools have **different hook surfaces**, which has consequences for Phase 2~5.

### Surface differences

| Surface | Claude | Codex |
|---|---|---|
| SessionStart hook | yes | yes |
| UserPromptSubmit hook | absent today; added in Phase 2 | yes (existing) |
| PreToolUse matcher | `Edit`, `Write`, `Bash` | `Bash` only |
| PostToolUse matcher | `Edit`, `Write` | `Bash` only |
| Stop hook | yes | yes |
| File-level edits visible to PostToolUse? | **yes** (`Edit`/`Write` matcher) | **no** (`apply_patch` and similar bypass `Bash`) |

The asymmetry in the last row is critical (Codex review R7). Phase 3 verification-first cannot rely on Codex's `PostToolUse` because Codex performs file edits via mechanisms that do not match `^Bash$`.

### Adapter strategy

- **Claude side**: file edits trigger `PostToolUse Edit|Write`. Phase 3 verification-first hook attaches there to suggest test runs after a code edit.
- **Codex side**: file edits do not surface in `PostToolUse`. Phase 3 detection runs on the **Stop side** by computing `git status --porcelain` over the working tree and triggering the verification reminder when changed source files exist without a corresponding test run.
- **Both sides**: UserPromptSubmit recognises the exception-token vocabulary identically (Phase 2). As of Phase 5 (#124, Hybrid Harness v1 milestone), the shared parser, marker writer, lifecycle reader, verify-first decision, and completion-gate logic all live in [`.agents/shared/governor/`](../../../.agents/shared/governor/). Hook scripts under `.claude/hooks/` and `.codex/hooks/` are thin shims that import from this package; they cannot redeclare reminder strings or governor-paths globs inline (`tests/unit/agents_shared/test_governor_boundary.py`). The hybrid governance model — escape-token vocabulary, dual-tool adapters, scope-of-impact-driven independent review — is permanent; only the *implementation* moved into the shared module. ADR 047 retargets the independent review *capture location* from `governor-review-log/` to the PR-description `## Governor Footer` block (CI-linted) without changing the trigger or review obligation itself.

### Canonical-truth precedence

When tool runtime config conflicts with shared rules, shared rules in `AGENTS.md` win — but **only within the bands that shared rules cover**. A Codex-specific rule (e.g. `web_search="disabled"` default) is canonical for Codex; `AGENTS.md` does not override it. The Default Flow is explicitly subordinate to such tool runtime configuration (see `AGENTS.md` § Default Coding Flow precedence table).

### Where enforcement lives (issue #117 Q5)

| Location | Phase | Enforcement type |
|---|---|---|
| `AGENTS.md` § Default Coding Flow | 1 (this PR) | Constitutional guidance |
| `target-operating-model.md` (this file) | 1 | Long-form reference |
| Skill body (3-layer) | 1 | Per-skill mandatory phase + Default Flow Position |
| `.github/pull_request_template.md` § Governor Footer | 1 (Pillar 5; rewritten by ADR 047, generalized by ADR 048) | Required PR-description block carrying independent review provenance + closure counts; CI-linted via `tools/check_governor_footer.py` |
| ADR Consequences (`ADR{NNN}-G{N}` slots, e.g. ADR 047) | 1 (Pillar 4 successor; ADR 047 D3) | Durable governance constraints inherited across PRs; `governor-review-log/` is the closed historical archive |
| Session-start | 2 | Optional banner reminder |
| UserPromptSubmit hook | 2 | Token-recognition + soft route hint |
| PostToolUse / Stop side | 3 | Verification reminder (tool-specific adapter) |
| Stop completion gate | 4 | Hard reminder (commit-time) when verification was skipped without an exception token; **and** when policy/harness paths were touched without a Governor Footer block in the PR description (post-ADR-047 — replaces the prior governor-review-log entry check) |
| Shared parser/policy module | 5 | Single source for both adapters |

### Independent Review Cadence (Pillar 2)

Independent review is a sub-step of `self-review`, mandatory **only** when the change is governor-changing as defined in [`governor-paths.md`](governor-paths.md) (Tier A / B / C minus exclusions). Non-governor-changing PRs are exempt to avoid heavy ceremony.

**Review modes (one is sufficient per PR):**

| Mode | Description | `reviewer` field |
|---|---|---|
| `cross-tool` | Another AI tool reads the change set (e.g. `codex exec --sandbox read-only "<review prompt>"`, with stronger model/effort only when warranted) | tool name (e.g. `codex-cli`) |
| `self-structured` | Single-tool environment — apply the structured checklist in `skills/review-pr.md` § "Self-Structured Review Checklist" | `self-structured` |
| `human` | A human reviewer (not the PR author) reviews the governor-changing surface | `human:<github-handle>` |

Per round (each PR may need one or several):

1. **Trigger detection** — Stop or UserPromptSubmit hook (Phases 2~4) detects that `changed_files` intersects the governor-changing trigger glob defined in [`governor-paths.md`](governor-paths.md). Until those hooks land, the trigger detection is performed manually by the author against that file.
2. **Reviewer invocation** — invoke the chosen review mode. The shared prompt template for `cross-tool` and `self-structured` modes lives in `docs/ai/shared/skills/{review-pr,review-architecture,security-review,sync-guidelines}.md` "Cross-Tool Review Prompt Template" / "Self-Structured Review Checklist".
3. **R-points capture** — review output is annotated with `R1`, `R2`, … per finding, and the closure counts (`Fixed` / `Deferred-with-rationale` / `Rejected` per Guard G) are recorded in the PR description's `## Governor Footer` block (post-ADR-047). The pre-ADR-047 obligation to write `governor-review-log/pr-{NNN}-{slug}.md` is retired for new PRs; the directory is a closed historical archive.
4. **Resolution discipline** — every R-point is either fixed in the PR or explicitly deferred with a rationale; deferred items become "Inherited Constraints" carried in the relevant ADR's Consequences (`ADR{NNN}-G{N}` slot) when they are durable governance rules, in `project-dna.md` or domain docs when they are durable domain invariants, or in the footer's `pr-scope-notes` line when they apply only to the current PR.
5. **Self-application** — `/review-architecture` and `/sync-guidelines` outputs are summarised in the PR description prose (a heading, a few bullets) so reviewers can verify the change-surface was checked. They are no longer archived per-PR as a separate section since the value comes from running them, not from preserving the output.
6. **Final Verdict** — `merge-ready` / `minor fixes recommended` / `block merge`. Captured in the Governor Footer's `final-verdict` field.

Two recurring rounds are common and recommended for large governor-changing PRs:
- *Plan-stage round* — review the plan or design document before implementation.
- *Implementation round* — review the change set after implementation, before merge.

**Round cap:** resolve each R-point within 2 rounds (initial + follow-up). A third round is a signal to split the PR. The same PR may still iterate beyond 2 rounds for large changes, but each additional round should be justified.

### Model And Effort Cost Policy

Default to the cheapest model and reasoning effort that still fits the risk of
the task. Cost control must not weaken governance; it should route higher-cost
review only to changes where the extra signal is load-bearing.

| Work class | Default posture | Escalate when |
|---|---|---|
| Routine / mechanical | Default or cheaper coding model, low or medium effort, no broad doc loading | Tests fail in a non-obvious way, behavior is ambiguous, or the change crosses module boundaries |
| Local feature / bug fix | Default coding model, medium effort, targeted file reads | The change alters public APIs, data contracts, auth, storage, or long-lived architecture |
| Governor / security / external contract | Stronger model or higher effort allowed; independent review required when governor-changing | The first review surfaces unresolved R-points, threat modeling is uncertain, or cross-tool diversity is material |
| Cross-tool review | Start from the normal review prompt and read-only sandbox | Use a premium model or `xhigh` only as an escalation example, not as the default invocation |

For OpenAI API call sites in this repository, use only documented knobs:
`reasoning.effort` to cap reasoning-token spend, `max_output_tokens` (or the
endpoint-specific equivalent) to cap generated output, `prompt_cache_key` for
requests with shared long prefixes, and stable prompt-prefix layout (static
instructions first, dynamic user context last) to improve prompt-cache hits.
These are API-level controls; Codex/Claude CLI sessions should use the
equivalent model/effort routing only when those tools expose it explicitly.

## §6 Canonical Truth Map

| Concern | Canonical location |
|---|---|
| Shared constitution | `AGENTS.md` |
| Default Flow definition | `AGENTS.md` § Default Coding Flow + `target-operating-model.md` (this file) |
| Asset inventory | `harness-asset-matrix.md` |
| Phase / migration plan | `migration-strategy.md` |
| Top-level decisions | ADR 045 (and per-feature ADRs in `docs/history/`) |
| Skill detail (procedure) | `docs/ai/shared/skills/{name}.md` |
| Skill metadata + per-tool wrapper | `.claude/skills/{name}/SKILL.md` and `.agents/skills/{name}/SKILL.md` |
| Architecture rules | `AGENTS.md` + `.claude/rules/architecture-conventions.md` + ADRs |
| Claude rules (auto-load) | `.claude/rules/*.md` |
| Codex rules (prefix) | `.codex/rules/fastapi-agent-blueprint.rules` |
| Hook configuration | `.claude/settings.json` and `.codex/hooks.json` |
| Hook implementations | `.claude/hooks/*.sh` and `.codex/hooks/*.py` |

When two locations could plausibly host the same fact, the table above resolves the conflict in favour of the listed canonical. Drift between any two of them is what `/sync-guidelines` looks for.

## §7 Model Identity

The Target Operating Model is **Mostly Local with Philosophy Overlay**.

- "Mostly Local" because the bucket distribution is ~80% Keep / ~20% Overlay / 0% Replace / 0% Drop (Phase 5 #124 closure; 64 active assets). The substantive content of the harness remains local.
- "Philosophy Overlay" because the *governance* layer — Default Flow, mandatory subset, exception vocabulary, completion-gate idea — is borrowed from the superpowers philosophy and grafted on top.

This is not a balanced 50/50 hybrid. It is 80%-local-with-a-process-shell. That ratio is the answer to issue #117's Key Design Question 7 ("How should Claude and Codex stay aligned without duplicating too much harness logic?"): they share the philosophy overlay; the substantive content is the same per-tool because both read identical shared documents.

---

## Appendix A — Eight Workstreams from Issue #117

| Workstream | Where it lives in this model | Phase |
|---|---|---|
| `asset-triage` | [harness-asset-matrix.md](harness-asset-matrix.md) | 0 (this PR) |
| `default-flow` | §1, `AGENTS.md` § Default Coding Flow | 1 (this PR) |
| `verification-first` | §1 `verify` step; Codex R7 adapter spec in §5 | 3 |
| `self-review` | §1 `self-review` step | 1 (skill body) → 4 (hook) |
| `completion-gate` | §1 `completion gate` step | 4 |
| `exception-model` | §3 | 1 (vocabulary defined) → 2 (parser) |
| `cross-tool-consistency` | §5 + Phase 5 shared module | 1 (precedence) → 5 (consolidation) |
| `migration-path` | [migration-strategy.md](migration-strategy.md) | 0 (this PR) |

## Appendix B — Sample Workflow Traces

Three traces demonstrate the model on representative tasks. These traces are the validation evidence required by issue #117 (the issue asks the contributor to "apply the new structure to three sample workflows and walk through each").

### Trace 1 — Feature Planning (`add OAuth login to user domain`)

| Step | What happens | Skill / Tool |
|---|---|---|
| framing | Clarify provider scope (Google? all OAuth2?), session-storage, tenancy. | `/plan-feature` Phase 0 |
| approach options | Mandatory because cross-domain wiring is involved. Compare: (1) provider-specific implementations, (2) generic `OAuthClient` Protocol, (3) PydanticAI Agent with provider tooling. | `/plan-feature` Phase 1 |
| plan | Recommended Approach (2) chosen. Tasks: Protocol + 2 Adapters + Service + Schema + tests + 1 ADR. | `/plan-feature` Phase 2~4 |
| implement | `/new-domain oauth` to scaffold the new domain; then `/add-cross-domain` to wire `oauth → user`; finally `/add-api` for the callback endpoint. | `/new-domain` → `/add-cross-domain` → `/add-api` |
| verify | `pytest tests/unit/oauth/`; `pytest tests/e2e/test_oauth_flow.py`; `make dev` smoke. | `/test-domain run` |
| self-review | `/review-architecture oauth`; `/security-review oauth` (auth surface). | both |
| completion gate | `/review-pr` then `/sync-guidelines` (drift candidate likely from new ADR). | both |

All seven steps engage. No exception token needed. This is the canonical path.

### Trace 2 — Bug Fix (`/users/me returns 500 for guest user`)

| Step | What happens | Skill / Tool |
|---|---|---|
| framing | Reproduce the failure; identify guest-user code path. | `/fix-bug` Phase 1 |
| approach options | Skipped (no architecture commitment). | — |
| plan | `/fix-bug` Phase 2 (Trace) identifies root cause: missing `None` guard in `UserService.get_me`. | `/fix-bug` Phase 2 |
| implement | One-line fix in `user_service.py`. | direct edit |
| verify | Add regression test in `tests/unit/user/test_user_service.py::test_get_me_guest`. | `/test-domain run` |
| self-review | Short-form scan only — single-file fix, no layer interaction. Still mandatory by default; `[trivial]` does **not** skip this step (see §3 token skip table). | — (manual quick scan; no skill needed) |
| completion gate | `/review-pr` only (drift unlikely). | `/review-pr` |

Exception token usage: if the fix is genuinely urgent and the test is added retroactively, a `[hotfix]` prompt is acceptable; the verify step still occurs in the same commit. `[trivial]` is *not* used here because a regression test is required.

### Trace 3 — Medium Refactor (`split UserService into UserQueryService and UserCommandService`)

| Step | What happens | Skill / Tool |
|---|---|---|
| framing | Why split? Driver: ADR 011 generic constraints + growing query surface. | `/plan-feature` Phase 0 |
| approach options | Mandatory because architecture commitment. Compare: (1) CQRS-style split, (2) facade with internal split, (3) keep current. | `/plan-feature` Phase 1 |
| plan | Approach (1) chosen. Tasks: extract Query DTOs, mirror service split, update DI container, update admin wiring, update tests. | `/plan-feature` Phase 4 |
| implement | Service / DTO / DI / admin / tests modified in incremental commits. | `/add-cross-domain`-style incremental edits |
| verify | Existing test suite must pass green. New tests added for `UserQueryService` and `UserCommandService`. `/test-domain run` confirms. | `/test-domain run` |
| self-review | `/review-architecture user` is the most important step here; ADR candidate. | `/review-architecture` |
| completion gate | `/review-pr` flags drift candidates → ADR 046 (or equivalent). `/sync-guidelines` follows. | both |

Refactors require approach options because the *commitment* is architectural even when the surface is local.

### Trace 4 (Bonus) — Design Review (this PR's Phase 0.5)

This trace is a meta-trace: the present PR's Phase 0.5 was itself a sample of cross-tool design review.

| Step | What happened | Skill / Tool |
|---|---|---|
| framing | Determine whether Claude-only design risks Codex-side blind spots. | direct discussion |
| approach options | Compare: (1) Codex auto-call via Bash, (2) user manual paste, (3) plan-only annotation. Chose (1). | direct discussion (architecture commitment present — touched cross-tool design) |
| plan | Add Phase 0.5 step to plan; list questions to ask Codex. | direct edit of plan file |
| implement | Install codex CLI; run `codex exec --sandbox read-only` with a structured review prompt, escalating model only if the review surface requires it. | `codex exec` |
| verify | Read codex review output; cross-check 7 review points against the plan. | manual reading |
| self-review | Apply the 7 review points to the plan as a "Codex Review feedback applied" section. | direct plan edit |
| completion gate | Save the trace as Appendix B Trace 4 here so future cross-tool design has a precedent. | this entry |

This trace shows that the model accommodates non-coding workflows (design review is "implementation" of a plan document).

## Appendix C — Eight Design Questions (issue #117) — Resolution Pointers

Detailed answers live in [ADR 045 §Eight Design Questions](../../history/045-hybrid-harness-target-architecture.md#eight-design-questions-issue-117--resolution-map). The pointers below name the canonical section of this document.

1. Project-specific value vs commodity scaffolding → harness-asset-matrix.md Tier classification.
2. Stay local / overlay / replace / drop → matrix bucket column.
3. Minimum viable process governor → §1 + §3.
4. Mandatory by default for coding work → §2.
5. Where enforcement lives → §5 ("Where enforcement lives" table).
6. Valid exception → §3.
7. Claude / Codex alignment → §5.
8. Rigor without friction → §1 (mandatory subset) + §3 (escape lanes) + §7 (model identity).
