"""Stop hook (Codex side) — sync-reminder + Phase 3 verify-first + Phase 4
completion-gate, with AGENT_LOCALE rendering (issue #133).

Single Stop event output (IC-2): all advisories are collected into a list
of segments and emitted as one ``{"systemMessage": "<segments joined by
\\n\\n>"}`` JSON line. Empty list = no output.

Phase 3 (#122 / R0.1) reinforcement: the verify-first import is performed
inside ``contextlib.suppress(Exception)`` so an ImportError or any
module-level failure never crashes the existing sync-reminder behaviour
(HC-3.6 fail-open).

Issue #133 refactor: top-level execution split into ``build_segments``
(pure — text only) and ``main`` (orchestrator — runs side effects). This
preserves all five existing Stop-hook responsibilities:

  1. sync-reminder text (foundation / structure)
  2. verify-first segment append
  3. completion-gate segment append
  4. Phase 2 marker consumption (IC-11 Option A side effect)
  5. stale verify-log cleanup (Codex-only side effect)

``build_segments`` is callable from tests (in-process, no subprocess) and
covers responsibilities 1–3. ``main`` calls ``build_segments`` then
executes 4 and 5 inside their own suppress blocks.

Issue #269 adds responsibility 6 — the mid-task stage-gate advisory (ADR
050): a Stop-time port of the Claude ``PostToolUse`` shim
(``.claude/hooks/post_tool_stage_gate.py``). ``stage_gate_segment`` is the
pure decision (callable in-process from tests, reusing ``governor.stage_gate``
unchanged); ``main`` evaluates it *before* Phase 2 marker consumption because
the shared ``should_stage_gate`` reads the exception-token markers that step 4
deletes, then claims the once-per-session marker via the shared ``mark_fired``
before appending.

IC-19 (always-fallback) — every locale resolver call must be combined
with the canonical English fallback. The ``_loc(key, fallback)`` helper
centralises this so each call site reads naturally.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path

from _shared import REPO_ROOT, changed_files

# Codex state dir — dedup markers (``stage-gate-*.json``) and the
# exception-token markers the stage-gate policy reads. Mirrors
# ``verify_first`` / ``completion_gate``; ``HARNESS_STATE_ROOT`` lets tests
# redirect it.
STATE_ROOT = Path(os.environ.get("HARNESS_STATE_ROOT", REPO_ROOT))
STATE_DIR = STATE_ROOT / ".codex" / "state"

# AGENT_LOCALE resolver (issue #133) — separate try block so a locale.py
# failure cannot break sync reminders. Keeps the canonical English values
# inline below as the second arg to _loc(), preserving Issue AC.
_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from governor.locale import (  # noqa: E402 — sys.path adjusted above
        get_locale_string as _resolve_locale_string,
    )
except Exception:  # noqa: BLE001 — HC-5.5 fail-open

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


try:
    from governor.sync_advisory import (  # noqa: E402
        classify_advisory as _classify_advisory,
    )

    _SYNC_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open
    _classify_advisory = None  # type: ignore[assignment]
    _SYNC_OK = False


# Mid-task stage-gate policy (ADR 050, #269) — separate try block so a
# stage_gate.py import failure cannot silence sync reminders (HC-5.5). The
# reminder text is imported, never redeclared, so Claude and Codex share one
# canonical string (ADR050-G4).
try:
    from governor.stage_gate import (  # noqa: E402 — sys.path adjusted above
        PLAN_EXECUTE_REMINDER,
        STAGE_GATE_REMINDER,
        default_ledger_path,
        is_implementation_source,
        mark_fired,
        should_plan_execute_gate,
        should_stage_gate,
    )

    _STAGE_GATE_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open
    PLAN_EXECUTE_REMINDER = ""
    STAGE_GATE_REMINDER = ""
    default_ledger_path = None  # type: ignore[assignment]
    is_implementation_source = None  # type: ignore[assignment]
    mark_fired = None  # type: ignore[assignment]
    should_plan_execute_gate = None  # type: ignore[assignment]
    should_stage_gate = None  # type: ignore[assignment]
    _STAGE_GATE_OK = False


def _loc(key: str, fallback: str) -> str:
    """Resolve locale string with canonical English fallback (IC-19).

    Convention: always positional — ``_loc("KEY", "fallback text")``.
    The IC-19 callsite test rejects the keyword form so this convention
    is machine-enforced.
    """
    return _resolve_locale_string(key) or fallback


def stage_gate_segment(
    changed: list[str],
    sid: str,
    *,
    state_dir: Path = STATE_DIR,
    ledger_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> str | None:
    """Mid-task stage-gate advisory text for the Codex Stop event (ADR 050, #269).

    Stop-time port of the Claude ``PostToolUse`` shim
    (``.claude/hooks/post_tool_stage_gate.py``). Codex has no per-edit
    ``file_path``, only a changed-file *set*, so this bridges the set to the
    shared single-file ``should_stage_gate`` policy (Approach A): it
    synthesizes a PostToolUse-shaped payload for the first changed
    implementation source and defers the whole decision — gated ledger stage,
    plan-waiver token, once-per-session dedup read — to the shared policy, so
    Claude and Codex evaluate one decision surface. The gate fires when *any*
    changed file is an implementation source, so short-circuiting on the first
    one is sufficient (dedup makes multi-fire moot regardless).

    Pure: performs no writes. The ``mark_fired`` claim is the caller's job
    (see ``main``) so a race-losing concurrent hook stays silent (R1.3).
    Returns the locale-rendered reminder text when the gate fires, else None.
    """
    if not _STAGE_GATE_OK:
        return None
    impl = next(
        (path for path in changed if is_implementation_source(path, repo_root)),
        None,
    )
    if impl is None:
        return None
    payload = {"tool_input": {"file_path": impl}, "session_id": sid}
    resolved_ledger = (
        ledger_path if ledger_path is not None else default_ledger_path(STATE_ROOT)
    )
    if not should_stage_gate(payload, state_dir, resolved_ledger, repo_root):
        return None
    # IC-19: combine the resolver result with the canonical English fallback so
    # an empty locale lookup never appends a blank segment. Mirrors the Claude
    # shim's emit line exactly (imported reminder text, never inline — ADR050-G4).
    return _resolve_locale_string("STAGE_GATE_REMINDER") or STAGE_GATE_REMINDER


def plan_execute_segment(
    changed: list[str],
    sid: str,
    *,
    state_dir: Path = STATE_DIR,
    ledger_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> str | None:
    """Plan→execute boundary advisory for the Codex Stop event (ADR 054 D8).

    Codex has no ``PreToolUse`` and cannot hard-block like Claude
    (``.claude/hooks/pre_tool_stage_block.py``), so the plan→execute boundary
    surfaces here as a Stop-time advisory — the same shape as
    ``stage_gate_segment`` (#269) but keyed to the ``planned`` stage via the
    shared ``should_plan_execute_gate``. Bridges the Stop-time changed-file set
    to the single-file policy (Approach A) and reuses the shared decision
    unchanged, so Claude's block and Codex's advisory evaluate one surface.

    Pure: performs no writes. The ``mark_fired`` claim is the caller's job
    (see ``main``) so a race-losing concurrent hook stays silent (R1.3).
    Returns the locale-rendered reminder text when the gate fires, else None.
    """
    if not _STAGE_GATE_OK:
        return None
    impl = next(
        (path for path in changed if is_implementation_source(path, repo_root)),
        None,
    )
    if impl is None:
        return None
    payload = {"tool_input": {"file_path": impl}, "session_id": sid}
    resolved_ledger = (
        ledger_path if ledger_path is not None else default_ledger_path(STATE_ROOT)
    )
    if not should_plan_execute_gate(payload, state_dir, resolved_ledger, repo_root):
        return None
    # IC-19 + ADR050-G4: imported reminder text, never inline.
    return _resolve_locale_string("PLAN_EXECUTE_REMINDER") or PLAN_EXECUTE_REMINDER


def build_segments(changed: list[str] | None = None) -> list[str]:
    """Compose advisory segments. Pure: no I/O, no side effects.

    Caller is responsible for default ``changed_files()``-driven discovery
    (``main`` does this) and for the marker / cleanup side effects.

    Returns the segments list ready to be JSON-encoded as a Stop systemMessage.
    """
    if changed is None:
        changed = changed_files()

    advisory_level, advisory_files = (
        _classify_advisory(changed)
        if _SYNC_OK and _classify_advisory is not None
        else (None, [])
    )

    segments: list[str] = []

    # (1) sync-reminder advisory (foundation > structure precedence)
    if advisory_level == "foundation":
        segments.append(
            "\n".join(
                [
                    _loc(
                        "SYNC_FOUNDATION_LEAD",
                        "Guideline sync required before closing this work.",
                    ),
                    _loc("SYNC_FOUNDATION_FILES_HEADER", "Foundation files changed:"),
                    *[f"- {path}" for path in advisory_files[:12]],
                    _loc("SYNC_CODEX_RUN_PRIMARY", "Codex: run $sync-guidelines"),
                    _loc(
                        "SYNC_CLAUDE_RUN_ALSO",
                        "Claude Code: run /sync-guidelines as well",
                    ),
                    _loc(
                        "SYNC_INCOMPLETE_NOTE",
                        "Sync is incomplete until project-dna, AUTO-FIX, REVIEW, "
                        "and Remaining are all reported.",
                    ),
                    _loc(
                        "SYNC_REVIEW_TARGETS_NOTE",
                        "REVIEW targets must be reported even when no automatic "
                        "doc edit is needed.",
                    ),
                ]
            )
        )
    elif advisory_level == "structure":
        segments.append(
            "\n".join(
                [
                    _loc("SYNC_STRUCTURE_LEAD", "Guideline sync recommended."),
                    _loc(
                        "SYNC_STRUCTURE_FILES_HEADER", "Domain structure files changed:"
                    ),
                    *[f"- {path}" for path in advisory_files[:12]],
                    _loc(
                        "SYNC_REPORT_BOTH_NOTE",
                        "When you run sync, report both AUTO-FIX and REVIEW targets "
                        "before closing.",
                    ),
                ]
            )
        )

    # (2) Phase 3 verify-first segment — fail-open
    with contextlib.suppress(Exception):
        import verify_first  # noqa: PLC0415 — local import for fail-open per R0.1

        if verify_first.should_remind():
            segments.append(verify_first.localized_reminder_text())

    # (3) Phase 4 completion-gate segment — fail-open
    with contextlib.suppress(Exception):
        import completion_gate  # noqa: PLC0415

        with contextlib.suppress(Exception):
            seg = completion_gate.governor_changing_segment()
            if seg:
                segments.append(seg)

    # (4) Native workflow advisory — fail-open and advisory-only.
    with contextlib.suppress(Exception):
        from work_ledger import build_workflow_advisory_segments  # noqa: PLC0415

        governor_changing = False
        with contextlib.suppress(Exception):
            from governor import (  # noqa: PLC0415
                is_governor_changing,
                is_log_only_backfill,
                parse_trigger_globs,
            )

            globs = parse_trigger_globs()
            governor_changing = (
                bool(changed)
                and not is_log_only_backfill(changed)
                and is_governor_changing(changed, globs)
            )

        segments.extend(
            build_workflow_advisory_segments(
                changed_files=changed,
                governor_changing=governor_changing,
            )
        )

    return segments


def main() -> int:
    """Stop hook orchestrator.

    Refreshes the work-ledger verification snapshot, calls ``build_segments``
    for advisory responsibilities, then executes marker consumption and stale
    verify-log cleanup side effects. Each side effect is wrapped in its own
    suppress block so a partial failure cannot mask the others or the segments
    output. Stop hook does NOT read stdin (informational fail-open).
    """
    # Work-ledger: refresh verification snapshot before composing native
    # workflow advisories so first-stop output is not stale.
    with contextlib.suppress(Exception):
        from work_ledger import update_verification_from_git  # noqa: PLC0415

        update_verification_from_git()

    changed = changed_files()
    segments = build_segments(changed)

    # (6) Mid-task stage-gate advisory (ADR 050, #269) + plan→execute boundary
    # advisory (ADR 054) — advisory-only, deduped per session. The two gates key
    # off disjoint ledger stages (no-plan set vs ``planned``) so at most one
    # fires; they share the once-per-session marker (one nudge budget). ORDERING:
    # this MUST run before the Phase 2 marker consumption below, because the
    # shared policy reads the exception-token markers (plan-waiver suppression)
    # that ``consume_phase2_markers`` deletes. The exclusive-create ``mark_fired``
    # claim gates the append so concurrent Stop hooks emit at most once (R1.3).
    with contextlib.suppress(Exception):
        import verify_first  # noqa: PLC0415 — local import for fail-open

        sid = verify_first.session_id()
        seg = stage_gate_segment(changed, sid) or plan_execute_segment(changed, sid)
        if seg is not None and mark_fired(STATE_DIR, sid) is not None:
            segments.append(seg)

    # (4) Phase 2 marker consumption + (5) stale verify-log cleanup.
    with contextlib.suppress(Exception):
        import completion_gate  # noqa: PLC0415

        with contextlib.suppress(Exception):
            completion_gate.consume_phase2_markers(completion_gate.STATE_DIR)
        with contextlib.suppress(Exception):
            completion_gate.cleanup_stale_verify_logs(completion_gate.STATE_DIR)

    if segments:
        print(json.dumps({"systemMessage": "\n\n".join(segments)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
