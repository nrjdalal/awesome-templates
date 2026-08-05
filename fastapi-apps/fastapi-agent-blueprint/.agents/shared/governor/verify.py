"""Phase 3 verify-first detection — shared module.

Single source of truth for:

* ``REMINDER_TEXT`` — frozen at Phase 3; string-equal between Claude and
  Codex hook adapters. Parity is enforced by
  ``tests/unit/agents_shared/test_verify_first.py::test_reminder_text_string_equality``.
* ``is_python_source(path)`` — ``.py`` extension predicate.
* ``extract_file_path(payload)`` — pulls ``tool_input.file_path`` out of
  the PostToolUse payload (Claude-side shape).
* ``should_remind_claude(payload, state_dir)`` — Claude verify-first
  decision: True iff a ``.py`` file was edited and the latest Phase 2
  marker is *not* an exploration token.

* ``VERIFY_PATTERNS`` / ``verify_log_path`` / ``append_verify_log`` /
  ``cleanup_stale_verify_logs`` — the verify-log record that
  ``tools/check_state_lifecycle.py`` and ``tools/governor_state_doctor.py``
  read. Added in #334, when ``.claude`` turned out to produce none of it.

Codex-side ``should_remind`` lives in ``.codex/hooks/verify_first.py``
and is intentionally not part of this module — it depends on max .py
mtime, which is only meaningful inside the Codex Stop hook. The
verify-log helpers *were* excluded on the same grounds until a second
harness needed them; what stays harness-specific is the **session id**,
which each adapter resolves and passes in.

Behaviour invariance (HC-5.1): ``REMINDER_TEXT`` is byte-for-byte
identical to the pre-Phase-5 constant; ``should_remind_claude`` mirrors
the original predicate ordering. AGENT_LOCALE rendering (issue #133)
is applied at the hook's emit call site via
``governor.locale.get_locale_string`` — this constant remains the
English canonical and the locale.py table re-exports it by reference
so default-locale output stays byte-identical.
"""

from __future__ import annotations

import contextlib
import json
import re
import time
from pathlib import Path

from .markers import MarkerLifecycle, read_latest_token
from .tokens import EXPLORATION_TOKENS

# Commands that count as verification. `rg pytest docs/` must NOT match — a
# grep for the word is not a run of it — which is why these are word-anchored
# rather than substring checks.
VERIFY_PATTERNS = (
    r"\bpytest\b",
    r"\bmake\s+test\b",
    r"\bmake\s+demo(?:-rag)?\b",
    r"\balembic\s+upgrade\b",
)

# Other sessions' logs are pruned after this; the current session's never is.
_STALE_AFTER_S = 86400


def verify_log_path(state_dir: Path, session_id: str) -> Path:
    """Per-session log file. One file per session keeps appends race-safe."""
    return state_dir / f"verify-log-{session_id}.json"


def append_verify_log(command: str, state_dir: Path, session_id: str) -> Path | None:
    """Record a verify-class command as JSONL. Returns None if it is not one.

    Both ``ts`` (ISO 8601 UTC, for a human reading the file) and
    ``ts_epoch_ns`` (int, for subsecond freshness comparison) are stored —
    the Stop hook compares the latter against source mtimes.
    """
    if not any(re.search(pattern, command) for pattern in VERIFY_PATTERNS):
        return None
    state_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ts_epoch_ns": time.time_ns(),
        "cmd": command,
    }
    path = verify_log_path(state_dir, session_id)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def cleanup_stale_verify_logs(state_dir: Path, session_id: str) -> None:
    """Prune other sessions' verify logs older than 24h.

    Never touches the current session's file: that is live state, and deleting
    it would make the Stop hook conclude nothing was verified this session.
    Failures are suppressed — a hook must not die on a locked or vanished file.
    """
    if not state_dir.exists():
        return
    current_name = verify_log_path(state_dir, session_id).name
    cutoff = time.time() - _STALE_AFTER_S
    for path in state_dir.glob("verify-log-*.json"):
        if path.name == current_name:
            continue
        with contextlib.suppress(Exception):
            if path.stat().st_mtime < cutoff:
                path.unlink()


REMINDER_TEXT = "\n".join(
    [
        "[verify-first] Verify step appears to be missing for the changed .py files.",
        "Run a test or static check before continuing.",
        "Suggested next: `/test-domain run <domain>` (or `pytest tests/unit/<domain>/`)",
        "Silence with `[exploration]` / `[탐색]` prefix when intentionally exploring.",
    ]
)


def extract_file_path(payload: dict) -> str | None:
    """Return ``tool_input.file_path`` when present and a string, else ``None``."""

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    return file_path if isinstance(file_path, str) else None


def is_python_source(file_path: str | None) -> bool:
    """Return True iff ``file_path`` is a non-empty ``.py`` path."""

    return file_path is not None and file_path.endswith(".py")


def should_remind_claude(payload: dict, state_dir: Path) -> bool:
    """Claude-side verify-first decision (Phase 3 read-only contract).

    Returns True when:
      1. The PostToolUse payload edited a ``.py`` file, AND
      2. The latest Phase 2 marker (within 24h) is *not* an exploration
         token (``exploration`` / ``탐색``).

    The reader uses ``MarkerLifecycle.READ_ONLY`` so verify-first never
    consumes markers — Phase 4 Stop hook owns lifecycle (IC-11).
    """

    if not is_python_source(extract_file_path(payload)):
        return False
    token = read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)
    return token not in EXPLORATION_TOKENS
