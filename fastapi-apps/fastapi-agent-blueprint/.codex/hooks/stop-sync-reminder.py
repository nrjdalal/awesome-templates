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

IC-19 (always-fallback) — every locale resolver call must be combined
with the canonical English fallback. The ``_loc(key, fallback)`` helper
centralises this so each call site reads naturally.
"""

from __future__ import annotations

import contextlib
import json
import sys

from _shared import REPO_ROOT, changed_files

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


def _loc(key: str, fallback: str) -> str:
    """Resolve locale string with canonical English fallback (IC-19).

    Convention: always positional — ``_loc("KEY", "fallback text")``.
    The IC-19 callsite test rejects the keyword form so this convention
    is machine-enforced.
    """
    return _resolve_locale_string(key) or fallback


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

    return segments


def main() -> int:
    """Stop hook orchestrator.

    Calls ``build_segments`` for responsibilities (1)-(3), then executes
    side-effect responsibilities (4) marker consumption and (5) stale
    verify-log cleanup. Each side effect is wrapped in its own suppress
    block so a partial failure cannot mask the others or the segments
    output. Stop hook does NOT read stdin (informational fail-open).
    """
    segments = build_segments()

    # (4) Phase 2 marker consumption + (5) stale verify-log cleanup.
    with contextlib.suppress(Exception):
        import completion_gate  # noqa: PLC0415

        with contextlib.suppress(Exception):
            completion_gate.consume_phase2_markers(completion_gate.STATE_DIR)
        with contextlib.suppress(Exception):
            completion_gate.cleanup_stale_verify_logs(completion_gate.STATE_DIR)

    # (6) Work-ledger: refresh verification snapshot (fail-open).
    with contextlib.suppress(Exception):
        from work_ledger import update_verification_from_git  # noqa: PLC0415

        update_verification_from_git()

    if segments:
        print(json.dumps({"systemMessage": "\n\n".join(segments)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
