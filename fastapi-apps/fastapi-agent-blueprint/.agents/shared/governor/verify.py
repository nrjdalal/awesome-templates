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

Codex-side ``should_remind`` lives in ``.codex/hooks/verify_first.py``
and is intentionally not part of this module — it depends on
session-scoped state (``CODEX_THREAD_ID`` verify-log, max .py mtime)
that is only meaningful inside the Codex Stop hook.

Behaviour invariance (HC-5.1): ``REMINDER_TEXT`` is byte-for-byte
identical to the pre-Phase-5 constant; ``should_remind_claude`` mirrors
the original predicate ordering. AGENT_LOCALE rendering (issue #133)
is applied at the hook's emit call site via
``governor.locale.get_locale_string`` — this constant remains the
English canonical and the locale.py table re-exports it by reference
so default-locale output stays byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from .markers import MarkerLifecycle, read_latest_token
from .tokens import EXPLORATION_TOKENS

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

    return bool(file_path) and file_path.endswith(".py")


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
