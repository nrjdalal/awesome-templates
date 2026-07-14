from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from _shared import REPO_ROOT, STATE_DIR, changed_files, session_env_id

try:
    from governor import (  # noqa: E402
        EXPLORATION_TOKENS,
        REMINDER_TEXT,
        MarkerLifecycle,
    )
    from governor import read_latest_token as _shared_read_latest_token  # noqa: E402

    _SHARED_OK = True
except Exception:  # noqa: BLE001
    EXPLORATION_TOKENS = frozenset()
    REMINDER_TEXT = ""
    MarkerLifecycle = None  # type: ignore[assignment,misc]
    _shared_read_latest_token = None
    _SHARED_OK = False

try:
    from governor.locale import (
        get_locale_string as _resolve_locale_string,  # noqa: E402
    )
except Exception:  # noqa: BLE001

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


VERIFY_PATTERNS = (
    r"\bpytest\b",
    r"\bmake\s+test\b",
    r"\bmake\s+demo(?:-rag)?\b",
    r"\balembic\s+upgrade\b",
)
_PROCESS_START_NS = time.monotonic_ns()


def localized_reminder_text() -> str:
    return _resolve_locale_string("REMINDER_TEXT") or REMINDER_TEXT


def session_id() -> str:
    explicit = session_env_id()
    if explicit:
        return explicit
    return f"{os.getppid()}-{os.getpid()}-{_PROCESS_START_NS:016x}"


def verify_log_path(state_dir: Path = STATE_DIR) -> Path:
    return state_dir / f"verify-log-{session_id()}.json"


def append_verify_log(command: str, state_dir: Path = STATE_DIR) -> Path | None:
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
    if not _SHARED_OK or _shared_read_latest_token is None or MarkerLifecycle is None:
        return None
    return _shared_read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)


def changed_python_files() -> list[str]:
    return [path for path in changed_files() if path.endswith(".py")]


def max_changed_py_mtime_ns(repo_root: Path = REPO_ROOT) -> int | None:
    mtimes_ns: list[int] = []
    for relative in changed_python_files():
        try:
            mtimes_ns.append((repo_root / relative).stat().st_mtime_ns)
        except OSError:
            continue
    if not mtimes_ns:
        return None
    return max(mtimes_ns)


def should_remind() -> bool:
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
    return verify_ns < py_mtime_ns
