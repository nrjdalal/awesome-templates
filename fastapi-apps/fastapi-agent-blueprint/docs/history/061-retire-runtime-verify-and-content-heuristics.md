# 061. Retire Runtime Verify and Content Heuristics

- Status: Accepted
- Date: 2026-11-06
- Related issues: #414 (B2, B8, B9), #334, #425
- Amends: [ADR 045](045-hybrid-harness-target-architecture.md), [ADR 052](052-native-execution-ledger-and-execute-plan.md)

## Context

Per-edit verify reminders and command-name logs consume processes and context
without proving a verification command succeeded. A log of `rg pytest docs/`
was even accepted as a verification run by the old lexical classifier. This
is a known false positive, not evidence that verification itself is optional.
Runtime content heuristics also duplicate commit-time architecture/credential
checks while covering only a small lexical corpus. The audit did not measure
an error-rate benefit, nor prove these heuristics never helped.

## Alternatives

1. Keep per-edit reminders and three command-log lifecycles. Rejected because
   command names are not successful verification evidence.
2. Remove the governor or its safety/import dependencies wholesale. Rejected:
   it disables active token, stage, shell-safety and completion behavior.
3. Retire only the named heuristics; retain deterministic gates, actual command
   outcomes and active lifecycle contracts. Selected.

## Decision

Retire verify-first, verify-log writers/readers and stale-log garbage collection
across Claude, Codex and Antigravity. Remove their configured processes and
shared public exports together. C4 now checks actual exception-token consumer
calls in all three adapters; state statistics count active token markers.
Existing untracked command-log files are inert local cache and are not deleted
by this migration. For one-off cleanup, inspect the `verify-log-*.json` files
under each harness state directory and remove only selected obsolete log files
when their diagnostic history is no longer needed; never clear active token or
stage markers as part of that cleanup. Tracked files under state directories remain prohibited.

Keep the existing actual-exit-code ledger recorder in Codex and Antigravity,
including Gemini cancellation/abort handling. A shared simple-command classifier
replaces the log writer's classifier side effect. Searches, echoed names and
compound commands with ambiguous exit outcomes are not verification evidence.
The accepted simple-command scope deliberately includes `pyright`,
`pre-commit run` and `make check-core` in addition to the original test/demo/
migration names: they are explicit deterministic verification commands, not a
substring match anywhere in shell text. Help/version and pytest collection-only
forms do not count. Environment-assignment prefixes, uv runner options, shell
composites and pipelines remain conservatively unrecorded, even after a real
pass, because parsing their aggregate exit result would invent a shell-execution
contract. They may leave a pending reminder; record an explicit verification
result or run a supported simple invocation instead. No new per-command log
file is written. Claude still does not infer command
success from a tool payload that supplies no supported result contract.

Retire runtime SQL-string, hardcoded-secret and Domain-to-Infrastructure import
heuristics in Claude and Antigravity; Codex already used shell safety only. The existing gitleaks and architecture import gates remain blocking;
Ruff selects the `S` family, including S105/S106/S107 (hardcoded password
strings/arguments/defaults) and S608 (hardcoded SQL expressions) for production
source; tests ignore `S`. Those lexical/static rules do not establish safe SQL
execution or discover every secret flow. Tests and security review retain their
own scopes. They are **not** claimed
to be equivalent coverage of SQL injection or every exposed secret. This is an
intentional removal of pre-edit heuristic rejection, not a security proof.

Move the existing sensitive-log lexical pattern to the blocking
`sensitive-logging` pygrep hook for `src/` and `examples/` Python. Test corpora
are excluded because their source intentionally contains leak examples. The
pattern flags same-line logger/logging/print references to credential names;
it is not data-flow analysis. Multiline calls, logger aliases such as `log`,
and `structlog.get_logger().info` are outside its pattern. Legitimate event
names such as `invalid_token` or `token_refreshed` also match: this intentional
false positive is pinned in a real pre-commit fixture. The hook scans whole
production files, not only edited text. After manually checking that no secret
is exposed, `SKIP=sensitive-logging` is the deliberate per-run escape for a
false positive; record the rationale and keep all other checks running. This
escape is not a passing logging-check result or an inline suppression. Multiline
or indirect leaks still require review. Run it on all production files before enabling it. Keep
`governor/code_safety.py` as an importable no-op compatibility surface: removing
it while Antigravity imports it beside shell safety would fail open and disable
the unrelated destructive-command guard.

Tokens, marker consumption, safety parsing, destructive-command checks,
AGENT_LOCALE for active messages, ADR 050/054 stage gates and independent-review
provenance remain. Retire only the unused verify-first locale key. Session-id
resolution needed by stage-marker dedup lives in the existing per-tool helpers.

Ledger summaries describe previous work from a local cache, never a proven
resumed session. Suppress completed cache with no changed Python, pending/failed
verification, blockers or pending review. Preserve idle prompt-and-verification
continuity promised by ADR 052; a caller that never invokes planning still sees
its recorded prompt and outcome. Local cache is not an authoritative ticket or
CI status.

## Consequences

- **ADR061-G1**: Retiring a hook requires removing its configured invocation,
  readers/writers, health-check expectations and live documentation together;
  preserve unrelated token, stage, shell-safety and locale behavior.
- **ADR061-G2**: Verification outcomes use actual supported exit results and a
  command classifier independent of command-log state. A search, cancellation or
  unknown outcome must not become a passing verification record.
- **ADR061-G3**: Runtime heuristic removal must disclose the changed guarantee.
  Keep the sensitive-logging production gate blocking and the Antigravity
  compatibility import intact until its consumer is deliberately migrated.
- **ADR061-G4**: Completed cache suppression must preserve unresolved verification
  and review state; idle prompt-and-verification continuity remains supported.

## Verification and Rollback

Exercise retired-surface regression probes, genuine command outcomes versus
search/fallback/cancellation, all three marker/stage adapters, active locale
messages, completed/idle ledger cases and sensitive-log positive/negative
fixtures. Run the real state doctor, pyright, language/link guards and all
pre-commit hooks. Root's integrated independent review covers the final diff.

Rollback is a coherent revert of this change, including configured hooks,
shared imports, tests and the sensitive-logging commit gate; do not restore a
writer without its consumers or a consumer without its shared module.
