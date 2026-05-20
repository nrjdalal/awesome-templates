"""PreToolUse Hook: Security pattern check before code writing.

Phase 5 / PR-A.4 thin-shim refactor: the four inline security-check
categories (SQL injection, hardcoded secrets, domain-infra import,
sensitive-log) are moved to governor/code_safety.py. This file retains
only the tool-routing logic (_extract_bash_write + check_security dispatch).

Exit 0 = allow, Exit 2 = block.
Fail-open (HC-5.5): shared import failure -> exit 0 (no block).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from governor.code_safety import check_code_safety  # noqa: E402

    _SHARED_OK = True
except Exception:  # noqa: BLE001 — HC-5.5 fail-open
    check_code_safety = None  # type: ignore[assignment]
    _SHARED_OK = False


def _extract_bash_write(command: str) -> tuple[str, str] | None:
    """Detect a write to a .py file in a Bash command and return (path, content).

    Returns None when the command does not perform such a write.
    """
    # > or >> redirect
    m = re.search(r">{1,2}\s*(\S+\.py)\b", command)
    if m:
        return (m.group(1), command)
    # tee [-a] file.py
    m = re.search(r"\btee\s+(?:-a\s+)?(\S+\.py)\b", command)
    if m:
        return (m.group(1), command)
    # heredoc: << EOF > file.py
    m = re.search(r"<<\s*[\x27\"]?(\w+)[\x27\"]?\s*>{0,2}\s*(\S+\.py)\b", command)
    if m:
        return (m.group(2), command)
    return None


def check_security(data: dict) -> list[str]:
    tool = data.get("tool_name", "")
    inp = data.get("tool_input", {})

    if tool == "Edit":
        path = inp.get("file_path", "")
        content = inp.get("new_string", "")
    elif tool == "Write":
        path = inp.get("file_path", "")
        content = inp.get("content", "")
    elif tool == "Bash":
        result = _extract_bash_write(inp.get("command", ""))
        if result is None:
            return []
        path, content = result
    else:
        return []

    if not path.endswith(".py"):
        return []

    if not _SHARED_OK or check_code_safety is None:
        return []

    return check_code_safety(path, content)


def main():
    data = json.load(sys.stdin)
    errors = check_security(data)

    if errors:
        for e in errors:
            print(f"[BLOCKED] {e}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
