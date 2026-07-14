from __future__ import annotations

import re
import sys

from _shared import command_from_payload, load_payload, tool_input, tool_name

try:
    from governor.code_safety import check_code_safety  # noqa: E402
    from governor.shell_safety import check_bash_command  # noqa: E402

    _SHARED_OK = True
except Exception:  # noqa: BLE001
    check_code_safety = None  # type: ignore[assignment]
    check_bash_command = None  # type: ignore[assignment]
    _SHARED_OK = False


def _extract_bash_write(command: str) -> tuple[str, str] | None:
    match = re.search(r">{1,2}\s*(\S+\.py)\b", command)
    if match:
        return (match.group(1), command)
    match = re.search(r"\btee\s+(?:-a\s+)?(\S+\.py)\b", command)
    if match:
        return (match.group(1), command)
    match = re.search(r"<<\s*[\x27\"]?(\w+)[\x27\"]?\s*>{0,2}\s*(\S+\.py)\b", command)
    if match:
        return (match.group(2), command)
    return None


def _code_payload(payload: dict) -> tuple[str, str] | None:
    name = tool_name(payload)
    inp = tool_input(payload)
    if name in {"replace", "Edit"}:
        path = inp.get("file_path") or inp.get("path") or inp.get("filePath")
        content = inp.get("new_string") or inp.get("newString") or inp.get("content")
    elif name in {"write_file", "Write"}:
        path = inp.get("file_path") or inp.get("path") or inp.get("filePath")
        content = inp.get("content") or inp.get("text")
    else:
        command = command_from_payload(payload)
        extracted = _extract_bash_write(command)
        if extracted is None:
            return None
        path, content = extracted
    if not isinstance(path, str) or not isinstance(content, str):
        return None
    if not path.endswith(".py"):
        return None
    return path, content


def main() -> int:
    payload = load_payload()
    if not _SHARED_OK:
        return 0

    command = command_from_payload(payload)
    if command and check_bash_command is not None:
        reason = check_bash_command(command)
        if reason:
            print(f"[BLOCKED] {reason}", file=sys.stderr)
            return 2

    code_payload = _code_payload(payload)
    if code_payload is None or check_code_safety is None:
        return 0
    path, content = code_payload
    errors = check_code_safety(path, content)
    if errors:
        for error in errors:
            print(f"[BLOCKED] {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
