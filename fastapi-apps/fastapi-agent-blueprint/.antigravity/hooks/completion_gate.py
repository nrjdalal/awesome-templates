from __future__ import annotations

import contextlib
import time
from pathlib import Path

from _shared import REPO_ROOT, STATE_DIR, changed_files
from verify_first import session_id

GOVERNOR_PATHS_MD = REPO_ROOT / "docs" / "ai" / "shared" / "governor-paths.md"

try:
    from governor import (  # noqa: E402
        EXPLORATION_TOKENS,
        GOVERNOR_REMINDER_NO_PR,
        GOVERNOR_REMINDER_WITH_PR,
        MarkerLifecycle,
        is_governor_changing,
        is_log_only_backfill,
        match_log_entry,
        parse_trigger_globs,
        pr_number_from_branch,
    )
    from governor import consume_phase2_markers as _shared_consume_phase2_markers
    from governor import read_latest_token as _shared_read_latest_token
    from governor.sync_cosmetic import governor_subset as _shared_governor_subset
    from governor.sync_cosmetic import (
        is_sync_cosmetic_only as _shared_is_sync_cosmetic_only,
    )

    _SHARED_OK = True
except Exception:  # noqa: BLE001
    EXPLORATION_TOKENS = frozenset()
    GOVERNOR_REMINDER_WITH_PR = ""
    GOVERNOR_REMINDER_NO_PR = ""
    MarkerLifecycle = None  # type: ignore[assignment,misc]
    _shared_read_latest_token = None
    _shared_consume_phase2_markers = None
    _shared_governor_subset = None
    _shared_is_sync_cosmetic_only = None
    _SHARED_OK = False

    def parse_trigger_globs(md_path: Path = GOVERNOR_PATHS_MD) -> list[str]:  # type: ignore[no-redef]
        return []

    def is_log_only_backfill(changed: list[str]) -> bool:  # type: ignore[no-redef]
        return False

    def is_governor_changing(changed: list[str], globs: list[str]) -> bool:  # type: ignore[no-redef]
        return False

    def match_log_entry(changed: list[str], current_pr: int | None) -> str:  # type: ignore[no-redef]
        return "missing"

    def pr_number_from_branch() -> int | None:  # type: ignore[no-redef]
        return None


try:
    from governor.locale import (
        get_locale_string as _resolve_locale_string,  # noqa: E402
    )
except Exception:  # noqa: BLE001

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


def _read_latest_token(state_dir: Path) -> str | None:
    if not _SHARED_OK or _shared_read_latest_token is None or MarkerLifecycle is None:
        return None
    return _shared_read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)


def consume_phase2_markers(state_dir: Path = STATE_DIR) -> None:
    if not _SHARED_OK or _shared_consume_phase2_markers is None:
        return
    _shared_consume_phase2_markers(state_dir)


def cleanup_stale_verify_logs(state_dir: Path = STATE_DIR) -> None:
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
    if not _SHARED_OK:
        return None
    try:
        changed = changed_files()
        if not changed or is_log_only_backfill(changed):
            return None
        token = _read_latest_token(STATE_DIR)
        if token in EXPLORATION_TOKENS:
            return None
        globs = parse_trigger_globs()
        if not globs or not is_governor_changing(changed, globs):
            return None
        if (
            _shared_governor_subset is not None
            and _shared_is_sync_cosmetic_only is not None
        ):
            subset = _shared_governor_subset(changed, globs)
            if _shared_is_sync_cosmetic_only(subset):
                return None
        current_pr = pr_number_from_branch()
        status = match_log_entry(changed, current_pr)
        if status in ("match", "unknown"):
            return None
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
    except Exception:  # noqa: BLE001
        return None
