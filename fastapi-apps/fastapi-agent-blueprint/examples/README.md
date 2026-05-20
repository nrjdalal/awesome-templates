# Examples

Small, self-contained example applications built with this blueprint.
Each example is a **contributor-built** reference showing one pattern —
plain CRUD, background workers, cross-domain dependencies, LLM agents —
without the extra tooling that ships with the production reference
domains in [`src/`](../src/).

> 👀 New here?
> - Evaluate first with [`make quickstart`](../docs/quickstart.md).
> - Build your own first domain with the [10-minute tutorial](../docs/tutorial/first-domain.md).
> - Then come back to pattern-match against these examples.

## How to run an example

Each example is laid out **exactly like a production domain** under
`src/{name}/`. The blueprint's auto-discovery
([`src/_core/infrastructure/discovery.py`](../src/_core/infrastructure/discovery.py))
only scans `src/`, so an example is "installed" by copying it in:

```bash
# Pick an example you want to try (e.g., todo).
cp -r examples/todo src/todo

# Boot the quickstart server — auto-discovery picks it up on startup.
rm -f ./quickstart.db         # so the new table is created at boot
make quickstart
```

Open <http://127.0.0.1:8001/docs> and pick Swagger from the selector;
the new tag is now listed alongside `User`. Remove the example when you
are done:

```bash
rm -rf src/todo
rm -f ./quickstart.db
```

> **Why copy instead of symlink?** Examples are meant to be *read* as
> much as *run*. Copying is explicit, works on every OS, and matches
> what a contributor would do when turning an example into a real
> domain inside their own fork.

## Contributing a new example

Each `good first issue` under the `examples/` area maps one-to-one to a
planned folder in this directory. See the
[`good first issue` list](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues?q=is%3Aopen+label%3A%22good+first+issue%22)
for what is up for grabs.

An example PR should include:

1. **Code** under `examples/{name}/` mirroring the `src/{domain}/`
   layout (Domain, Infrastructure, Interface) exactly — see the
   [tutorial](../docs/tutorial/first-domain.md#step-3--describe-an-order)
   for the canonical structure.
   - **Path params** should use `{<domain>_id}` (e.g.
     `/user/{user_id}`, `/todo/{todo_id}`) to avoid shadowing the
     Python builtin `id`. The handler parameter name (`user_id: int`,
     `todo_id: int`) must match the path placeholder.
   - **Handler function names** follow `src/{domain}/` only when the
     domain has multiple lookup variants needing disambiguation (e.g.
     `get_user_by_user_id` vs `get_user_by_ids`). Single-lookup
     examples may keep short names (`get_todo`, `update_todo`,
     `delete_todo`).
2. **A README** in `examples/{name}/README.md` covering:
   - What pattern the example teaches (2–3 sentences).
   - `curl` requests a reader can paste to exercise the endpoints.
   - Relevant production-domain reference (e.g. "compare with
     [`src/user/`](../src/user/) for password hashing").
3. **A unit test** under `tests/unit/{name}/` (matching the production
   test layout so CI auto-discovery runs it without extra wiring; see
   the [tutorial unit test](../docs/tutorial/first-domain.md#step-5--add-a-unit-test)
   for a protocol-based mock pattern). Examples are **not** required
   to provide the full production test baseline (factories /
   integration / e2e under `tests/{layer}/{name}/`) — a single unit
   test is sufficient. This is the **examples profile**; see
   [`docs/ai/shared/skills/review-architecture.md`](../docs/ai/shared/skills/review-architecture.md#examples-profile-vs-production)
   for the audit-side counterpart.
4. **No new dependencies** unless explicitly called for by the issue.
   If your example needs a library not already in `pyproject.toml`,
   open a discussion on the issue first.

Architectural rules in [`AGENTS.md`](../AGENTS.md) apply to examples
just like production domains — no `Domain → Infrastructure` imports,
no Model objects leaving the Repository, no Mapper classes.

## Available examples

Populated incrementally as contributors land the good-first-issues:

| Example | Pattern it teaches | Status |
|---|---|---|
| `todo/` | Minimal CRUD domain (zero infra) | 🟡 tracked issue |
| `url-shortener/` | CRUD + Taskiq worker cleanup task | 🟡 tracked issue |
| `blog/` | Two domains + Protocol-based cross-domain DIP | 🟡 tracked issue |
| `webhook-receiver/` | Worker task driven by a broker message | 🟡 tracked issue |
| `simple-chatbot/` | Minimal PydanticAI Agent — no RAG | 🟡 tracked issue |

Finished examples move from 🟡 to ✅ with a link to the PR that landed
them. If an example you want is not on the list, open a
[feature request](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/new?template=feature_request.yml)
describing the pattern it would teach.

## What belongs here (and what does not)

**Good fit for `examples/`**

- Demonstrates a single blueprint pattern end-to-end in under a day of work.
- Standalone: can be copied into `src/` of a fresh clone and run with
  `make quickstart`, no external infrastructure.
- Small enough for a reviewer to read the full diff in one sitting.

**Belongs in `src/` instead**

- Showcases the full stack (e.g. the planned RAG domain in
  [#80](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/80)
  lives in `src/` because it exercises embeddings + vector store + LLM
  together and needs to be covered by the main test suite).

**Belongs in a separate repo**

- Consumer applications built *with* the blueprint (e.g. a SaaS product).
  Those are the payoff, not examples. Link them from your own README
  and we will happily feature them in a "built with" section.
