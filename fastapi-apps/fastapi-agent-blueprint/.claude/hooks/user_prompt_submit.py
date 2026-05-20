"""UserPromptSubmit Hook (Claude side) — thin shim over `.agents/shared/governor`.

Phase 5 (#124) replaces the inline parser body with imports from the
shared governor module. Behaviour is byte-identical to Phase 2 (HC-5.1).

Module-level invariants (Plan §D3 fail-open redesign):
    * No top-level ``sys.exit`` / ``raise SystemExit`` — the Codex
      Stop adapter imports siblings under ``contextlib.suppress(Exception)``
      which does NOT catch ``SystemExit`` (BaseException). Top-level exits
      would crash the Stop hook entirely.
    * shared import failure → ``_SHARED_OK = False`` plus safe defaults;
      ``main()`` returns 0 silently rather than raising.
    * ``raise SystemExit(main())`` is only reached from
      ``if __name__ == "__main__":`` — i.e. when the file is invoked as
      a subprocess, never when imported as a module.

Decision payload schema is shared with Codex side and frozen by Phase 2:
    {"matched": bool, "token": str | None, "rationale_required": bool}
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
    from harness_debug import debug_log  # noqa: E402
except Exception:  # noqa: BLE001

    def debug_log(event: str, exc: BaseException | None = None) -> None:
        return


try:
    from governor import (  # noqa: E402 — sys.path adjusted above
        TOKEN_REGEX,
        parse_exception_token,
    )
    from governor import write_marker as _shared_write_marker  # noqa: E402

    _SHARED_OK = True
except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open, must not raise SystemExit
    debug_log("claude user-prompt shared import failed", exc)
    TOKEN_REGEX = None  # type: ignore[assignment]
    _shared_write_marker = None
    _SHARED_OK = False

    def parse_exception_token(prompt: str) -> dict:  # type: ignore[no-redef]
        return {"matched": False, "token": None, "rationale_required": False}


def write_marker(payload: dict) -> Path | None:
    """Backward-compat wrapper — uses module-level STATE_DIR (monkeypatchable)."""

    if not _SHARED_OK or _shared_write_marker is None:
        return None
    return _shared_write_marker(payload, STATE_DIR)


def read_prompt() -> str:
    raw = sys.stdin.read()
    if not raw.strip():
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if isinstance(payload, dict):
        return str(payload.get("prompt", "") or "")
    return ""


def main() -> int:
    if not _SHARED_OK:
        return 0
    # Read stdin once; reuse for both token parsing and ledger update.
    prompt = read_prompt()
    try:
        payload = parse_exception_token(prompt)
        write_marker(payload)
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open
        debug_log("claude user-prompt token parse failed", exc)
        return 0

    # Work-ledger: persist last_prompt for cross-session context continuity.
    # Separate try block so a ledger I/O failure never masks the token result.
    if prompt:
        try:
            from work_ledger import update_last_prompt  # noqa: PLC0415

            update_last_prompt(prompt)
        except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open
            debug_log("claude user-prompt ledger update failed", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
