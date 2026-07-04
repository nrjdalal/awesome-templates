"""PostToolUse Edit|Write — verify-first reminder shim (Phase 5 of #117 / #124).

Thin shim over ``.agents/shared/governor``. Preserves the Phase 3
contract:

* Read-only on Phase 2 markers (IC-11) — uses
  ``MarkerLifecycle.READ_ONLY`` so verify-first never consumes markers.
* ``REMINDER_TEXT`` is imported from the shared module so it is
  byte-equal to the Codex side automatically.
* Module-level ``sys.exit`` is forbidden (Plan §D3) — shared import
  failure → ``_SHARED_OK = False`` and ``main()`` returns 0 silently.

Delivery channel (#271, ADR 050 D3 drift candidate): the reminder is
emitted as ``hookSpecificOutput.additionalContext`` JSON on stdout with
exit 0 — the documented model-visible, non-blocking PostToolUse channel.
Plain stderr on exit 0 reaches only the user transcript, never the
model, so the reminder could not influence the agent's next action.
Mirrors the PR #270 stage-gate emit pattern.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = Path(os.environ.get("HARNESS_STATE_ROOT", REPO_ROOT))
STATE_DIR = STATE_ROOT / ".claude" / "state"

_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from governor import (  # noqa: E402 — sys.path adjusted above
        EXPLORATION_TOKENS,
        REMINDER_TEXT,
        MarkerLifecycle,
        _within_24h,
        extract_file_path,
        is_python_source,
        read_latest_token,
    )

    _SHARED_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open
    EXPLORATION_TOKENS = frozenset()
    REMINDER_TEXT = ""
    MarkerLifecycle = None  # type: ignore[assignment,misc]
    read_latest_token = None  # type: ignore[assignment]
    _SHARED_OK = False

    def _within_24h(ts: str) -> bool:  # type: ignore[no-redef]
        return True

    def extract_file_path(payload: dict) -> str | None:  # type: ignore[no-redef]
        return None

    def is_python_source(file_path: str | None) -> bool:  # type: ignore[no-redef]
        return False


# AGENT_LOCALE resolver (issue #133) — separate try block so a locale.py
# import failure cannot silence the shared-governor path. Fallback returns
# "" and the caller combines the result with the canonical English
# constant via `or REMINDER_TEXT` (IC-19).
try:
    from governor.locale import (  # noqa: E402 — sys.path adjusted above
        get_locale_string as _resolve_locale_string,
    )
except Exception:  # noqa: BLE001 — HC-5.5 fail-open

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


def read_latest_token_marker(state_dir: Path) -> str | None:
    """Backward-compat wrapper — read with READ_ONLY lifecycle (IC-11)."""

    if not _SHARED_OK or read_latest_token is None or MarkerLifecycle is None:
        return None
    return read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)


def should_remind(payload: dict, state_dir: Path = STATE_DIR) -> bool:
    if not is_python_source(extract_file_path(payload)):
        return False
    token = read_latest_token_marker(state_dir)
    return token not in EXPLORATION_TOKENS


def main() -> int:
    if not _SHARED_OK:
        return 0
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 0
        if should_remind(payload):
            # IC-19: always combine resolver result with canonical English
            # fallback so an empty locale lookup never emits a blank line.
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": (
                                _resolve_locale_string("REMINDER_TEXT") or REMINDER_TEXT
                            ),
                        }
                    },
                    ensure_ascii=False,
                )
            )
    except Exception:  # noqa: BLE001 — fail-open per HC-5.5
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
