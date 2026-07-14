from __future__ import annotations

import contextlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

from _shared import (
    REPO_ROOT,
    command_from_payload,
    extract_python_paths,
    load_payload,
    tool_input,
    tool_name,
)


def _format_python_paths(command: str) -> None:
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


def _coerce_code(value: object) -> int | None:
    """An int/str exit code, or None. Bools are not codes (handled via
    ``success``), so they return None here."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _error_message(err: object) -> str:
    if isinstance(err, str):
        return err
    if isinstance(err, dict):
        msg = err.get("message")
        return msg if isinstance(msg, str) else ""
    return ""


_META_LINE = re.compile(
    r"Exit Code:\s*\d+|Signal:\s*\S+|Background PIDs:.*|Process Group PGID:.*|Error:.*"
)


def _shell_text_outcome(text: str) -> int | None:
    """Classify a gemini-cli shell ``llmContent`` / ``returnDisplay`` into a
    verify verdict, keyed on ONE structural invariant of the shell tool: a
    command that COMPLETED in the foreground begins with ``Output:`` (then any
    trailing metadata); anything else is a status message (``Command was
    cancelled …`` / ``… automatically cancelled …`` / ``Command moved to
    background …`` / ``Command is running in background …`` / ``Background
    process started …`` / ``Command injection detected …``). Keying on the
    leading form — not a substring scan — means a command's own stdout cannot
    spoof the verdict, and new status-message wordings do not need enumerating.

      * completed (``Output:``) -> read the trailing metadata block: a
        ``Signal:`` line or ``Error:`` line -> failure (1); the bottom-most
        ``Exit Code: N`` line -> N (emitted only on a non-zero exit; a spurious
        stdout copy is shadowed by the real trailing one); otherwise -> 0;
      * blocked (command never ran) -> failure (1);
      * any other status (cancelled / timed out / backgrounded / running) or
        unrecognised text -> None (no verify verdict).
    """
    stripped = text.strip()
    if not stripped.startswith("Output:"):
        if "Command injection detected" in stripped or stripped.startswith("Blocked:"):
            return 1
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Locate the metadata block: the last contiguous run of metadata lines,
    # skipping any trailing NON-metadata suffix the runtime may append after it
    # — e.g. the "[System] Tool input parameters (...) were modified by a hook
    # before execution." note added when a BeforeTool hook rewrites the input,
    # which otherwise pushes the real Exit Code / Background PIDs out of view.
    idx = len(lines) - 1
    while idx >= 0 and not _META_LINE.fullmatch(lines[idx]):
        idx -= 1
    trailing: list[str] = []
    while idx >= 0 and _META_LINE.fullmatch(lines[idx]):
        trailing.append(lines[idx])
        idx -= 1
    if any(re.fullmatch(r"Signal:\s*\S+", line) for line in trailing):
        return 1
    # A real metadata "Exit Code:" line is emitted ONLY on a non-zero exit, so
    # a *non-zero* code is authoritative (bottom-most wins). A trailing
    # "Exit Code: 0" is a spurious stdout echo (success omits the line) and is
    # ignored, so it cannot override the incomplete-background check below.
    for line in trailing:  # end->start order, so the first hit is bottom-most
        match = re.fullmatch(r"Exit Code:\s*(\d+)", line)
        if match and int(match.group(1)) != 0:
            return int(match.group(1))
    if any(line.startswith("Error:") for line in trailing):
        return 1
    # Unwaited background processes outlived the foreground command — the work
    # (e.g. `pytest ... &`) may still be running, so record no verify verdict.
    if any(line.startswith("Background PIDs:") for line in trailing):
        return None
    return 0


def _extract_exit_code(payload: dict) -> int | None:
    # 1. Explicit top-level codes (non-Gemini runtimes).
    for value in (payload.get("exit_code"), payload.get("returncode")):
        code = _coerce_code(value)
        if code is not None:
            return code
    for key in ("tool_response", "tool_output", "result", "response"):
        response = payload.get(key)
        if not isinstance(response, dict):
            continue
        error = response.get("error")
        error_msg = _error_message(error).lower()
        # 2. Cancellation via the error envelope ("Operation cancelled by
        #    user.", aborted) FIRST — not a verify failure, so skip the verdict.
        #    Anchored to error.message (not a stdout scan) so a failing test
        #    whose output merely contains "cancelled" is not misread.
        if error and ("cancel" in error_msg or "abort" in error_msg):
            return None
        # 3. Structured fields, if a runtime ever forwards them (the current
        #    AfterTool bridge drops `data`; kept for forward/back-compat).
        data = response.get("data")
        if isinstance(data, dict):
            code = _coerce_code(data.get("exitCode"))
            if code is not None:
                return code
            if data.get("isError"):
                return 1
        for value in (
            response.get("exit_code"),
            response.get("returncode"),
            response.get("status"),
        ):
            code = _coerce_code(value)
            if code is not None:
                return code
        success = response.get("success")
        if isinstance(success, bool):
            return 0 if success else 1
        # 4. A non-cancellation execution error (e.g. spawn ENOENT) -> failure.
        if error:
            return 1
        # 5. Foreground-shell text (the real Gemini success/failure contract).
        #    llmContent is authoritative and its verdict is FINAL (incl. None
        #    for an incomplete/cancelled/backgrounded command) — do NOT fall
        #    through to returnDisplay, which could turn a genuine "incomplete"
        #    into a spurious success. returnDisplay is consulted only when
        #    llmContent is absent/empty.
        for text in (response.get("llmContent"), response.get("returnDisplay")):
            if isinstance(text, str) and text.strip():
                return _shell_text_outcome(text)
    return None


def _record_verify_class(command: str, payload: dict) -> None:
    from verify_first import append_verify_log  # noqa: PLC0415

    if append_verify_log(command) is None:
        return
    exit_code = _extract_exit_code(payload)
    if exit_code is None:
        return
    shared = Path(__file__).resolve().parents[2] / ".agents" / "shared"
    if str(shared) not in sys.path:
        sys.path.insert(0, str(shared))
    with contextlib.suppress(Exception):
        from work_ledger import mark_verified  # noqa: PLC0415

        mark_verified(command, passed=exit_code == 0)


def _native_edit_path(payload: dict) -> str | None:
    """The edited file path for a native ``replace`` / ``write_file`` edit
    (Gemini/Antigravity's primary edit path). Unlike a shell command, these
    carry the path in ``tool_input.file_path`` — the same field the BeforeTool
    security hook reads."""
    if tool_name(payload) not in {"replace", "write_file", "Edit", "Write"}:
        return None
    inp = tool_input(payload)
    path = inp.get("file_path") or inp.get("path") or inp.get("filePath")
    return path if isinstance(path, str) and path.endswith(".py") else None


def main() -> int:
    try:
        payload = load_payload()
        command = command_from_payload(payload)
        if command:
            with contextlib.suppress(Exception):
                _format_python_paths(command)
            with contextlib.suppress(Exception):
                _record_verify_class(command, payload)
            return 0
        # Native file edit (replace/write_file): format the edited .py file.
        # extract_python_paths (via _format_python_paths) confines the path to
        # the repo and checks existence, so a stray path cannot escape.
        native = _native_edit_path(payload)
        if native:
            with contextlib.suppress(Exception):
                _format_python_paths(native)
    except Exception:  # noqa: BLE001
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
