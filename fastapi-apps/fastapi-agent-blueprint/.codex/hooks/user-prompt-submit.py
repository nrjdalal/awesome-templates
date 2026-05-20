"""UserPromptSubmit Hook (Codex side) — thin shim over `.agents/shared/governor`.

Phase 5 (#124) replaces the inline parser + safety routing with imports
from the shared governor module. Behaviour preserves Phase 2 invariants:

* HC-1 (safety-block-first → parser-second) is enforced *inside* the
  shared ``safe_parse_exception_token`` single-entry function. The shim
  cannot reach the parser past a destructive-prompt block (R0-C.1
  rejected callable-injection bypass surface).
* ``PROMPT_RULES`` and ``parse_exception_token`` remain importable from
  this module so existing tests continue to monkeypatch / inspect them
  directly.
* No top-level ``sys.exit``: shared import failure → silent ``main()``
  return-0 (HC-5.5; Plan §D3 fail-open redesign).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = Path(os.environ.get("HARNESS_STATE_ROOT", REPO_ROOT))
STATE_DIR = STATE_ROOT / ".codex" / "state"

_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from harness_debug import debug_log  # noqa: E402
except Exception:  # noqa: BLE001

    def debug_log(event: str, exc: BaseException | None = None) -> None:
        return


try:
    from governor import (  # noqa: E402 — sys.path adjusted above
        PROMPT_RULES,
        TOKEN_REGEX,
        Blocked,
        ParsedToken,
        parse_exception_token,
        safe_parse_exception_token,
    )
    from governor import write_marker as _shared_write_marker  # noqa: E402

    _SHARED_OK = True
except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open
    debug_log("codex user-prompt shared import failed", exc)
    PROMPT_RULES = []  # type: ignore[assignment]
    TOKEN_REGEX = None  # type: ignore[assignment]
    Blocked = None  # type: ignore[assignment,misc]
    ParsedToken = None  # type: ignore[assignment,misc]
    safe_parse_exception_token = None  # type: ignore[assignment]
    _shared_write_marker = None
    _SHARED_OK = False

    def parse_exception_token(prompt: str) -> dict:  # type: ignore[no-redef]
        return {"matched": False, "token": None, "rationale_required": False}


def write_marker(payload: dict) -> Path | None:
    """Backward-compat wrapper — uses module-level STATE_DIR (monkeypatchable)."""

    if not _SHARED_OK or _shared_write_marker is None:
        return None
    return _shared_write_marker(payload, STATE_DIR)


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload_in = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload_in, dict):
        return 0
    prompt = payload_in.get("prompt", "") or ""

    if not _SHARED_OK or safe_parse_exception_token is None:
        return 0

    try:
        result = safe_parse_exception_token(prompt)
    except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open
        debug_log("codex user-prompt token parse failed", exc)
        return 0

    if Blocked is not None and isinstance(result, Blocked):
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": result.reason,
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": result.additional_context,
                    },
                }
            )
        )
        return 0

    if ParsedToken is not None and isinstance(result, ParsedToken):
        try:
            write_marker(result.payload)
        except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open
            debug_log("codex user-prompt marker write failed", exc)
        print(json.dumps(result.payload, ensure_ascii=False), file=sys.stderr)

    # Work-ledger: persist last_prompt for cross-session context continuity.
    if prompt:
        with contextlib.suppress(Exception):  # HC-5.5 fail-open
            from work_ledger import update_last_prompt  # noqa: PLC0415

            update_last_prompt(prompt)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
