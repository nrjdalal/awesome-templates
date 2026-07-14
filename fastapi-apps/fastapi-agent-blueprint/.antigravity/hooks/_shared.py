from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = Path(os.environ.get("HARNESS_STATE_ROOT", REPO_ROOT))
STATE_DIR = STATE_ROOT / ".antigravity" / "state"

SHARED_PKG = REPO_ROOT / ".agents" / "shared"
if str(SHARED_PKG) not in sys.path:
    sys.path.insert(0, str(SHARED_PKG))


try:
    from harness_debug import debug_log  # noqa: E402
except Exception:  # noqa: BLE001

    def debug_log(event: str, exc: BaseException | None = None) -> None:
        return


# Delegate changed-file discovery to the shared governor policy so Antigravity
# inherits the same "uncommitted + untracked, with 2h recent-commit fallback"
# behaviour as Codex — otherwise a clean (fully committed) worktree returns []
# and silences every AfterAgent advisory. Per-tool git plumbing stays local
# (boundary), but the *policy* of what counts as changed is shared.
try:
    from governor.completion_gate import (  # noqa: E402
        changed_files_via_git as _shared_changed_files,
    )

    _CHANGED_FILES_OK = True
except Exception as exc:  # noqa: BLE001 — fail-open import
    debug_log("antigravity shared changed-files import failed", exc)
    _shared_changed_files = None  # type: ignore[assignment]
    _CHANGED_FILES_OK = False


def load_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        debug_log("antigravity hook payload parse failed", exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def changed_files() -> list[str]:
    if _CHANGED_FILES_OK and _shared_changed_files is not None:
        try:
            return _shared_changed_files()
        except Exception as exc:  # noqa: BLE001 — execution fail-open
            debug_log("antigravity shared changed-files execution failed", exc)
    # Fallback when the shared module is unavailable or raises: uncommitted +
    # untracked only (no recent-commit fallback). sorted() for stable ordering.
    tracked = run_command(["git", "diff", "--name-only", "HEAD"])
    untracked = run_command(["git", "ls-files", "--others", "--exclude-standard"])
    return sorted(
        {
            line
            for chunk in (tracked.stdout, untracked.stdout)
            for line in chunk.splitlines()
            if line
        }
    )


def tool_name(payload: dict[str, Any]) -> str:
    for key in ("tool_name", "toolName", "tool", "name"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("tool_input", "toolInput", "input", "args", "arguments"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def command_from_payload(payload: dict[str, Any]) -> str:
    inp = tool_input(payload)
    for key in ("command", "cmd", "shell_command"):
        value = inp.get(key)
        if isinstance(value, str):
            return value
    for key in ("command", "cmd", "shell_command"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def extract_python_paths(command: str) -> list[Path]:
    matches = re.findall(r"([A-Za-z0-9_./-]+\.py)\b", command)
    paths: list[Path] = []
    for match in matches:
        # Resolve BOTH branches (relative AND absolute) before the confinement
        # check. ``Path.relative_to`` is purely lexical and does not collapse
        # ``..``, so an absolute path like ``<repo>/../outside.py`` would pass
        # the check unresolved and let ruff mutate a file outside the workspace.
        candidate = (
            Path(match) if match.startswith("/") else REPO_ROOT / match
        ).resolve()
        try:
            candidate.relative_to(REPO_ROOT)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            paths.append(candidate)
    return list(dict.fromkeys(paths))


def session_env_id() -> str | None:
    for key in (
        "ANTIGRAVITY_SESSION_ID",
        "GEMINI_SESSION_ID",
        "GEMINI_CLI_SESSION_ID",
        "AGENT_SESSION_ID",
    ):
        value = os.environ.get(key)
        if value:
            return value
    return None
