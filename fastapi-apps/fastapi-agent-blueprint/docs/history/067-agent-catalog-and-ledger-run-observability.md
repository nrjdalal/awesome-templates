# 067. Agent Catalog and Ledger-Based Run Observability — See Workflows, Do Not Build Them

- Status: Proposed
- Date: 2026-11-16 (recording date; becomes the decision date when accepted)
- Record type: contemporaneous
- Decision evidence: owner discussion on 2026-11-16 and the Execution Packet on [#453](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/453) (tickets #454–#457). Not yet approved for execution.
- Related issue: #453 (epic); #454 ledger linkage, #455 registry + reference workflow, #456 `/admin/agents`, #457 call tree
- Amends / supersedes: none. Builds on [ADR 066](066-prompt-provider-contract.md) (per-agent prompt registry) and [ADR 046](046-otel-core-langfuse-recipe-prompt-domain-defer.md) §1 (OTEL core stays independent).
- Related: [ADR 042](042-optional-infrastructure-di-pattern.md) (stub fallbacks), [ADR 050](050-midtask-scope-expansion-gate.md) (non-goals), [ADR 037](037-pydanticai-agent-integration.md) (PydanticAI)

## Summary

The owner wants to see which agents exist, how a workflow is meant to run, and how a
request actually ran across agents and sub-agents. We propose to show all three in the
existing admin, built from code-defined `pydantic-graph` workflows and the existing
usage ledger. No new infrastructure is added, and workflows are not authored visually.

## Background

- **Trigger.** After #451, operators can version each agent's prompt. The owner then
  asked for the surrounding picture:
  - every agent has its own prompts;
  - agents call sub-agents;
  - workflows should be drawable;
  - the owner wants to understand how an agent drives a workflow.
- **What exists today.** Two independent agents (RAG answer, classifier), no
  sub-agents and no workflows. The ledger groups a request's calls by `request_id`
  and carries `trace_id` / `span_id`, but records no parent–child relation.
- **Constraint carried from ADR 066.** Langfuse was rejected for operational burden.
  The owner's direction is to stay self-hosted on infrastructure the project already
  runs.
- **Decision type:** upfront design.

## Problem

1. Per-agent prompts already work: each agent registers its own name via
   `register_prompt` (ADR 066). Nothing, however, lists the *agents* — their model,
   their prompts, which sub-agents they call.
2. "Draw workflows" covers two very different things:
   - **C1 — see:** render a workflow defined in code.
   - **C2 — build:** compose a workflow in a UI and execute it.
   C1 is a viewer; C2 is a workflow-engine product.
3. Without a parent link in the ledger, a request that fans out to sub-agents is a
   flat list of rows; the execution path cannot be reconstructed.
4. Viewers built before any multi-agent code exists would render empty screens.

## Alternatives Considered

### A. Ledger-based call trees + code-defined graph diagrams in the admin (proposed)
Add `parent_call_id` to the ledger, propagated automatically through a ContextVar in
`track_agent_usage`. Define workflows with `pydantic-graph`, which is already
installed with `pydantic-ai`, and render them with `graph.render()` → Mermaid →
NiceGUI `ui.mermaid`. Add an agent registry next to the prompt registry. Build a
reference multi-agent workflow first, so the viewers have content.

### B. Export OTEL spans to a trace backend (Jaeger, Phoenix, Langfuse)
PydanticAI already emits GenAI spans (ADR 046 §1). Rejected as the primary path:
- it adds a service to run, which is the burden ADR 066 rejected;
- it lives outside the admin the operators use;
- it shows spans, not the agent/sub-agent/prompt-version view asked for.

OTEL export remains available for teams that run a backend.

### C. Visual workflow builder (C2)
Drag-and-drop composition that executes: an execution engine, persisted state,
error handling and versioning of flows. This is the Langflow/Dify product class,
and it matches the ADR 050 non-goal "an admin-panel product". Rejected; revisiting
requires its own ADR and demonstrated demand.

### D. Build the viewers first, the reference workflow later
Rejected: with two independent agents the catalog is two rows, the diagram has no
edges and the call tree has depth one. The order matters for whether the work can be
verified.

## Decision (proposed)

1. **Scope is C1 (see), not C2 (build).** Workflows are Python code. The admin shows
   them and their executions; it never edits or runs arbitrary flows.
2. **Ledger parent linkage.** Nullable `parent_call_id` on `ai_usage_log`, set
   automatically for any agent call started inside another tracked call. Migration
   0012 is additive. Top-level calls stay `NULL`. Sibling calls under
   `asyncio.gather` share a parent and never parent each other.
3. **Agent registry.** `register_agent(AgentSpec(name, description, prompt_names,
   sub_agents, graph=None))` in `_core`, next to `register_prompt`. The model shown
   is read from settings at render time, never from a code constant.
4. **Reference multi-agent workflow first.** A thin consumer domain (proposed name
   `research_assistant`) runs a `pydantic-graph` flow: classify → retrieve (the
   existing docs RAG) → summarise → answer.
   - Each sub-agent has its own registered prompt and composes instructions with the
     code-owned tail last (ADR 066).
   - Stub models apply with no LLM configured (ADR 042), so no LLM **credentials** are
     needed. The `pydantic-ai` **package** still is: `make quickstart` installs only
     the `admin` extra, and without `pydantic-ai` the stub factory returns `None`
     (`stub_llm_model.py`; ADR 042) and `pydantic-graph` is absent. The demo path is
     therefore `uv sync --extra admin --extra pydantic-ai` with no keys, unless the
     owner chooses to widen quickstart (see defaults below).
5. **Admin surfaces.**
   - `/admin/agents`: catalog, workflow diagram and recent runs. Behind a new
     read-only permission key `agents`. A "Run sample" action is
     permission-checked and audited.
   - Per-request call tree at `/admin/ai_usage/request/{request_id}`, behind the
     existing `ai_usage` permission.
6. **No new infrastructure and no new dependency.**

### Defaults awaiting owner confirmation

These may change before acceptance:
- the reference flow — the owner's real flow should replace it if one exists;
- the domain name `research_assistant`;
- the permission split: `agents` for the catalog, `ai_usage` for the call tree;
- how the demo is installed: document `--extra pydantic-ai` for the demo (proposed),
  or add `pydantic-ai` to `make quickstart`. The second makes the zero-config path
  heavier for every adopter. Either way, the catalog and `/admin/agents` must still
  render without `pydantic-ai`, listing agents with "not runnable here".

## Rationale

- **The question is "how did it run".** Answering it needs the actual execution
  path, which the ledger already half-records. One column and context propagation
  complete it without a second telemetry pipeline.
- **Code-defined workflows keep review in the loop.** A workflow changes agent
  behaviour as much as a prompt does. Under C1 flows go through code review and CI;
  only personas are runtime-editable (ADR 066), with the boundary tail fixed.
- **Diagrams are generated, not drawn.** `graph.render()` is derived from the
  executable graph, so the picture cannot drift from the code — a hand-maintained
  diagram would.
- **Reference first** follows the project direction (a reusable `_core` pattern plus
  a thin consumer, as RAG did) and makes every ticket verifiable end to end.

### Self-check
- [x] Does this decision address the root cause, not just the symptom? — The missing
  parent link and the missing catalog are the causes; viewers alone would not fix them.
- [x] Is this the right approach for the current project scale? — It reuses the
  ledger, the admin and an installed library; it adds no service.
- [x] Will a reader understand "why" 6 months from now without extra context? — The
  C1/C2 split and the rejected trace backend are recorded here, not only in chat.
- [x] Am I recording the decision process, or justifying a conclusion? — Alternative
  D (viewers first) was the initial instinct and is recorded as rejected, with the
  reason.

## Consequences

- **Scope.** C2 stays out. Any request for UI-authored, executable workflows is a new
  ADR, not a ticket under #453.
- **Trade-offs.**
  - The ledger records agent calls, not every tool call or span. The call tree shows
    agent-level structure.
  - Span-level detail inside one LLM call still needs OTEL and a backend.
- **Evidence limits.** Nothing here is implemented yet. Each ticket must attach its
  own verification: tests, a migration safety scan, an e2e run whose call tree has at
  least three nodes, and admin screenshots light/dark × 1440/390.
- **Status change.** Becomes Accepted when the owner approves #453 for execution
  (`/execute-plan`), with any changed defaults recorded in a dated note here.
- **Revisit when:**
  - operators must change workflow structure without a deploy (C2 demand);
  - tool-level tracing in the admin is needed;
  - the ledger volume makes per-request trees expensive to assemble.
