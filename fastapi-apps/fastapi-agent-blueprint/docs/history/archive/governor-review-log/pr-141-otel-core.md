# pr-141: OTEL core — `[otel]` extra + settings + bootstrap wiring + recipe doc

## Summary

ADR 046 (merged in PR #135, 2026-04-28) established OTEL as the standard
backend-agnostic trace output for PydanticAI Agents but deferred the bootstrap
wiring to Issue #136. PR #141 (Issue #136) completes ADR 046 Pillar 1:

- New `[otel]` optional extra (`opentelemetry-api/sdk/exporter-otlp-proto-grpc >=1.40.0`)
- `OTEL_ENABLED` + `OTEL_EXPORTER_OTLP_ENDPOINT` Settings fields + partial-config validator
- `_maybe_configure_otel()` helper in both server and worker bootstraps
- `src/_core/infrastructure/observability/otel_setup.py` — `configure_otel()` + `_instrument_pydantic_ai_agents()`
- `docs/operations/observability-otel.md` — Jaeger / Tempo / Phoenix recipe + HTTP exporter swap

Tier A files touched: `.claude/rules/project-status.md`,
`docs/ai/shared/ai-infrastructure-overview.md`.

GitHub PR: https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/141

## Review Rounds

> Each round lists every surfaced point as `R{n}.{m}` with severity, plus
> a one-line *Disposition* showing how that point was resolved (plan version or
> commit reference). This is the traceability requirement per prior round ICs.

### Round 1 — Codex cross-review (plan review, gpt-5.5)

- Reviewer: `codex exec --skip-git-repo-check --sandbox read-only --model gpt-5.5`
- Trigger: Tier A change set — plan v1 submitted for adversarial review before implementation

| Point | Severity | Surface | Disposition |
|-------|----------|---------|-------------|
| R1.1 | BLOCKER | `settings.app_name` used in `configure_otel()` — field does not exist in `Settings` | Plan v2: replaced with explicit `service_name: str` parameter passed from each bootstrap call |
| R1.2 | MINOR | Log event level `info` for `otel_extra_not_installed` inconsistent — user opted in via `OTEL_ENABLED=true`, silent skip warrants `warning` | Plan v2: changed to `warning`; event name `otel_extra_not_installed` matches ADR L100 sketch exactly |
| R1.3 | MINOR | `except ImportError` in `_maybe_configure_otel` too broad — internal bugs in `otel_setup.py` silently swallowed | Plan v2: switched to `ModuleNotFoundError` + `exc.name.startswith("opentelemetry")` filter |
| R1.4 | MINOR | No idempotency guard — second `configure_otel()` call (e.g. test isolation, Logfire co-existence) installs a second `BatchSpanProcessor` and leaks threads | Plan v2: added `isinstance(current, TracerProvider)` short-circuit; tests reset `trace._TRACER_PROVIDER` |
| R1.5 | MINOR | `_has_otel` in `test_minimal_install.py` checks namespace package only — `opentelemetry` namespace exists even without SDK/exporter | Plan v2: checks both `opentelemetry.sdk.trace` and `opentelemetry.exporter.otlp.proto.grpc.trace_exporter` |
| R1.6 | MINOR | `clean_optional_env` fixture in `test_optional_infra.py` does not clear OTEL fields — test isolation gap | Plan v2: extended fixture with `otel_enabled=False` + `otel_exporter_otlp_endpoint=None` |
| R1.7 | MINOR | `uv.lock` update not mentioned in plan — lockfile drift after `pyproject.toml` change | Plan v2: added explicit `uv lock` step |
| R1.8 | MINOR | `_env/local.env.example` and `_env/quickstart.env.example` not updated with OTEL vars | Plan v2: added commented OTEL block mirroring LLM block style |
| R1.9 | MINOR | `CHANGELOG.md` Unreleased section not updated | Plan v2: added full Unreleased `### Added` entry for #136 |
| R1.10 | MINOR | Governor-changing files (project-status.md, ai-infrastructure-overview.md) touched without a governor review log entry | Plan v2: added `docs/ai/shared/governor-review-log/pr-136-otel-core.md` + PR template fill |
| R1.11 | INFO | `Agent.instrument_all()` availability floor not verified — confirmed present from pydantic-ai-slim 1.0.5+; lockfile at 1.83.0; double-call safe in 1.83+ | Closed — no floor bump needed |

- Final Verdict: plan v1 requires 10 fixes before implementation
- Plan version after round: v2

### Round 2 — Codex re-review after Round 1 fixes (gpt-5.5)

- Reviewer: `codex exec --skip-git-repo-check --sandbox read-only --model gpt-5.5`
- Trigger: 10 MINOR/BLOCKER items in Round 1 warranted a second adversarial pass on plan v2

| Point | Severity | Surface | Disposition |
|-------|----------|---------|-------------|
| R2.1 | BLOCKER | Idempotency guard direction wrong: `isinstance(current, TracerProvider)` only catches SDK type — Logfire and any third-party non-proxy provider slip through | Plan v3: inverted to `not isinstance(current, ProxyTracerProvider)`; covers all non-proxy providers |
| R2.2 | MINOR | Test reset code mis-modeled SDK 1.40 internals: `trace._TRACER_PROVIDER = ProxyTracerProvider()` is wrong; SDK default is `None`, not a new `ProxyTracerProvider()` | Plan v3: reset to `trace._TRACER_PROVIDER = None` + must also reset `_TRACER_PROVIDER_SET_ONCE._done = False`; SDK provider gets `shutdown()` first |
| R2.3 | MINOR | Fallback note only mentioned `_TRACER_PROVIDER` — future readers need both attribute resets documented | Plan v3: fallback explicitly requires both `_TRACER_PROVIDER = None` AND `_TRACER_PROVIDER_SET_ONCE._done = False` |
| R2.4 | MINOR | `OTEL_SERVICE_NAME` env override claim was wrong: `Resource.create({"service.name": name})` overrides env var in SDK 1.40+, not the other way around | Plan v3: added explicit env-var check in `configure_otel()` — only set `service.name` attribute when env is silent; env wins by design |
| R2.5 | MINOR | `test_otel_modules_not_imported_at_runtime` false-positive: checking same-process `sys.modules` is polluted from earlier test imports — idempotency of module loading makes the check meaningless | Plan v3: switched to `subprocess.run` with a clean Python interpreter; skip gate added for when otel is locally installed (CI minimal-install job is authoritative) |
| R2.6 | INFO | `instrument_all()` floor question from R1.11 — closed; confirmed present from 1.0.5+, double-call safe in 1.83+ | No change |

- Final Verdict: plan v2 requires 4 fixes; plan v3 is implementation-ready
- Plan version after round: v3

## R-points Closure Table

| Source | R-point | Closure | Note |
|---|---|---|---|
| Round 1 | R1.1: nonexistent `settings.app_name` | Fixed | Plan v2 uses explicit `service_name` parameter. |
| Round 1 | R1.2: OTEL extra missing event should be warning | Fixed | Plan v2 changed the event level to warning. |
| Round 1 | R1.3: broad ImportError swallow | Fixed | Plan v2 narrowed handling to opentelemetry ModuleNotFoundError. |
| Round 1 | R1.4: missing idempotency guard | Fixed | Plan v2 added an idempotency guard and test reset strategy. |
| Round 1 | R1.5: namespace-only OTEL install detection | Fixed | Plan v2 checks SDK and exporter modules. |
| Round 1 | R1.6: optional infra fixture missing OTEL fields | Fixed | Fixture clears OTEL settings. |
| Round 1 | R1.7: lockfile update not planned | Fixed | `uv lock` step added. |
| Round 1 | R1.8: env examples missing OTEL vars | Fixed | Commented OTEL blocks added to env examples. |
| Round 1 | R1.9: CHANGELOG missing update | Fixed | Unreleased entry added. |
| Round 1 | R1.10: missing governor review-log entry | Fixed | Governor review-log entry added. |
| Round 1 | R1.11: instrument_all availability floor | Rejected | Existing dependency floor was sufficient; no bump needed. |
| Round 2 | R2.1: idempotency guard direction wrong | Fixed | Plan v3 guards on non-proxy provider. |
| Round 2 | R2.2: tracer provider reset internals mis-modeled | Fixed | Reset plan uses `None` and resets the once flag. |
| Round 2 | R2.3: fallback note incomplete | Fixed | Fallback explicitly documents both reset attributes. |
| Round 2 | R2.4: OTEL_SERVICE_NAME precedence claim wrong | Fixed | Plan v3 makes env service name win by design. |
| Round 2 | R2.5: same-process module-loading false positive | Fixed | Test moved to a clean subprocess. |
| Round 2 | R2.6: instrument_all floor re-check | Rejected | Confirmed safe with current dependency range. |

## Inherited Constraints

- Carries forward PR #135's IC stack (no new ICs introduced by this PR)
- Tier 1 Language Policy: this entry and all modified governance files are English-only
- No `Co-Authored-By: Claude` or "Generated with Claude Code" in any artefact
- `otel_enabled=False` is the default — `make quickstart` must boot unchanged
- `OTEL_ENABLED=true` without an endpoint must be rejected by `Settings._validate_environment_safety` in all ENV values (unconditional, not strict-env-gated — mirrors SQS/RabbitMQ patterns)

## Self-Application Proof

> Per `docs/ai/shared/governor-review-log/README.md` §Entry shape, this section
> requires canonical output of `/review-architecture` and `/sync-guidelines`
> on the PR's own changed surface, plus grep-based mechanical checks.

### `/review-architecture` (run on this PR's diff)

```
Scope: src/_core/infrastructure/observability/otel_setup.py,
       src/_apps/server/bootstrap.py, src/_apps/worker/bootstrap.py,
       src/_core/config.py (OTEL fields + validator),
       docs/operations/observability-otel.md,
       .claude/rules/project-status.md,
       docs/ai/shared/ai-infrastructure-overview.md,
       docs/ai/shared/governor-review-log/pr-136-otel-core.md
Sources Loaded: AGENTS.md §Language Policy, docs/ai/shared/architecture-review-checklist.md,
                governor-paths.md §1D drift-checklist
Findings: none — bootstrap-level wiring mirrors _mount_admin_if_available pattern;
          no CoreContainer Selector (process-global, not per-domain);
          no Domain → Infrastructure import violations;
          Language Policy: 0 violations per tools/check_language_policy.py
Drift Candidates: none
Next Actions: none
Completion State: Pass
Sync Required: false
```

### `/sync-guidelines` (closure run after /review-architecture)

```
Mode: review follow-up
Input Drift Candidates: none
project-dna: Unchanged (no new architectural pattern — OTEL wiring is
             bootstrap-level, same pattern as admin extra)
AUTO-FIX: none
REVIEW: none
Remaining: none
Next Actions: none — gate closed
```

### Mechanical checks (run before merge)

```bash
# OTEL fields present in config
grep -F "otel_enabled" src/_core/config.py
grep -F "otel_exporter_otlp_endpoint" src/_core/config.py

# Partial-config validator entry present
grep -F "OTEL_ENABLED=true requires" src/_core/config.py

# Bootstrap wiring present in both entrypoints
grep -F "_maybe_configure_otel" src/_apps/server/bootstrap.py
grep -F "_maybe_configure_otel" src/_apps/worker/bootstrap.py

# otel_setup module exists
test -f src/_core/infrastructure/observability/otel_setup.py

# Recipe doc exists
test -f docs/operations/observability-otel.md

# project-status.md row present
grep -F "#136" .claude/rules/project-status.md

# CHANGELOG updated
grep -F "#136" CHANGELOG.md

# Env example files updated
grep -F "OTEL_ENABLED" _env/local.env.example
grep -F "OTEL_ENABLED" _env/quickstart.env.example
```
