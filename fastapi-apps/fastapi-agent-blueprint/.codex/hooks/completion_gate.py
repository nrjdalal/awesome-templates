"""Completion-gate helper (Codex side, Phase 5 of #117 / #124) — thin shim.

Imported by ``.codex/hooks/stop-sync-reminder.py`` inside a
``with contextlib.suppress(Exception):`` block (IC-2 single Stop event):

    seg = completion_gate.governor_changing_segment()
    if seg:
        segments.append(seg)
    completion_gate.consume_phase2_markers(STATE_DIR)
    completion_gate.cleanup_stale_verify_logs(STATE_DIR)

Phase 5 consolidates governor *policy* into ``.agents/shared/governor``.
This shim retains:

* ``cleanup_stale_verify_logs`` — Codex-only, depends on
  ``verify_first.session_id()`` to preserve the current session's
  verify-log file while pruning stale ones from other sessions.
* Manual orchestration in ``governor_changing_segment`` so module-level
  attrs (``changed_files`` from ``_shared``, ``_read_latest_token``,
  ``pr_number_from_branch``) remain monkeypatchable for the existing
  test suite (PR #128 R0/R1 sample-run patterns).

IC-10 preserved: glob list parsed from ``governor-paths.md``; no inline.
HC-5.5: shared import failure → silent return-0.
Module-level invariant (Plan §D3): no top-level ``sys.exit``.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path

from _shared import REPO_ROOT, changed_files
from verify_first import session_id

STATE_ROOT = Path(os.environ.get("HARNESS_STATE_ROOT", REPO_ROOT))
STATE_DIR = STATE_ROOT / ".codex" / "state"
GOVERNOR_PATHS_MD = REPO_ROOT / "docs" / "ai" / "shared" / "governor-paths.md"

_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from governor import (  # noqa: E402 — sys.path adjusted above
        EXPLORATION_TOKENS,
        GOVERNOR_REMINDER_NO_PR,
        GOVERNOR_REMINDER_WITH_PR,
        MarkerLifecycle,
        _within_24h,
        is_governor_changing,
        is_log_only_backfill,
        match_log_entry,
        parse_trigger_globs,
        pr_number_from_branch,
    )
    from governor import (  # noqa: E402
        consume_phase2_markers as _shared_consume_phase2_markers,
    )
    from governor import read_latest_token as _shared_read_latest_token  # noqa: E402
    from governor.completion_gate import _matches_glob  # noqa: E402
    from governor.sync_cosmetic import (  # noqa: E402 — ADR 047 D4 self-loop carve-out
        governor_subset as _shared_governor_subset,
    )
    from governor.sync_cosmetic import (  # noqa: E402
        is_sync_cosmetic_only as _shared_is_sync_cosmetic_only,
    )

    _SHARED_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open
    EXPLORATION_TOKENS = frozenset()
    GOVERNOR_REMINDER_WITH_PR = ""
    GOVERNOR_REMINDER_NO_PR = ""
    MarkerLifecycle = None  # type: ignore[assignment,misc]
    _shared_read_latest_token = None
    _shared_consume_phase2_markers = None
    _shared_governor_subset = None
    _shared_is_sync_cosmetic_only = None
    _SHARED_OK = False

    def _within_24h(ts: str) -> bool:  # type: ignore[no-redef]
        return True

    def parse_trigger_globs(md_path: Path = GOVERNOR_PATHS_MD) -> list[str]:  # type: ignore[no-redef]
        return []

    def _matches_glob(path: str, glob: str) -> bool:  # type: ignore[no-redef]
        return False

    def is_log_only_backfill(changed: list[str]) -> bool:  # type: ignore[no-redef]
        return False

    def is_governor_changing(  # type: ignore[no-redef]
        changed: list[str], globs: list[str]
    ) -> bool:
        return False

    def match_log_entry(  # type: ignore[no-redef]
        changed: list[str], current_pr: int | None
    ) -> str:
        return "missing"

    def pr_number_from_branch() -> int | None:  # type: ignore[no-redef]
        return None


# AGENT_LOCALE resolver (issue #133) — separate try block so a locale.py
# import failure cannot silence the shared-governor path.
try:
    from governor.locale import (  # noqa: E402 — sys.path adjusted above
        get_locale_string as _resolve_locale_string,
    )
except Exception:  # noqa: BLE001 — HC-5.5 fail-open

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


def _read_latest_token(state_dir: Path) -> str | None:
    """Module-level wrapper so tests can monkeypatch ``_read_latest_token``."""

    if not _SHARED_OK or _shared_read_latest_token is None or MarkerLifecycle is None:
        return None
    return _shared_read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)


def consume_phase2_markers(state_dir: Path = STATE_DIR) -> None:
    """Delete all Phase 2 exception-token markers (IC-11 Option A)."""

    if not _SHARED_OK or _shared_consume_phase2_markers is None:
        return
    _shared_consume_phase2_markers(state_dir)


def cleanup_stale_verify_logs(state_dir: Path = STATE_DIR) -> None:
    """Delete verify-log-*.json files older than 24h from OTHER sessions.

    Codex-only — depends on ``verify_first.session_id()`` to know which
    log file belongs to the current session and must not be pruned.
    """

    if not state_dir.exists():
        return
    current_name = f"verify-log-{session_id()}.json"
    cutoff = time.time() - 86400
    for path in state_dir.glob("verify-log-*.json"):
        if path.name == current_name:
            continue
        with contextlib.suppress(Exception):
            if path.stat().st_mtime < cutoff:
                path.unlink()


def governor_changing_segment() -> str | None:
    """Pillar 7 reminder, manually orchestrated so module attrs stay
    monkeypatchable for the existing test suite."""

    if not _SHARED_OK:
        return None
    try:
        ch = changed_files()
        if not ch:
            return None
        if is_log_only_backfill(ch):
            return None
        token = _read_latest_token(STATE_DIR)
        if token in EXPLORATION_TOKENS:
            return None
        globs = parse_trigger_globs()
        if not globs or not is_governor_changing(ch, globs):
            return None
        # ADR 047 D4 — `/sync-guidelines` cosmetic subset carve-out.
        if (
            _shared_governor_subset is not None
            and _shared_is_sync_cosmetic_only is not None
        ):
            subset = _shared_governor_subset(ch, globs)
            if _shared_is_sync_cosmetic_only(subset):
                return None
        current_pr = pr_number_from_branch()
        status = match_log_entry(ch, current_pr)
        if status in ("match", "unknown"):
            return None
        # IC-19: combine resolver result with canonical English fallback
        # BEFORE .format() — empty resolver → "".format(pr=...) is also "".
        if current_pr is None:
            return (
                _resolve_locale_string("GOVERNOR_REMINDER_NO_PR")
                or GOVERNOR_REMINDER_NO_PR
            )
        template = (
            _resolve_locale_string("GOVERNOR_REMINDER_WITH_PR")
            or GOVERNOR_REMINDER_WITH_PR
        )
        return template.format(pr=current_pr)
    except Exception:  # noqa: BLE001 — HC-5.5 fail-open
        return None
