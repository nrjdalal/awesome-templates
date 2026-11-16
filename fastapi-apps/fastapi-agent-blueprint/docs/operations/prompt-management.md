# Prompt Management Runbook — Editing Agent Personas Without a Deploy

This document covers the self-hosted prompt store
([#451](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/451)): how an
operator changes an agent persona from the admin dashboard, rolls it back, and
confirms which text served a call. The design and its limits are recorded in
[ADR 066](../history/066-prompt-provider-contract.md).

The store is **not optional infrastructure**. It lives in the mandatory RDB, has
no environment variable, and with nothing active it serves exactly the code text.

> Holding the `prompts` permission is holding the ability to change agent
> behaviour in production. Grant it as narrowly as `accounts`.

## What can be edited

Only the **persona** of a prompt that code registered — today `docs_answer` (the
RAG answer agent) and `classification` (the classifier). The prompt-injection
rules that agents append after the persona are fixed in code and cannot be edited
here; whatever the persona says, those rules run last. Text must be non-empty and
at most 8000 characters.

## Before first use

1. **Run the migration.** `uv run alembic upgrade head` applies
   `0011_prompt_store` (two new tables, additive). Quickstart creates the tables
   on boot. See [rdb-migrations.md](rdb-migrations.md).
2. **Grant the permission.** On `/admin/accounts`, edit the admin's permissions
   and tick `prompts`. Existing admins do **not** receive it automatically; only
   the first admin created by the setup wizard gets every key. The **Prompts**
   item appears under **Operations** in the navigation once granted.

## Reading a prompt card

`/admin/prompts` shows one card per registered prompt.

| Element | Meaning |
|---|---|
| Badge `Serving code default` | No version is active. Agents use the code text. |
| Badge `Active: vN` | Agents use stored version N. |
| **Code default** panel | The text that ships in code. Served when nothing is active or the store fails. |
| **Active version** panel | The text agents serve now, with who activated it. |
| **Versions** list | Every saved text, newest first. Versions are never edited in place. |

A developer's change to a persona in code takes effect **only while no version is
active**. If a code change seems to have no effect, check the badge: an active
version overrides it until someone reverts to the code default.

## Tasks

**Edit and put live.** Edit the **New version** text, click **Save as new
version**, then click **Activate** on that version in the list. Saving alone
changes nothing agents serve — this lets you stage text and activate it later.

**Roll back.** Click **Activate** on an older version. Rollback only moves the
active pointer; no text is rewritten.

**Revert to code default.** Click **Revert to code default** (shown only while a
version is active). The pointer is cleared; the saved versions stay.

**Propagation.** There is no cache. Every process serves the new text on its next
agent call after an activation, rollback or revert.

**"The active version changed since this page was loaded."** A colleague activated
or reverted after you opened the page. Reload, review the new state, and retry.

## Audit trail

Every write, successful or refused, is recorded in the admin audit log
(`/admin/audit-log`, requires `audit_log`):

| Action | `record_id` |
|---|---|
| `PROMPT_VERSION_SAVE` | `name@version` (the name alone when refused) |
| `PROMPT_ACTIVATE` | `name@version` (the name alone when refused) |
| `PROMPT_REVERT` | `name` |

A refused write carries a stable `failure_reason`, for example
`PROMPT_CONTENT_INVALID` (empty or too long), `PROMPT_ACTIVE_CHANGED`, or
`PERMISSION_DENIED`. The permission is re-checked on every write, so revoking it
takes effect even for a page that is already open, and the refused attempt is
still audited.

## Verifying which prompt served a call

Each real agent call writes a row to the AI usage ledger:

| Field | Active stored version | Code text |
|---|---|---|
| `prompt_name` | `docs_answer` | `docs_answer` |
| `prompt_version` | `2` | empty |
| `prompt_source` | `self` | `inline` |
| `external_prompt_ref` | `docs_answer@2` | empty |

The `/admin/ai_usage` grid shows prompt name, version and source.
`external_prompt_ref` is returned by `GET /v1/usage` and `GET /v1/usage/{id}`
(as `externalPromptRef`). Because versions are append-only, `name@version` always
identifies the exact text.

## Failure behaviour

If the store cannot be read (database error, missing table), the agent call still
succeeds on the **code text**, the ledger records `prompt_source=inline`, and the
server logs a `prompt_store_unavailable` warning with `prompt_name` and the
exception type only. If ledger rows show `inline` while a version is active,
search the logs for that event.

## Limits

- A compromised account holding `prompts` can change agent behaviour. The fixed
  boundary rules, runtime guardrails and audit log limit and record what an edit
  can do; they do not prevent it.
- The concurrent-edit check is check-then-write: two activations within the same
  few milliseconds can both pass it. When a version is already active, both
  writes succeed, both are audited, and the last one wins. When **nothing** is
  active yet, the two writes race to insert the same pointer row: the first
  wins and the second fails on the primary key, shows an error, and is audited
  as a failure.
- A pointer to a version that does not exist (hand-edited or partially restored
  data) is not read as "nothing active": agents serve the code text and log
  `prompt_store_unavailable` with `exc_type=DanglingActivePointer`.
- No diff view, test run before activation, labels or prompt variables
  ([ADR 066](../history/066-prompt-provider-contract.md) Decision 5 defers them).
