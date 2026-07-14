"""Stop-side verify-first helper (Phase 5 of #117 / #124) — thin shim.

Imported by ``.codex/hooks/stop-sync-reminder.py`` and
``.codex/hooks/post-tool-format.py``. NOT registered as its own hook.

Phase 5 consolidates governor *policy* (REMINDER_TEXT, _within_24h,
EXPLORATION_TOKENS, marker reader) into ``.agents/shared/governor``.
Codex-specific *runtime* state — session id, verify-log writer/reader,
changed .py mtime — stays here because it depends on
``CODEX_THREAD_ID`` and the per-session ``verify-log-{session}.json``
file lifecycle.

Module-level invariant (Plan §D3): no top-level ``sys.exit`` /
``raise SystemExit``. ``stop-sync-reminder.py`` imports this module
under ``contextlib.suppress(Exception)`` which does NOT catch
``SystemExit`` — top-level exits would crash the whole Stop hook.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from _shared import REPO_ROOT, changed_files

STATE_ROOT = Path(os.environ.get("HARNESS_STATE_ROOT", REPO_ROOT))
STATE_DIR = STATE_ROOT / ".codex" / "state"

_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from governor import (  # noqa: E402 — sys.path adjusted above
        EXPLORATION_TOKENS,
        REMINDER_TEXT,
        MarkerLifecycle,
        _within_24h,
    )
    from governor import read_latest_token as _shared_read_latest_token  # noqa: E402

    _SHARED_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open
    EXPLORATION_TOKENS = frozenset()
    REMINDER_TEXT = ""
    MarkerLifecycle = None  # type: ignore[assignment,misc]
    _shared_read_latest_token = None  # type: ignore[assignment]
    _SHARED_OK = False

    def _within_24h(ts: str) -> bool:  # type: ignore[no-redef]
        return True


# AGENT_LOCALE resolver (issue #133) — separate try block so a locale.py
# import failure cannot silence the shared-governor path. Stop hook reads
# REMINDER_TEXT via localized_reminder_text() below.
try:
    from governor.locale import (  # noqa: E402 — sys.path adjusted above
        get_locale_string as _resolve_locale_string,
    )
except Exception:  # noqa: BLE001 — HC-5.5 fail-open

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


def localized_reminder_text() -> str:
    """Return REMINDER_TEXT in the current locale; English fallback (IC-19)."""
    return _resolve_locale_string("REMINDER_TEXT") or REMINDER_TEXT


VERIFY_PATTERNS = (
    r"\bpytest\b",
    r"\bmake\s+test\b",
    r"\bmake\s+demo(?:-rag)?\b",
    r"\balembic\s+upgrade\b",
)

# Cached at module import — collision-resistant suffix even if PPID is reused.
_PROCESS_START_NS = time.monotonic_ns()


def session_id() -> str:
    """Stable id within one Codex CLI invocation.

    Priority: ``CODEX_THREAD_ID`` (Codex-injected, same across all hook
    processes in a session) → ``CODEX_SESSION_ID`` (fallback alias) →
    ``ppid-pid-startns`` (non-Codex environments only;
    writer/reader-incompatible in live Codex).
    """

    explicit = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")
    if explicit:
        return explicit
    return f"{os.getppid()}-{os.getpid()}-{_PROCESS_START_NS:016x}"


def verify_log_path(state_dir: Path = STATE_DIR) -> Path:
    return state_dir / f"verify-log-{session_id()}.json"


def append_verify_log(command: str, state_dir: Path = STATE_DIR) -> Path | None:
    """Append a verify-class command record to current-session JSONL.

    Append-only (race-safe across concurrent Codex sessions writing
    different files). Records both ``ts`` (ISO 8601 UTC for human
    reading) and ``ts_epoch_ns`` (int for subsecond freshness comparison).
    Returns the log path on append, or ``None`` if the command does not
    match any verify pattern.
    """

    if not any(re.search(pattern, command) for pattern in VERIFY_PATTERNS):
        return None
    state_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ts_epoch_ns": time.time_ns(),
        "cmd": command,
    }
    path = verify_log_path(state_dir)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def current_session_latest_verify_ns(state_dir: Path = STATE_DIR) -> int | None:
    """Most-recent verify-class entry in the CURRENT session's log only.

    Reads ``verify-log-{session_id()}.json`` exclusively — does not glob
    other sessions. Returns the largest ``ts_epoch_ns`` integer, or
    ``None`` if the file is missing / empty / every line malformed.
    """

    path = verify_log_path(state_dir)
    if not path.exists():
        return None
    latest: int | None = None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        ns = record.get("ts_epoch_ns")
        if isinstance(ns, int) and (latest is None or ns > latest):
            latest = ns
    return latest


def read_latest_token_marker(state_dir: Path) -> str | None:
    """Backward-compat wrapper — READ_ONLY lifecycle (IC-11)."""

    if not _SHARED_OK or _shared_read_latest_token is None or MarkerLifecycle is None:
        return None
    return _shared_read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)


def changed_python_files() -> list[str]:
    return [p for p in changed_files() if p.endswith(".py")]


def max_changed_py_mtime_ns(repo_root: Path = REPO_ROOT) -> int | None:
    """Largest ``st_mtime_ns`` across changed `.py` files.

    Uses ``stat().st_mtime_ns`` directly so subsecond ordering is
    preserved. Returns ``None`` when no changed `.py` exists or when
    every file disappeared between ``git status`` and the stat (race).
    """

    paths = changed_python_files()
    mtimes_ns: list[int] = []
    for relative in paths:
        full = repo_root / relative
        try:
            mtimes_ns.append(full.stat().st_mtime_ns)
        except OSError:
            continue
    if not mtimes_ns:
        return None
    return max(mtimes_ns)


def should_remind() -> bool:
    """Codex-side decision. ``False`` = silent, ``True`` = emit reminder.

    Logic:
      1. No changed `.py` → silent.
      2. Latest Phase 2 marker is ``[exploration]``/``[탐색]`` → silent.
      3. Current session has a verify-class log entry whose
         ``ts_epoch_ns`` ≥ the largest changed-`.py` ``st_mtime_ns`` →
         silent (verification is fresh enough).
      4. Otherwise → emit reminder.
    """

    if not changed_python_files():
        return False
    token = read_latest_token_marker(STATE_DIR)
    if token in EXPLORATION_TOKENS:
        return False
    verify_ns = current_session_latest_verify_ns()
    if verify_ns is None:
        return True
    py_mtime_ns = max_changed_py_mtime_ns()
    if py_mtime_ns is None:
        return True
    # Stale verify when log is older than the most recent .py edit.
    return verify_ns < py_mtime_ns
