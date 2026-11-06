# Target Operating Model

> Last synced: 2026-11-06 via #420
> Source of truth for the workflow, mandatory steps, exception handling, Claude/Codex/Antigravity alignment, and sample-workflow traces. The shared-constitution summary lives in [`AGENTS.md` § Default Coding Flow](../../../AGENTS.md); this document is the long-form companion.
> Sibling docs: [ADR 045](../../history/045-hybrid-harness-target-architecture.md) · [harness-asset-matrix.md](harness-asset-matrix.md) · [historical migration plan](../../history/archive/harness-context/migration-strategy.md)

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

Architecture and durable workflow choices use [scoped ADR evidence](adr-evidence.md) within existing plan, ticket, review and sync fields (ADR 064). Read applicable clauses and current implementation evidence; ADR intent does not prove runtime effects or grant permission.

### Step interaction with skills

Each shared procedure and both tool wrappers retain a compact `Default Flow Position` pointer to this canonical per-skill table. Step and Phase counts remain procedure contracts; compacting routing does not relax their parity checks. Command names below use `/skill`; Codex uses the matching `$skill` name.

| Skill | Step(s) | approach-options condition | Routes after | Recursion guard |
|---|---|---|---|---|
| `plan-feature` | `framing` (Phase 0), `approach options` (Phase 1), `plan` (Phases 2–4) | Compare 2–3 approaches when an architecture commitment exists; exception tokens follow §3. | **Stop at the approved Execution Packet.** Execution is a separate explicit step via `execute-plan` (ledger → `executing`), or a single self-evident follow-up with a `[trivial]`/`[hotfix]` token. Never auto-continue in the same turn; ADR 054 applies (Claude hard block, Codex Stop advisory). | No recursive planning; implementation skills must not re-enter planning for their own task. ADR 050 scope expansion is separate. |
| `execute-plan` | `implement` → `verify` → `self-review` → `completion gate` | Settled by the approved Execution Packet from `plan-feature`. | Execute mapped implementation skills (`new-domain`, `add-api`, `add-cross-domain`, `add-worker-task`, `add-admin-page`, `migrate-domain`); run packet verification/review gates and close the ledger only after they pass. | No additional per-skill guard. |
| `new-domain` | `implement` | Always: new domain boundary, optional AI infrastructure decision, or cross-domain integration surface. Settle the boundary, key fields and Optional AI Infra Variant with `plan-feature` upstream. | `test-domain {name} run` (or domain unit tests) → `review-architecture {name}` → `sync-guidelines` if shared docs reference the domain. | Do not invoke `plan-feature` from inside this skill. |
| `add-api` | `implement` | Required for non-trivial response shapes, cross-domain access or new validation patterns; skip for straightforward CRUD with existing DTOs. | `test-domain {name} run` → `review-architecture {name}` if layer interactions changed → `sync-guidelines` if shared docs reference the endpoint. | Do not invoke `plan-feature` from inside this skill. |
| `add-worker-task` | `implement` | Required for new event types, broker patterns or interleaving with existing transactions; skip for established Taskiq additions. | `test-domain {name} run` and an applicable integration smoke run via `make worker` → `sync-guidelines` if shared docs reference the task. | Do not invoke `plan-feature` from inside this skill. |
| `add-admin-page` | `implement` | Required for sensitive fields, new admin auth surfaces or unprecedented service contracts; skip routine config-only pages. | `test-domain {name} run` → `security-review` if secrets/PII/tokens may be exposed → `sync-guidelines` if shared docs reference admin patterns. | Do not invoke `plan-feature` from inside this skill. |
| `add-cross-domain` | `implement` | Always: a cross-domain dependency is an architecture commitment. Compare Protocol shapes and dependency direction with `plan-feature` upstream. | `test-domain {consumer} run` and `test-domain {producer} run` → `review-architecture {consumer}` → `sync-guidelines`. | Do not invoke `plan-feature` from inside this skill. |
| `migrate-domain` | `implement`, `verify` | Required for indexed-column changes, transactional constraints or backfills; skip additive nullable columns following existing Alembic patterns. | `alembic upgrade head` against a clean DB and `test-domain {name} run` → manual autogenerated-revision diff plus Zero-Downtime Safety Review (ADR 056) → `sync-guidelines` if shared docs reference the migration. | Manual user invocation; no additional guard. |
| `test-domain` | `verify` (`run`); `implement` (`generate`) | No additional condition; generated tests must then be exercised via `run`. | `review-architecture {name}` if layer interactions changed → `review-pr` and, if drift, `sync-guidelines`. | Verify-step skill; no additional guard. |
| `review-architecture` | `self-review` | No additional condition. Invoke after implementation/verification changed layer interactions, base classes, generics, DI or Protocol contracts; a single-file architectural refactor still requires this audit. | `sync-guidelines` if drift candidates exist; otherwise `review-pr`. | No self-recursion or invocation of `plan-feature`. |
| `security-review` | `self-review` | No additional condition. Invoke for auth, passwords, tokens, sensitive admin/log fields, file uploads, external requests or credential migration. | `sync-guidelines` if drift candidates exist; otherwise `review-pr`. | No self-recursion or invocation of `plan-feature`. |
| `review-pr` | `completion gate` | No additional condition; final change-set review follows implementation, verification and self-review. | `sync-guidelines` if `Drift Candidates` or `Sync Required: true`. | No self-recursion or invocation of `plan-feature`. |
| `sync-guidelines` | `completion gate`; follow-up to `self-review` when drift exists | No additional condition. Required after review-detected drift, changes to shared rule sources, or ADR creation/amendment. | End of work; close documentation/workflow drift without re-entering the flow. | No self-recursion or invocation of `plan-feature`. |
| `fix-bug` | `framing` (Reproduce), `plan` (Trace), `implement` (Fix), `verify` (Verify) | Required if the trace reveals multiple candidate layers (Service/Router/Schema) or a missing architectural pattern; skip single-layer single-line fixes. | `review-architecture` if layer interactions changed; `security-review` if security-relevant → `review-pr`. | No self-recursion or `plan-feature` for the bug’s own framing/plan (Phases 1+2 own them). ADR 050 still requires stop → report → `plan-feature` for a missing capability; scope expansion is not recursion. |
| `onboard` | Outside coding flow; explicit session-start orientation | Not a coding-flow phase; `[exploration]` is appropriate for accompanying read-only investigation. | Subsequent coding is a fresh Default Flow run. | No self-recursion or invocation of `plan-feature`. |
| `trace` | Outside coding flow; read-only exploration | None; investigate only when requested. | Return cited execution path and unknown edges to the caller; no edits or stage mutation. | Do not recurse or invoke other skills. |
| `why` | Outside coding flow; read-only exploration | None; investigate only when requested. | Return cited decision history and uncertainty to the caller; no edits or stage mutation. | Do not recurse or invoke other skills. |

