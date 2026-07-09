"""PreToolUse Edit|Write — plan→execute boundary hard block (ADR 054, ADR054-G1).

Thin shim over ``governor.stage_gate.should_block_plan_execute_edit``. Blocks
the edit (exit 2 + stderr — the model-visible ``PreToolUse`` channel that
``pre_tool_security.py`` also uses) when an implementation-source edit is
attempted while the work ledger ``workflow.stage`` is ``planned`` and no
plan-waiver token is active: i.e. a plan exists but ``/execute-plan`` has not
been invoked.

Contrast with ``post_tool_stage_gate.py`` (ADR 050): that shim is a
*non-blocking* advisory for the "no plan at all" stages and always exits 0.
This shim *blocks* for the ``planned`` stage only, and there is deliberately no
``PostToolUse`` advisory for ``planned`` on Claude — the block intercepts the
same cases pre-edit, so an advisory there would be dead code (ADR 054 D4).

Module-level invariants (Plan §D3 fail-open, mirrors ``post_tool_stage_gate``):
    * No top-level ``sys.exit`` / ``raise SystemExit`` outside ``__main__``.
    * Shared import failure → ``_SHARED_OK = False``; ``main()`` returns 0
      (ALLOW) silently (HC-5.5 / ADR054-G5 — best-effort, never fail-closed).
    * Reads only (work ledger + token markers); writes nothing.
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
        PLAN_EXECUTE_REMINDER,
        default_ledger_path,
        should_block_plan_execute_edit,
    )

    _SHARED_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open (ADR054-G5)
    PLAN_EXECUTE_REMINDER = ""
    default_ledger_path = None  # type: ignore[assignment]
    should_block_plan_execute_edit = None  # type: ignore[assignment]
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


# PreToolUse control codes: 0 = allow, 2 = block (stderr fed to the model).
_ALLOW = 0
_BLOCK = 2


def main() -> int:
    if not _SHARED_OK:
        return _ALLOW
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return _ALLOW
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return _ALLOW
        ledger_path = default_ledger_path(STATE_ROOT)
        if not should_block_plan_execute_edit(
            payload, STATE_DIR, ledger_path, REPO_ROOT
        ):
            return _ALLOW
        # IC-19: combine resolver result with the canonical English fallback so
        # an empty locale lookup never emits a blank block reason. The reminder
        # text is imported, never inlined (ADR050-G4); the [BLOCKED] cue is
        # hook-local framing, not the canonical reminder body.
        reminder = (
            _resolve_locale_string("PLAN_EXECUTE_REMINDER") or PLAN_EXECUTE_REMINDER
        )
        print(
            f"[BLOCKED] plan→execute boundary (ADR 054):\n{reminder}", file=sys.stderr
        )
        return _BLOCK
    except Exception:  # noqa: BLE001 — fail-open per HC-5.5 (never fail-closed)
        return _ALLOW


if __name__ == "__main__":
    raise SystemExit(main())
