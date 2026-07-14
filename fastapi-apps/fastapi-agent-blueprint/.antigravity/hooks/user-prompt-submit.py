from __future__ import annotations

import contextlib
import json
import sys
from typing import Any

from _shared import STATE_DIR, load_payload

try:
    from governor import (  # noqa: E402
        Blocked,
        ParsedToken,
        safe_parse_exception_token,
    )
    from governor import (
        write_marker as _shared_write_marker,
    )

    _SHARED_OK = True
except Exception:  # noqa: BLE001
    Blocked = None  # type: ignore[assignment,misc]
    ParsedToken = None  # type: ignore[assignment,misc]
    safe_parse_exception_token = None  # type: ignore[assignment]
    _shared_write_marker = None
    _SHARED_OK = False


def _extract_prompt(payload: dict[str, Any]) -> str:
    for key in ("prompt", "input", "query", "user_prompt", "text"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    for key in ("agent_input", "request", "message"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _extract_prompt(value)
            if nested:
                return nested
    messages = payload.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
    return ""


def main() -> int:
    payload = load_payload()
    prompt = _extract_prompt(payload)
    if not prompt:
        return 0
    if not _SHARED_OK or safe_parse_exception_token is None:
        return 0

    try:
        result = safe_parse_exception_token(prompt)
    except Exception:  # noqa: BLE001
        return 0

    if Blocked is not None and isinstance(result, Blocked):
        print(result.reason, file=sys.stderr)
        if result.additional_context:
            print(result.additional_context, file=sys.stderr)
        return 2

    if ParsedToken is not None and isinstance(result, ParsedToken):
        with contextlib.suppress(Exception):
            if _shared_write_marker is not None:
                _shared_write_marker(result.payload, STATE_DIR)
        print(json.dumps(result.payload, ensure_ascii=False), file=sys.stderr)

    with contextlib.suppress(Exception):
        from work_ledger import update_last_prompt  # noqa: PLC0415

        update_last_prompt(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
