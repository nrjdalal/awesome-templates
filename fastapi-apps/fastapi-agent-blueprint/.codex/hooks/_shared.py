from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SHARED_PKG = REPO_ROOT / ".agents" / "shared"
if str(_SHARED_PKG) not in sys.path:
    sys.path.insert(0, str(_SHARED_PKG))

try:
    from harness_debug import debug_log  # noqa: E402
except Exception:  # noqa: BLE001

    def debug_log(event: str, exc: BaseException | None = None) -> None:
        return


try:
    from governor.completion_gate import (  # noqa: E402 — sys.path adjusted above
        changed_files_via_git as _impl,
    )

    _GATE_OK = True
except Exception as exc:  # noqa: BLE001 — HC-5.5 fail-open
    debug_log("codex shared changed-files import failed", exc)
    _impl = None  # type: ignore[assignment]
    _GATE_OK = False


def load_payload() -> dict:
    return json.load(__import__("sys").stdin)


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def changed_files() -> list[str]:
    if _GATE_OK and _impl is not None:
        try:
            return _impl()
        except Exception as exc:  # noqa: BLE001 — HC-5.5: execution fail-open, fall through
            debug_log("codex shared changed-files execution failed", exc)
            pass
    # Fallback when governor module is unavailable or _impl() raises (HC-5.5).
    # sorted() applied for consistent ordering with changed_files_via_git().
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
