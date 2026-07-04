"""PostToolUse Edit|Write — mid-task stage-gate advisory shim (ADR 050, #268).

Thin shim over ``.agents/shared/governor.stage_gate``. Emits the advisory
as ``hookSpecificOutput.additionalContext`` JSON on stdout with exit 0 —
the documented model-visible, non-blocking PostToolUse channel (plain
stderr on exit 0 reaches only the user transcript; see ADR 050 D3).

Module-level invariants (Plan §D3 fail-open redesign, mirrors
``verify_first.py``):
    * No top-level ``sys.exit`` / ``raise SystemExit``.
    * Shared import failure → ``_SHARED_OK = False``; ``main()`` returns 0
      silently (HC-5.5).
    * Writes only under ``HARNESS_STATE_ROOT/.claude/state`` (dedup
      markers); reads the work ledger read-only.
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
        STAGE_GATE_REMINDER,
        default_ledger_path,
        extract_session_id,
        mark_fired,
        should_stage_gate,
    )

    _SHARED_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open
    STAGE_GATE_REMINDER = ""
    default_ledger_path = None  # type: ignore[assignment]
    extract_session_id = None  # type: ignore[assignment]
    mark_fired = None  # type: ignore[assignment]
    should_stage_gate = None  # type: ignore[assignment]
    _SHARED_OK = False

# AGENT_LOCALE resolver (issue #133) — separate try block so a locale.py
# import failure cannot silence the shared-governor path (IC-19).
try:
    from governor.locale import (  # noqa: E402 — sys.path adjusted above
        get_locale_string as _resolve_locale_string,
    )
except Exception:  # noqa: BLE001 — HC-5.5 fail-open

    def _resolve_locale_string(key: str) -> str:  # type: ignore[no-redef]
        return ""


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
        ledger_path = default_ledger_path(STATE_ROOT)
        if not should_stage_gate(payload, STATE_DIR, ledger_path, REPO_ROOT):
            return 0
        # R1.3: exclusive-create claim — only the winning writer emits, so
        # concurrent sibling hook runs produce at most one reminder.
        if mark_fired(STATE_DIR, extract_session_id(payload)) is None:
            return 0
        # IC-19: combine resolver result with the canonical English fallback
        # so an empty locale lookup never emits a blank advisory.
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": (
                            _resolve_locale_string("STAGE_GATE_REMINDER")
                            or STAGE_GATE_REMINDER
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
