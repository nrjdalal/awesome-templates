"""PreToolUse Hook (Codex side) — thin shim over governor.shell_safety.

Phase 5 / PR-A.4 replaces the five inline regex checks with a single call
to ``check_bash_command`` from the shared governor module. The deny reason
strings are now the single source of truth inside governor/shell_safety.py.

Fail-open (HC-5.5): if the shared import fails, the hook exits 0 without
blocking (the governor module is not on the critical path for session
continuity).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from harness_debug import debug_log  # noqa: E402
except Exception:  # noqa: BLE001

    def debug_log(event: str, exc: BaseException | None = None) -> None:
        return


try:
    from governor.shell_safety import check_bash_command  # noqa: E402

    _SHARED_OK = True
except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open
    debug_log("codex pre-tool shared import failed", exc)
    check_bash_command = None  # type: ignore[assignment]
    _SHARED_OK = False


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    raise SystemExit(0)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        debug_log("codex pre-tool payload parse failed", exc)
        return
    command = payload.get("tool_input", {}).get("command", "")

    if not _SHARED_OK or check_bash_command is None:
        debug_log("codex pre-tool safety check unavailable")
        return

    result = check_bash_command(command)
    if result is not None:
        deny(result)


if __name__ == "__main__":
    main()
