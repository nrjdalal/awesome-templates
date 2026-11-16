# 066. Prompt Provider Contract — Code-Owned Boundary Tail, Self-Hosted Store Next

- Status: Accepted
- Date: 2026-11-16 (decision and recording date)
- Record type: contemporaneous
- Decision evidence: approved Execution Packet on [#447](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/447), revised after the owner dropped the Langfuse provider for operational burden
- Related issue: #447 (contract); #451 (implementation of Decision 5 — see [Implementation note](#implementation-note-451-2026-11-16))
- Amends / supersedes: amends [ADR 046](046-otel-core-langfuse-recipe-prompt-domain-defer.md) §4 (implements the deferred `get_active` contract) and Problem §3 (narrows the rejection of a self-built editor to the scope listed there; the minimum store defined below is accepted for the follow-up). ADR 046 §1 (OTEL core), §2 (Langfuse trace recipe) and §3 (ledger columns) remain in force.
- Related: [ADR 042](042-optional-infrastructure-di-pattern.md) (optional infrastructure), [ADR 049](049-admin-identity-realm-separation.md) (admin identity and page permissions), [ADR 051](051-runtime-llm-guardrails.md) (runtime guardrails)

## Summary

ADR 046's first trigger for prompt management is met: non-developers must be able
to change agent personas without a deploy. This ADR ships the part every editing
backend needs — the `get_active` provider contract, a code-owned boundary tail that
is always composed last, and ledger linkage — with one implementation that serves
the code text. Langfuse and Logfire were evaluated as the editing backend and
rejected. Operator editing will be a minimal self-hosted, DB-backed store delivered
in a follow-up ticket, whose required minimum and deliberate omissions are fixed
here.

*Update:* the store shipped in #451 — see the
[Implementation note](#implementation-note-451-2026-11-16).

## Background

**Trigger.** ADR 046 §4 deferred the prompt domain until either "a non-developer
needs to edit prompts without code deployment" or "3+ distinct prompts require
version management". #447 records the first condition as met: planners and
operators need to tune prompts without a release, and the need is expected to
continue. The second condition is not met — two production prompts exist
(`docs_answer`, `classification`).

**Decision type.** Upfront design against a reserved contract, not a correction
after experience. ADR 046 already shipped the anchors: the `PromptSnapshot` VO,
the `PromptSource` vocabulary (`inline` / `langfuse` / `self`), the four nullable
prompt columns on the `ai_usage` ledger, and a `prompt_snapshot` parameter on
`track_agent_usage` that no production caller passed.

**Revision within #447.** The first implementation of this ADR added a Langfuse
provider behind an opt-in Selector. Before merge the repository owner dropped it:
running Langfuse is a larger operational commitment than the feature it would
serve. This record states the revised decision; the Langfuse provider never
shipped.

## Problem

1. Personas were `Final[LiteralString]` module constants passed to the
   PydanticAI `Agent` constructor. Changing one required a code change and a deploy.
2. The ledger could not say which prompt served a call, so a bad edit could not
   be traced to the requests it affected — the gap ADR 046 Problem §3 called out
   for rollbacks.
3. Making prompt text runtime data must not weaken the LLM01 boundary. The
   persona and the "treat wrapped content as untrusted DATA" guidance were one
   `LiteralString` concatenation; an editable prompt that included the guidance
   would let an operator — or anyone holding the operator's credentials — delete it.
4. An editing backend has to be chosen, and ADR 046 Problem §3 rejected a
   self-built editor while the obvious external candidates carry their own
   operational or dependency cost.

## Alternatives Considered

### A. Langfuse prompt management — rejected (operational burden)

MIT-licensed and already the project's opt-in trace recipe, and its UI supplies
versioning, diff, labels and RBAC. But a self-hosted production Langfuse is a
stack of its own — PostgreSQL, ClickHouse, Redis, S3-compatible storage (MinIO)
and the web/worker containers — to upgrade, back up and monitor, all to serve two
personas. Langfuse Cloud removes that burden but makes a blueprint's request path
depend on an external SaaS and its credentials. A provider was built and reviewed
in #447; its synchronous SDK also needed a bounded-wait thread design and log
filtering to stay off the request path, which is further evidence of the
integration cost. The trace recipe of ADR 046 §2 is unaffected.

### B. Logfire `ManagedPrompt` (via `pydantic-ai-harness`) — rejected

Native to PydanticAI, but available only as commercial SaaS, which conflicts with
the provider-neutral, self-hostable direction of ADR 046.

### C. Langflow — rejected

A visual workflow builder with its own runtime. Adopting it would replace the
PydanticAI agent stack rather than manage that stack's prompts.

### D. Full self-built prompt domain + editor — rejected

The scope ADR 046 Problem §3 listed (diff, rollback, audit, variable validation,
preview, label workflow, RBAC, concurrent-edit handling) still exceeds the need and
crosses the "admin-panel product" non-goal.

### E. Contract now, minimal self-hosted store next — chosen

Ship the contract, the boundary split and the ledger linkage now; build a small
DB-backed store with only the properties an operator cannot safely work without,
on infrastructure the project already runs (RDB, NiceGUI admin, admin permissions,
audit log).

## Decision

1. **Contract.** `PromptProviderProtocol.get_active(name, *, default) -> PromptSnapshot`
   in `src/_core/domain/protocols/prompt_provider_protocol.py`. The caller always
   passes the code persona as `default`, so a provider needs no registry of its own
   and an unreachable backend degrades to code text. Implementations must not raise
   for a backend failure.
2. **One implementation today.** `InlinePromptProvider`
   (`src/_core/infrastructure/prompt/inline_prompt_provider.py`) returns `default`
   with `source="inline"`. `CoreContainer.prompt_provider` is a plain
   `providers.Singleton` — no Selector, no environment variable, no settings, no
   extra — because there is nothing to opt into yet. The follow-up store swaps this
   one provider. *(#451: swapped for `DbPromptProvider`, still a plain Singleton —
   the store lives in the mandatory RDB, and an empty store serves exactly what
   `InlinePromptProvider` served. `InlinePromptProvider` and `inline_snapshot`
   remain for the degraded path and tests.)*
3. **Editable surface: persona only.** `compose_instructions(persona, tail)` in
   `src/_core/infrastructure/llm/prompt_boundaries.py` appends the code-owned tail
   (`RAG_INSTRUCTIONS_TAIL`, `CLASSIFIER_INSTRUCTIONS_TAIL`) after the resolved
   persona. `tail` is typed `LiteralString`, so pyright rejects runtime text in that
   slot. Instructions are passed per `agent.run(..., instructions=...)`, not at
   `Agent` construction: PydanticAI places constructor instructions before run-time
   ones, which would put an edited persona *after* the boundary guidance. Input
   escaping and the ADR 051 guardrails are unchanged; the prompt-leak check runs
   against the resolved instructions.
4. **Ledger linkage.** The real answer agent and classifier pass the resolved
   snapshot to `track_agent_usage` on every call, so `ai_usage` rows record
   `prompt_name` and `prompt_source=inline`; `prompt_version` and
   `external_prompt_ref` are null for inline calls. No migration: the columns exist
   since ADR 046 §3.
5. **Operator editing is a follow-up: a minimal self-hosted store.** It revisits
   ADR 046 Problem §3 on these grounds: that list described a general-purpose
   prompt product, while two code-registered personas need only the properties
   below, and each is small on infrastructure the project already has. Required
   minimum:
   - append-only versions; an active-version pointer per prompt name, so rollback
     is moving the pointer;
   - saving a version is separate from activating it;
   - editing is limited to prompt names registered in code — no free-form names;
   - content must be non-empty and within a length cap;
   - every save and activation is written to the existing admin audit log;
   - a dedicated admin permission gates editing;
   - any store failure degrades to the code text (`source="inline"`), per
     Decision 1;
   - no per-process cache: one indexed read per call. LLM latency dominates that
     read, and without a cache there is no propagation window between processes.

   Deferred, not required for the first version: diff view, a pre-activation test
   run, multiple labels, prompt variables, and concurrent-edit handling beyond an
   optimistic version check.

   *Status (#451):* #449 shipped the contract (Decisions 1–4); #451 implemented
   this minimum as written, with no deferred item added. Where each property lives
   is listed in the [Implementation note](#implementation-note-451-2026-11-16).

### Out of scope

Per-tenant prompts (no tenancy model exists), A/B traffic routing, the
`examples/*` chatbots (they stay inline as copy-flow standalones), and the stub
agents (they call no model and resolve no prompt).

## Rationale

The provider boundary is placed at the persona rather than at the whole
instruction string because the two halves have different owners. The persona is
product behaviour — tone, scope, format — which is exactly what operators asked to
tune. The boundary tail is a security control whose correctness depends on the
escape-wrapping in `_format_prompt`; it changes only with that code, so it stays
in code. Splitting them now lets the editable surface arrive later without the
security surface growing with it.

Shipping the contract before the store is deliberate: the composition order and
ledger linkage are the parts that are easy to get wrong and expensive to retrofit,
and they are fully testable with the inline provider and a fake provider. The
store then becomes an infrastructure swap behind a pinned contract.

Rejecting Langfuse trades a ready-made editing UI for not operating a five-service
stack. The minimum in Decision 5 is the subset of ADR 046 Problem §3 whose absence
would make editing unsafe (no rollback, no audit, no permission, failure takes the
request down); the deferred items make editing more comfortable, not safer.

### Self-check

- [x] Does this decision address the root cause, not just the symptom?
- [x] Is this the right approach for the current project scale?
- [x] Will a reader understand "why" 6 months from now without extra context?
- [x] Am I recording the decision process, or justifying a conclusion?

## Consequences

- **ADR066-G1** — The boundary tail is code-owned. A consumer that resolves a
  persona from a provider must compose instructions with `compose_instructions`
  (tail last, `LiteralString`) and pass them per run. Constructor `instructions=`
  combined with a runtime persona reverses the order and is a defect.
- **ADR066-G2** — A prompt provider never raises into the request path. Backend
  failure degrades to the caller's `default` with `source="inline"`; a provider
  must not record a stored version for a call that ran on code text
  (`inline_snapshot` is public for that degraded path).
- **ADR066-G3** — A consumer that resolves a prompt passes the snapshot to
  `track_agent_usage`, so the ledger can attribute a call to a prompt version.
- **ADR066-G4** — The prompt store meets the Decision 5 minimum, including no
  per-process cache, and keeps editing behind a dedicated admin permission with
  audit-log entries. *(#451: `PromptStoreService` enforces the write rules below
  the admin page; `DbPromptProvider` reads once per call; the `prompts` fixed
  permission key gates the page and is re-checked on every write; saves,
  activations and reverts are audited as `PROMPT_VERSION_SAVE` /
  `PROMPT_ACTIVATE` / `PROMPT_REVERT`, including refused writes.)*
- **ADR066-G5** — The admin page shows both the active stored version and the
  code default, and offers "revert to code default" (deactivating the stored
  version). *(#451: `/admin/prompts`, one card per registered prompt.)*

**Trust-boundary change (in force since #451).** Before the store the persona was
`LiteralString` text that passed code review. With the store it is operator data,
so the `prompts` permission is equivalent to changing agent behaviour in
production. Accepted limit: a compromised account holding that permission can
change agent behaviour; the boundary tail, guardrails and audit log limit and
record what an edit can do but do not prevent it.

**Blind spot.** An active stored version overrides the code default, so a
developer who edits a persona in code sees no change in an environment where a
stored version is active. ADR066-G5 exists to make that state visible and
reversible.

**For forks.** `PydanticAIAnswerAgent` and `PydanticAIClassifier` no longer pass
`instructions=` to the `Agent` constructor; a subclass relying on that must move to
`compose_instructions` and run-time instructions.

**Decision basis** (per [adr-evidence.md](../ai/shared/adr-evidence.md)):

| Decision / claim | ADR, status and exact clause | Applicability / limits | Current evidence and disposition |
|---|---|---|---|
| `get_active` is the consumer contract | ADR 046 (Accepted) §4 | Prompt resolution for `_core` RAG and classification adapters | `PromptProviderProtocol`; `test_prompt_providers.py::test_inline_provider_satisfies_the_protocol`; conform (signature gains `default`) |
| Trigger to build prompt management | ADR 046 §4 trigger conditions | First condition only | #447 problem statement; new decision (this ADR) |
| Self-built editor rejected | ADR 046 Problem §3 | Editing backend | Narrowed to the Decision 5 minimum for the follow-up; amended by this ADR |
| Disabled path serves a working provider | ADR 042 (Accepted) Decision §1–§2 | `CoreContainer.prompt_provider` (plain Singleton, no Selector) | `core_container.py`, `test_optional_infra.py::test_prompt_provider_is_the_db_store` (renamed in #451 when the Singleton became `DbPromptProvider`); conform |
| Inline provider returns the code text | ADR066-G2 | `InlinePromptProvider` | `test_prompt_providers.py::test_inline_returns_the_code_text`; conform |
| Guardrails unchanged | ADR051-G1 | Answer agent and classifier | `test_adversarial_prompts.py`; conform |
| Hostile persona cannot displace the tail | ADR066-G1 | Both consumers | `test_pydantic_ai_answer_agent_prompt.py`, `test_pydantic_ai_classifier_prompt.py` (`test_default_instructions_are_code_persona_then_boundary_tail`, `test_operator_persona_cannot_displace_the_boundary_tail`); conform |
| Ledger names the prompt that served a call | ADR066-G3, ADR 046 §3 | Real agent calls, including guardrail blocks | `test_guardrail_usage_recording.py` (`test_rag_row_records_inline_prompt_by_default`, `test_rag_row_records_resolved_prompt_version`, `test_guardrail_block_row_still_names_the_prompt`); conform |
| Store write rules: registered names, non-empty, length cap, append-only, save ≠ activate | Decision 5, ADR066-G4 | `PromptStoreService`, `prompt_version` table | `test_prompt_store.py` (`test_save_rejects`, `test_save_accepts_exactly_the_length_cap`, `test_save_appends_and_never_changes_what_is_served`, `test_version_text_is_never_rewritten`, `test_unique_constraint_rejects_a_duplicate_number`, `test_registration_is_idempotent_and_rejects_a_second_default`, `test_both_agents_register_their_code_persona`); conform (#451) |
| Rollback is moving the pointer; optimistic check | Decision 5 | `activate`, `revert_to_code_default` | `test_prompt_store.py` (`test_activate_rollback_and_revert`, `test_activate_unknown_version_is_refused`, `test_stale_page_cannot_overwrite_a_colleagues_change`); conform (#451) |
| No cache; store failure degrades to code text | Decision 5, ADR066-G2 | `DbPromptProvider` | `test_prompt_store.py` (`test_provider_serves_code_default_when_nothing_is_active`, `test_provider_serves_the_active_version_on_the_next_call`, `test_provider_degrades_when_the_store_fails`); conform (#451) |
| Admin page: permission, audit, code default beside active, revert | ADR066-G4, ADR066-G5 | `/admin/prompts` on quickstart | Browser e2e during #451 (not an automated test): two saves left "Serving code default"; activate → v2; activate v1 → rollback; empty save refused with a `PROMPT_CONTENT_INVALID` FAILURE audit row; revert cleared the pointer; conform |
| Ledger links a call to a stored version | ADR066-G3 | Real answer agent, in-process | In-process e2e during #451: with v2 active, instructions began with the v2 persona and ended with `RAG_INSTRUCTIONS_TAIL`, and the ledger row read `docs_answer / 2 / self / docs_answer@2`; after revert, the code persona and `inline`; conform |

**Limits of the evidence.** As recorded for #447: the non-inline path was
exercised only with a fake provider. Since #451 the store path is covered by the
unit and integration tests above; the admin page and the ledger linkage with the
real answer agent were verified by hand (browser and in-process e2e), not by an
automated test.

## Implementation note (#451, 2026-11-16)

#449 shipped the contract; #451 implemented Decision 5. The design choices that
the Decision left open:

- **Registry.** `register_prompt(name, default)` in
  `src/_core/infrastructure/prompt/registry.py`; the answer agent registers
  `docs_answer` and the classifier `classification` next to their code persona.
  Only registered names are listed or editable. `MAX_PROMPT_LENGTH = 8000`.
- **Tables.** `prompt_version` (append-only, unique `(name, version)`, which is
  also the guard against two concurrent saves taking the same number) and
  `prompt_active` (one pointer row per name; no row = code default). Additive
  migration `0011_prompt_store`; models are registered for Alembic and for the
  quickstart `create_all`.
- **Service.** `PromptStoreService` holds every write rule, so a caller other than
  the admin page cannot skip them. Activating requires the version to exist; activate
  and revert are refused with `PROMPT_ACTIVE_CHANGED` (409) when the active version
  moved since the operator loaded the page.
- **Provider.** `DbPromptProvider` performs one read per call. An active version is
  served as `source="self"`, `version="<n>"`, `external_ref="name@<n>"`; any error
  serves the code text as `inline` and logs `prompt_store_unavailable` with the
  exception type only (a driver message can carry the DSN).
- **Admin.** `/admin/prompts` behind the fixed permission key `prompts`. Persona
  text is rendered as escaped text (`ui.label`), never as HTML or Markdown.
  Operator guide: [prompt management runbook](../operations/prompt-management.md).

**Accepted limits of the implementation.**

- A compromised account holding `prompts` can change agent behaviour (see the
  trust-boundary note above).
- The optimistic check is check-then-write, not a transaction: two activations
  within the same few milliseconds can both pass it. With a version already
  active, both succeed and are audited and the last wins; with nothing active,
  the second loses the primary-key race on the pointer row and is audited as a
  failure.
- Existing admins do not receive `prompts` automatically. Only the first admin
  created by the setup wizard gets every key; everyone else must be granted it on
  `/admin/accounts`.

**Revisit when** a consumer needs prompt variables, a per-tenant prompt model exists,
traffic must be split between versions, or a third production prompt makes the
deferred items (diff, labels) worth their cost.
