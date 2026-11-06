"""Format touched Python and record supported actual verification outcomes.

ADR 061 removes per-command log files; malformed inputs and missing results
remain fail-open and never manufacture a successful verification record.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _format_python_paths(command: str) -> None:
    from _shared import REPO_ROOT, extract_python_paths  # local import — fail-open

    paths = extract_python_paths(command)
    if not paths or shutil.which("ruff") is None:
        return
    for path in paths:
        subprocess.run(  # noqa: S603
            ["ruff", "format", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(  # noqa: S603
            ["ruff", "check", "--fix", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


def _extract_exit_code(payload: dict) -> int | None:
    candidates: list[object] = [
        payload.get("exit_code"),
        payload.get("returncode"),
    ]
    for key in ("tool_response", "tool_output", "result"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.extend(
                [
                    value.get("exit_code"),
                    value.get("returncode"),
                    value.get("status"),
                ]
            )
            success = value.get("success")
            if isinstance(success, bool):
                candidates.append(0 if success else 1)

    for candidate in candidates:
        if isinstance(candidate, bool):
            return 0 if candidate else 1
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def _record_verify_class(command: str, payload: dict) -> None:
    shared = Path(__file__).resolve().parents[2] / ".agents" / "shared"
    if str(shared) not in sys.path:
        sys.path.insert(0, str(shared))
    from work_ledger import is_verification_command  # noqa: PLC0415

    if not is_verification_command(command):
        return

    exit_code = _extract_exit_code(payload)
    if exit_code is None:
        return

    with contextlib.suppress(Exception):
        from governor import resolve_session_roots  # noqa: PLC0415
        from work_ledger import mark_verified  # noqa: PLC0415

        # The shared ledger is the session tree's, wherever this copy runs (#425).
        roots = resolve_session_roots(payload)
        if not roots.rejected:
            mark_verified(command, passed=exit_code == 0, state_root=roots.state_root)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        command = (payload.get("tool_input") or {}).get("command", "")
        if not isinstance(command, str) or not command:
            return 0

        # Both branches fail-open per HC-3.6: formatting / outcome recorder errors
        # must never crash the hook.
        with contextlib.suppress(Exception):
            _format_python_paths(command)
        with contextlib.suppress(Exception):
            _record_verify_class(command, payload)
    except Exception:  # noqa: BLE001 — broad fail-open per HC-3.6 + R1.2
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