A skill must not invoke itself recursively. The seven guarded skills named in the table above retain a one-line recursion guard in every layer; the table also preserves implementation-skill planning guards. ADR 050 and ADR 054 in §2 govern scope expansion and the planning/execution boundary.

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

Enforcement is advisory-first (ADR 050) and ships as a tool-specific adapter over one shared `governor.stage_gate` policy: on Claude a `PostToolUse Edit|Write` reminder (#268, `.claude/hooks/post_tool_stage_gate.py`); on Codex a Stop-time `systemMessage` segment (#269, `.codex/hooks/stop-sync-reminder.py` — Codex has no file-edit `PostToolUse` matcher, so it bridges the Stop-time changed-file set to the shared single-file decision); on Antigravity an `AfterAgent` JSON `systemMessage` segment (`.antigravity/hooks/stop-sync-reminder.py`) wired by `.gemini/settings.json`. Each adapter fires once per session when a `.py` file under `src/` or `examples/` is edited while the work ledger's `workflow.stage` is `idle`/`complete`/`blocked` and no *plan-waiver* token marker (`[trivial]`/`[hotfix]`, incl. Korean equivalents) is active — `[exploration]` does not suppress it, since an implementation edit inside a declared read-only session is itself a signal (ADR 050 D6). Missing or unreadable ledger state stays silent (fail-open) — contributors without the maintainer workflow never see it.

### Plan→Execute Boundary (ADR 054)

`/plan-feature` (`$plan-feature`) **ends at the approved Execution Packet — it does not implement.** Beginning implementation is always a separate, explicit step: the user invokes `/execute-plan` (`$execute-plan`) — which advances the ledger to `executing` and routes to the implement skills internally — or authorises a single self-evident follow-up with a `[trivial]`/`[hotfix]` token. A bare verbal go-ahead does not release the block. Sliding from an approved plan straight into edits is a distinct failure mode from Mid-Task Scope Expansion above: there the plan never mentioned the capability; here a plan exists but execution was never formally started.

This boundary is enforced by a **sibling gate** on the same `governor.stage_gate` policy, keyed to `PLAN_EXECUTE_GATED_STAGES = {planned}` — disjoint from the ADR 050 `GATED_STAGES` set. It fires when a `.py` file under `src/`/`examples/` is edited while `workflow.stage == "planned"` and no plan-waiver token (`[trivial]`/`[hotfix]`, incl. Korean equivalents) is active. **Enforcement strength is asymmetric by tool** (ADR054-G4):

- **Claude — hard block.** A `PreToolUse Edit|Write` hook (`.claude/hooks/pre_tool_stage_block.py`) returns exit 2, blocking the edit and surfacing `PLAN_EXECUTE_REMINDER` to the model. Unlike the ADR 050 advisory it does **not** dedup — it holds on every edit (ADR054-G1 D5). There is deliberately no Claude `PostToolUse` advisory for `planned`: the block intercepts the same cases pre-edit, so one would be dead code (ADR 054 D4).
- **Codex — Stop advisory.** Codex has only Bash `PreToolUse` matching and cannot intercept file edits; `plan_execute_segment` in `.codex/hooks/stop-sync-reminder.py` emits the same reminder at Stop time (once per session), mirroring the #269 `stage_gate_segment`.

Release paths: invoke `/execute-plan` (advances the ledger to `executing`, the gate stops matching) or use a plan-waiver token. The gate is **best-effort by fail-open** (ADR054-G5): any unreadable ledger, import failure, or malformed payload allows the edit — a workflow gate must never wedge editing. It also depends on `/plan-feature` writing `stage="planned"`; if that write is skipped the stage stays `idle`/`complete` and only the ADR 050 advisory applies (never a false block). As a workflow gate it ranks **below** the four precedence layers (§3) — safety hooks and Absolute Prohibitions still take priority, and plan-waiver tokens suppress it.

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
- Tool-specific hook adapters (Claude, Codex, and Antigravity; see §5).
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
shared work ledger so Claude, Codex, and Antigravity can resume with the same current task,
verification state, and review state.

Enforcement is advisory-first. Stop hooks may remind the agent when native
harness workflow state is missing, verification is pending, or governor-changing
work lacks recorded review state. Future PRs may promote only high-confidence
conditions to hard gates or CI failures after tests prove the detection avoids
exploration, trivial edits, and single-skill work.

### Ticket session boundary (ADR 060)

[Ticket workflow](ticket-workflow.md) defines the native brief, epic/ticket/task
criteria, fresh serial execution, PR risk floor, precision-filter review, integrated
sync, and prospective measurement. The approved issue/packet, PR and CI provide
durable intent/evidence; hydrate the existing local ledger as resume state. Keep
ADR 054's explicit execute-plan boundary and gate behavior. Trace/why investigations
are on demand, read-only and isolated; their shared procedures replace duplicated
bug-path examples and onboarding history stories.

### Model identity

This is **Mostly Local with Philosophy Overlay**. The [harness navigator](harness-asset-matrix.md#bucket-distribution-summary)
links the generated inventory and reviewed bucket map; use its check command for
current counts instead of copying percentages. The philosophy port adds the
framing / governance layer; substantive content remains local.

## §5 Claude / Codex / Antigravity Alignment

`AGENTS.md` is canonical. Tool-specific adapters expose the shared rules in each tool's runtime model. The three tools have **different hook surfaces**, which has consequences for prompt, tool, and session-end enforcement.

### Surface differences

| Surface | Claude | Codex | Antigravity / Gemini CLI |
|---|---|---|---|
| SessionStart hook | yes | yes | yes |
| Prompt hook | `UserPromptSubmit` | `UserPromptSubmit` | `BeforeAgent` |
| Pre-tool matcher | `Edit`, `Write` (stage boundary) | `Bash` only | `replace`, `write_file`, `run_shell_command` |
| Post-tool matcher | `Edit`, `Write` | `Bash` only | `replace`, `write_file`, `run_shell_command` |
| Session-end hook | `Stop` | `Stop` | `AfterAgent` |
| File-level edits visible to post-tool hooks? | **yes** (`Edit`/`Write` matcher) | **no** (`apply_patch` and similar bypass `Bash`) | **yes** for `replace` / `write_file`; shell writes are command-derived |

The file-edit asymmetry determines stage-gate delivery: Claude receives native edit events; Codex computes changed files at Stop because its post-tool matcher covers Bash only. ADR 061 retired the former verify-first reminder instead of treating command-name logs as successful verification.

### Adapter strategy

- **Claude side**: `PreToolUse Edit|Write` enforces the plan→execute boundary; `PostToolUse Edit|Write` formats Python and runs the once-per-session stage advisory. The per-edit content scanner and verify-first/log processes are retired (ADR 061).
- **Codex side**: Bash hooks retain shell safety, formatting and supported actual verification-outcome recording. File-edit stage checks and workflow/verification advisories run at Stop using the changed-file set. No command-name log is written and no verify-first segment remains.
- **Antigravity side**: `.gemini/settings.json` wires Gemini / Antigravity events to `.antigravity/hooks/`. Prompt handling runs on `BeforeAgent`, shell safety and formatting/outcome recording run on `BeforeTool` / `AfterTool`; sync / completion / workflow / stage-gate reminders are merged on `AfterAgent`. Runtime exception/stage markers stay under `.antigravity/state/`; per-command verify logs and verify-first reminders are retired by [ADR 061](../../history/061-retire-runtime-verify-and-content-heuristics.md).
- **All adapters**: prompt hooks recognise the exception-token vocabulary identically (Phase 2). As of Phase 5 (#124, Hybrid Harness v1 milestone), the shared parser, marker writer, lifecycle reader, stage-gate and completion-gate logic all live in [`.agents/shared/governor/`](../../../.agents/shared/governor/). Hook scripts under `.claude/hooks/`, `.codex/hooks/`, and `.antigravity/hooks/` are thin shims that import from this package; they cannot redeclare reminder strings or governor-paths globs inline (`tests/unit/agents_shared/test_governor_boundary.py`). The hybrid governance model — escape-token vocabulary, tool-specific adapters, scope-of-impact-driven independent review — is permanent; only the *implementation* moved into the shared module. ADR 047 retargets the independent review *capture location* from `governor-review-log/` to the PR-description `## Governor Footer` block (CI-linted) without changing the trigger or review obligation itself.

### Canonical-truth precedence

When tool runtime config conflicts with shared rules, shared rules in `AGENTS.md` win — but **only within the bands that shared rules cover**. A Codex-specific rule (e.g. `web_search="disabled"` default) is canonical for Codex; an Antigravity-specific setting in `.gemini/settings.json` is canonical for Antigravity. `AGENTS.md` does not override tool runtime capabilities. The Default Flow is explicitly subordinate to such tool runtime configuration (see `AGENTS.md` § Default Coding Flow precedence table).

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
| Post-tool result adapters | ADR 061 | Codex/Antigravity record supported actual verification outcomes; help/search/unknown/cancelled results do not establish a pass. Former Phase 3 verify-first/log runtime is retired. |
| Stop completion/workflow adapters | 4 + ADR 052/061 | Non-blocking missing-verification/workflow and Governor Footer reminders; marker consumption stays unconditional. Governor Footer Lint CI, not the reminder, blocks a malformed/missing required PR-description footer. |
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

1. **Trigger detection** — Stop or UserPromptSubmit hook (Phases 2~4) detects that `changed_files` intersects the governor-changing trigger glob defined in [`governor-paths.md`](governor-paths.md). The adapters are shipped; the author still verifies the detected scope against that file.
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
| Historical phase / migration plan | [migration archive](../../history/archive/harness-context/migration-strategy.md) |
| Top-level decisions | ADR 045 (and per-feature ADRs in `docs/history/`) |
| Skill detail (procedure) | `docs/ai/shared/skills/{name}.md` |
| Skill metadata + per-tool wrapper | `.claude/skills/{name}/SKILL.md` and `.agents/skills/{name}/SKILL.md` |
| Architecture rules | `AGENTS.md` + `.claude/rules/architecture-conventions.md` + ADRs |
| Claude rule projections | `.claude/rules/*.md`: unconditional files load by default; files with `paths:` load for matching paths |
| Codex rules (prefix) | `.codex/rules/fastapi-agent-blueprint.rules` |
| Antigravity rules (adapter) | `.antigravity/rules/*.md` |
| Hook configuration | `.claude/settings.json`, `.codex/hooks.json`, and `.gemini/settings.json` |
| Hook implementations | `.claude/hooks/*.sh`, `.codex/hooks/*.py`, and `.antigravity/hooks/*.py` |

When two locations could plausibly host the same fact, the table above resolves the conflict in favour of the listed canonical. Drift between any two of them is what `/sync-guidelines` looks for.

## §7 Model Identity

The Target Operating Model is **Mostly Local with Philosophy Overlay**.

- "Mostly Local" because the substantive harness content remains local; current
  asset counts and buckets come from the generated inventory linked by the matrix
  navigator, not a copied historical percentage.
- "Philosophy Overlay" because the *governance* layer — Default Flow, mandatory subset, exception vocabulary, completion-gate idea — is borrowed from the superpowers philosophy and grafted on top.

The local implementation carries the process shell. This answers issue #117's Key Design Question 7 ("How should Claude and Codex stay aligned without duplicating too much harness logic?"), now extended to Antigravity: the tools share the philosophy overlay and read the same shared policy; current inventory counts remain generated rather than copied.

---

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

> Historical design workstreams and resolution pointers: [Appendices A/C archive](../../history/archive/harness-context/target-operating-model-appendices.md).
