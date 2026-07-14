from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

from _shared import REPO_ROOT, STATE_DIR, STATE_ROOT, changed_files

_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from governor.locale import (
        get_locale_string as _resolve_locale_string,  # noqa: E402
    )
except Exception:  # noqa: BLE001

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


try:
    from governor.sync_advisory import (
        classify_advisory as _classify_advisory,  # noqa: E402
    )

    _SYNC_OK = True
except Exception:  # noqa: BLE001
    _classify_advisory = None  # type: ignore[assignment]
    _SYNC_OK = False

try:
    from governor.stage_gate import (  # noqa: E402
        PLAN_EXECUTE_REMINDER,
        STAGE_GATE_REMINDER,
        default_ledger_path,
        is_implementation_source,
        mark_fired,
        should_plan_execute_gate,
        should_stage_gate,
    )

    _STAGE_GATE_OK = True
except Exception:  # noqa: BLE001
    PLAN_EXECUTE_REMINDER = ""
    STAGE_GATE_REMINDER = ""
    default_ledger_path = None  # type: ignore[assignment]
    is_implementation_source = None  # type: ignore[assignment]
    mark_fired = None  # type: ignore[assignment]
    should_plan_execute_gate = None  # type: ignore[assignment]
    should_stage_gate = None  # type: ignore[assignment]
    _STAGE_GATE_OK = False


def _loc(key: str, fallback: str) -> str:
    return _resolve_locale_string(key) or fallback


def stage_gate_segment(
    changed: list[str],
    sid: str,
    *,
    state_dir: Path = STATE_DIR,
    ledger_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> str | None:
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
    return _resolve_locale_string("STAGE_GATE_REMINDER") or STAGE_GATE_REMINDER


def plan_execute_segment(
    changed: list[str],
    sid: str,
    *,
    state_dir: Path = STATE_DIR,
    ledger_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> str | None:
    """Plan->execute boundary advisory (ADR 054 D8), keyed to the ``planned``
    stage via the shared ``should_plan_execute_gate``. Antigravity's AfterAgent
    is the parity surface for Claude's PreToolUse hard block — advisory-only,
    reusing the shared single-file policy unchanged. The ``mark_fired`` claim is
    the caller's job (see ``main``) so it dedupes with ``stage_gate_segment``."""
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
    return _resolve_locale_string("PLAN_EXECUTE_REMINDER") or PLAN_EXECUTE_REMINDER


def build_segments(changed: list[str] | None = None) -> list[str]:
    if changed is None:
        changed = changed_files()
    advisory_level, advisory_files = (
        _classify_advisory(changed)
        if _SYNC_OK and _classify_advisory is not None
        else (None, [])
    )
    segments: list[str] = []
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
                    "Antigravity: run the matching workspace sync skill before closing.",
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
                        "When you run sync, report both AUTO-FIX and REVIEW targets before closing.",
                    ),
                ]
            )
        )

    with contextlib.suppress(Exception):
        import verify_first  # noqa: PLC0415

        if verify_first.should_remind():
            segments.append(verify_first.localized_reminder_text())

    with contextlib.suppress(Exception):
        import completion_gate  # noqa: PLC0415

        segment = completion_gate.governor_changing_segment()
        if segment:
            segments.append(segment)

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
    with contextlib.suppress(Exception):
        from work_ledger import update_verification_from_git  # noqa: PLC0415

        update_verification_from_git()

    changed = changed_files()
    segments = build_segments(changed)

    with contextlib.suppress(Exception):
        import verify_first  # noqa: PLC0415

        sid = verify_first.session_id()
        # Stage-gate (mid-task, ADR 050) OR plan->execute boundary (ADR 054)
        # fire at most once per session via the shared exclusive-create marker.
        segment = stage_gate_segment(changed, sid) or plan_execute_segment(changed, sid)
        if segment is not None and mark_fired(STATE_DIR, sid) is not None:
            segments.append(segment)

    with contextlib.suppress(Exception):
        import completion_gate  # noqa: PLC0415

        with contextlib.suppress(Exception):
            completion_gate.consume_phase2_markers(completion_gate.STATE_DIR)
        with contextlib.suppress(Exception):
            completion_gate.cleanup_stale_verify_logs(completion_gate.STATE_DIR)

    # Gemini CLI / Antigravity parse a hook's stdout as JSON on exit 0 and
    # reject plain text. Surface the merged AfterAgent advisory bundle (sync /
    # verify-first / completion-gate / workflow / stage-gate) via the JSON
    # `systemMessage` field so it is shown alongside the response.
    if segments:
        print(json.dumps({"systemMessage": "\n\n".join(segments)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
