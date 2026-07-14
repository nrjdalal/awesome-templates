"""Regression tests for the Antigravity harness hardening (PR #285 review round 2/3).

Covers the codex cross-review findings fixed in this cycle:
- F1  path-traversal confinement in ``extract_python_paths`` (BLOCKING)
- F5  real Gemini ``tool_response`` shape parsing in ``post-tool-format``
- F4  ADR 054 plan->execute gate wired into the AfterAgent adapter
- F6  native ``write_file`` / ``replace`` edits are formatted

The Antigravity hooks import a bare ``_shared`` module whose name collides with
the Claude / Codex ``_shared`` modules other tests load. In-process imports here
run inside ``_antigravity_import_env`` (restores ``sys.modules`` + ``sys.path``)
or under unique module names, so this file cannot shadow the ``_shared`` other
suites resolve (which previously broke test_completion_gate).
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS = REPO_ROOT / ".antigravity" / "hooks"
SHARED = REPO_ROOT / ".agents" / "shared"
_COLLIDING_MODULES = ("_shared", "harness_debug", "antigravity_post_tool_format")


@contextlib.contextmanager
def _antigravity_import_env() -> Iterator[None]:
    saved_modules = {name: sys.modules.get(name) for name in _COLLIDING_MODULES}
    saved_path = list(sys.path)
    # Front-insert the Antigravity hook dir and drop any cached colliding
    # modules so ``from _shared import ...`` resolves to the Antigravity copy
    # rather than a Claude/Codex ``_shared`` a prior test left in sys.modules.
    for path in (str(HOOKS), str(SHARED)):
        sys.path.insert(0, path)
    for name in _COLLIDING_MODULES:
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        sys.path[:] = saved_path
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _load_module(unique_name: str, file_path: Path):
    """Load a hook module under a unique name (no ``_shared`` collision)."""
    spec = importlib.util.spec_from_file_location(unique_name, file_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# F1 — path traversal confinement (must be red on the pre-fix implementation)
# ---------------------------------------------------------------------------
def test_extract_python_paths_confines_to_repo(tmp_path: Path) -> None:
    fake_repo = (tmp_path / "repo").resolve()
    fake_repo.mkdir()
    (fake_repo / "inside.py").write_text("x = 1\n", encoding="utf-8")
    # A real file that EXISTS outside the fake repo, placed exactly where the
    # `..` escape resolves (fake_repo.parent) so the check is symlink-safe. The
    # pre-fix code returned it because relative_to() is lexical and .exists()
    # collapses the '..'; the fix resolve()s first, so it is now rejected.
    (fake_repo.parent / "outside.py").write_text("x = 1\n", encoding="utf-8")

    for name, rel in (
        ("ag_shared_f1", ".antigravity/hooks/_shared.py"),
        ("cx_shared_f1", ".codex/hooks/_shared.py"),
    ):
        module = _load_module(name, REPO_ROOT / rel)
        module.REPO_ROOT = fake_repo  # patch the confinement root

        escaped = module.extract_python_paths(f"cat {fake_repo}/../outside.py")
        assert escaped == [], f"{name} leaked an out-of-repo path: {escaped}"

        found = module.extract_python_paths(f"python {fake_repo}/inside.py")
        assert [p.name for p in found] == ["inside.py"], f"{name} lost the in-repo file"


# ---------------------------------------------------------------------------
# F5 — real Gemini AfterTool tool_response contract
# ---------------------------------------------------------------------------
def test_extract_exit_code_matches_real_gemini_contract() -> None:
    with _antigravity_import_env():
        extract = _load_module(
            "antigravity_post_tool_format", HOOKS / "post-tool-format.py"
        )._extract_exit_code

    # Success: a foreground shell emits NO "Exit Code:" line and no `data`.
    assert extract({"tool_response": {"llmContent": "Output: 1 passed in 0.1s"}}) == 0
    # Failure via structured data (the real non-zero shape).
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: boom\nExit Code: 2",
                    "data": {"exitCode": 2, "isError": True},
                }
            }
        )
        == 2
    )
    # Failure via a standalone text "Exit Code:" metadata line.
    assert extract({"tool_response": {"llmContent": "Output: boom\nExit Code: 1"}}) == 1
    # An error object outranks a stray "Exit Code: 0" embedded in command output.
    assert (
        extract(
            {"tool_response": {"llmContent": "Output: Exit Code: 0", "error": {"m": 1}}}
        )
        == 1
    )
    # Output-embedded "Exit Code: 0" (not a metadata line) is NOT a failure — the
    # command succeeded, so the result is 0.
    assert extract({"tool_response": {"llmContent": "Output: Exit Code: 0"}}) == 0
    # Real payload has NO `data`: a command whose stdout prints "Exit Code: 0"
    # must not mask the trailing metadata "Exit Code: 7" — the LAST line wins.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: harmless\nExit Code: 0\nExit Code: 7"
                }
            }
        )
        == 7
    )
    # A real cancellation carries error "Operation cancelled by user." — this is
    # NOT a verify failure, so it must be skipped (None), not recorded as 1.
    assert (
        extract(
            {
                "tool_response": {
                    "error": {"message": "Operation cancelled by user."},
                    "llmContent": "Output: partial",
                }
            }
        )
        is None
    )
    # Signal termination: a trailing "Signal:" line is a failure even when the
    # command's stdout printed a spurious "Exit Code: 0" (signal exit is null).
    assert (
        extract(
            {"tool_response": {"llmContent": "Output: x\nExit Code: 0\nSignal: 15"}}
        )
        == 1
    )
    assert extract({"tool_response": {"llmContent": "Output: x\nSignal: 15"}}) == 1
    # Explicit background: the command is still running, so no verdict — even
    # though the initial output contains an "Output:" line.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Command is running in background. PID: 5. "
                    "Initial output:\nOutput: starting"
                }
            }
        )
        is None
    )
    assert (
        extract(
            {"tool_response": {"llmContent": "Background process started with PID 9."}}
        )
        is None
    )
    # A FAILING test whose output merely contains the word "cancelled" is a real
    # failure (Exit Code: 1), not a cancellation — cancel is error-anchored only.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: test_cancelled_job FAILED\nExit Code: 1"
                }
            }
        )
        == 1
    )
    # Command-substitution block: the command never ran, so it is not a pass.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Command injection detected: command substitution "
                    "syntax found in command arguments. ... the command was blocked."
                }
            }
        )
        == 1
    )
    # A trailing "[System] ... modified by a hook" suffix (added when a
    # BeforeTool hook rewrites the input) must not hide the metadata block: the
    # real Exit Code 7 is still read as a failure, and Background PIDs still None.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: failed\nExit Code: 7\nProcess Group PGID: 10"
                    "\n\n[System] Tool input parameters (command) were modified by a "
                    "hook before execution.",
                    "returnDisplay": "failed",
                }
            }
        )
        == 7
    )
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: started\nBackground PIDs: 11\n"
                    "Process Group PGID: 10\n\n[System] Tool input parameters "
                    "(command) were modified by a hook before execution.",
                    "returnDisplay": "started",
                }
            }
        )
        is None
    )
    # Unwaited background processes (e.g. `pytest ... &`) — the foreground shell
    # returned but the work may still be running, so record no verdict (not 0).
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: starting\nBackground PIDs: 55\n"
                    "Process Group PGID: 54"
                }
            }
        )
        is None
    )
    # A spurious stdout "Exit Code: 0" must not override the background-incomplete
    # signal (a real success omits the Exit Code line).
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: x\nExit Code: 0\nBackground PIDs: 55\n"
                    "Process Group PGID: 54"
                }
            }
        )
        is None
    )
    # A genuine non-zero exit still wins over lingering background processes.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Output: x\nExit Code: 7\nBackground PIDs: 55"
                }
            }
        )
        == 7
    )
    # Aborted (error=null) with output appended AFTER the cancel message — must
    # stay None even though the appended stdout has an "Output:" line, and must
    # NOT fall through to a returnDisplay that looks like a success.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Command was cancelled by user before it could "
                    "complete. Below is the output before it was cancelled:\n"
                    "Output: partial\nExit Code: 0",
                    "returnDisplay": "Output: partial",
                }
            }
        )
        is None
    )
    # Inactivity timeout (auto-cancel), same structural shape.
    assert (
        extract(
            {
                "tool_response": {
                    "llmContent": "Command was automatically cancelled because it "
                    "exceeded the timeout of 5.0 minutes without output.\n"
                    "Output: partial",
                    "returnDisplay": "Output: partial",
                }
            }
        )
        is None
    )
    # Cancelled / backgrounded (text-only) -> no verify verdict.
    assert (
        extract({"tool_response": {"llmContent": "Command was cancelled by user."}})
        is None
    )
    assert (
        extract(
            {"tool_response": {"llmContent": "Command moved to background (PID: 5)"}}
        )
        is None
    )
    # Legacy / non-Gemini runtime shape stays supported.
    assert extract({"result": {"exit_code": 0}}) == 0
    assert extract({"result": {"success": False}}) == 1


# ---------------------------------------------------------------------------
# F4 — ADR 054 plan->execute gate wired into the AfterAgent adapter (static)
# ---------------------------------------------------------------------------
def test_stop_sync_reminder_wires_plan_execute_gate() -> None:
    text = (HOOKS / "stop-sync-reminder.py").read_text(encoding="utf-8")
    assert "should_plan_execute_gate" in text
    assert "PLAN_EXECUTE_REMINDER" in text
    assert "def plan_execute_segment" in text
    # Both gates share the once-per-session mark_fired claim.
    assert (
        "stage_gate_segment(changed, sid) or plan_execute_segment(changed, sid)" in text
    )


# ---------------------------------------------------------------------------
# F6 — native write_file / replace edits are formatted (subprocess)
# ---------------------------------------------------------------------------
def test_native_write_file_edit_is_formatted(tmp_path: Path) -> None:
    # Confinement requires an in-repo, existing file. Use an exclusive temp dir
    # under the repo root so parallel runs / same-named files never collide.
    work_dir = Path(tempfile.mkdtemp(dir=REPO_ROOT, prefix=".native_fmt_"))
    try:
        target = work_dir / "edited.py"
        target.write_text("x=1\ny =2\n", encoding="utf-8")
        env = os.environ.copy()
        env["HARNESS_STATE_ROOT"] = str(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(HOOKS / "post-tool-format.py")],
            input=json.dumps(
                {"tool_name": "write_file", "tool_input": {"file_path": str(target)}}
            ),
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        assert proc.returncode == 0
        if shutil.which("ruff") is not None:
            assert target.read_text(encoding="utf-8") == "x = 1\ny = 2\n"
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
