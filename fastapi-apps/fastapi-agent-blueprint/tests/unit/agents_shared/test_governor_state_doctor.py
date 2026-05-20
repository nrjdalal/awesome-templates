"""Unit tests for tools/governor_state_doctor.py (PR-A.1).

Each check function is tested with:
  * a passing fixture (expected ok=True)
  * one or more failure fixtures (expected ok=False)

Integration smoke: ``test_run_all_real_project`` runs all seven checks
against the actual project root and asserts all pass.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Make the tools/ directory importable without installing the package.
# parents[3]: tests/unit/agents_shared → tests/unit → tests → project root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from governor_state_doctor import (  # noqa: E402  # type: ignore[import]
    CheckResult,
    check_gitignore_registered,
    check_hook_command_canaries,
    check_hook_interpreter,
    check_marker_glob_coverage,
    check_no_git_tracked_state,
    check_stale_stats,
    check_stop_hook_schema,
    run_all,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_hooks_json(
    stop_cmd: str = "python3 .codex/hooks/stop-sync-reminder.py",
) -> dict:
    return {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": stop_cmd}]}]}}


def _make_valid_settings_json(
    stop_cmd: str = "bash .claude/hooks/stop-sync-reminder.sh",
) -> dict:
    return {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": stop_cmd}]}]}}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_minimal_marker_files(root: Path) -> None:
    """Create the three files required for C4 to pass."""
    stop_py = root / ".codex" / "hooks" / "stop-sync-reminder.py"
    stop_py.parent.mkdir(parents=True, exist_ok=True)
    stop_py.write_text("consume_phase2_markers(STATE_DIR)", encoding="utf-8")

    markers_py = root / ".agents" / "shared" / "governor" / "markers.py"
    markers_py.parent.mkdir(parents=True, exist_ok=True)
    markers_py.write_text('glob("exception-token-*.json")', encoding="utf-8")

    gate_py = root / ".codex" / "hooks" / "completion_gate.py"
    gate_py.write_text('glob("verify-log-*.json")', encoding="utf-8")


# ---------------------------------------------------------------------------
# C1 — gitignore_registered
# ---------------------------------------------------------------------------


def test_gitignore_registered_pass(tmp_path: Path) -> None:
    gi = tmp_path / ".gitignore"
    gi.write_text(".claude/state/\n.codex/state/\n", encoding="utf-8")
    result = check_gitignore_registered(tmp_path)
    assert result.ok is True
    assert result.name == "C1_gitignore_registered"


def test_gitignore_registered_fail_missing_one(tmp_path: Path) -> None:
    gi = tmp_path / ".gitignore"
    gi.write_text(".claude/state/\n# only one pattern\n", encoding="utf-8")
    result = check_gitignore_registered(tmp_path)
    assert result.ok is False
    assert ".codex/state/" in result.detail


def test_gitignore_registered_fail_no_file(tmp_path: Path) -> None:
    result = check_gitignore_registered(tmp_path)
    assert result.ok is False
    assert ".gitignore" in result.detail


def test_gitignore_registered_fail_empty(tmp_path: Path) -> None:
    gi = tmp_path / ".gitignore"
    gi.write_text("", encoding="utf-8")
    result = check_gitignore_registered(tmp_path)
    assert result.ok is False
    assert len(result.data.get("missing", [])) == 2


# ---------------------------------------------------------------------------
# C2 — no_git_tracked_state
# ---------------------------------------------------------------------------


def test_no_git_tracked_state_pass(tmp_path: Path) -> None:
    with patch("governor_state_doctor.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        result = check_no_git_tracked_state(tmp_path)
    assert result.ok is True


def test_no_git_tracked_state_fail_tracked(tmp_path: Path) -> None:
    with patch("governor_state_doctor.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ".claude/state/exception-token-foo.json\n"
        mock_run.return_value.returncode = 0
        result = check_no_git_tracked_state(tmp_path)
    assert result.ok is False
    assert "tracked" in result.detail.lower()
    assert len(result.data["tracked_files"]) == 1


def test_no_git_tracked_state_fail_command_not_found(tmp_path: Path) -> None:
    with patch(
        "governor_state_doctor.subprocess.run",
        side_effect=FileNotFoundError("git not found"),
    ):
        result = check_no_git_tracked_state(tmp_path)
    assert result.ok is False


# ---------------------------------------------------------------------------
# C3 — stop_hook_schema
# ---------------------------------------------------------------------------


def test_stop_hook_schema_pass(tmp_path: Path) -> None:
    _write_json(tmp_path / ".codex" / "hooks.json", _make_valid_hooks_json())
    _write_json(tmp_path / ".claude" / "settings.json", _make_valid_settings_json())
    result = check_stop_hook_schema(tmp_path)
    assert result.ok is True


def test_stop_hook_schema_fail_no_stop_entry(tmp_path: Path) -> None:
    _write_json(tmp_path / ".codex" / "hooks.json", {"hooks": {"SessionStart": []}})
    _write_json(tmp_path / ".claude" / "settings.json", _make_valid_settings_json())
    result = check_stop_hook_schema(tmp_path)
    assert result.ok is False
    assert "no Stop entry" in result.detail


def test_stop_hook_schema_fail_wrong_type(tmp_path: Path) -> None:
    bad = {"hooks": {"Stop": [{"hooks": [{"type": "script", "command": "stop.py"}]}]}}
    _write_json(tmp_path / ".codex" / "hooks.json", bad)
    _write_json(tmp_path / ".claude" / "settings.json", _make_valid_settings_json())
    result = check_stop_hook_schema(tmp_path)
    assert result.ok is False
    assert "not 'command'" in result.detail or "command" in result.detail


def test_stop_hook_schema_fail_empty_command(tmp_path: Path) -> None:
    bad = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": ""}]}]}}
    _write_json(tmp_path / ".codex" / "hooks.json", bad)
    _write_json(tmp_path / ".claude" / "settings.json", _make_valid_settings_json())
    result = check_stop_hook_schema(tmp_path)
    assert result.ok is False


def test_stop_hook_schema_fail_missing_file(tmp_path: Path) -> None:
    _write_json(tmp_path / ".claude" / "settings.json", _make_valid_settings_json())
    # .codex/hooks.json intentionally absent
    result = check_stop_hook_schema(tmp_path)
    assert result.ok is False
    assert "hooks.json not found" in result.detail


def test_stop_hook_schema_fail_invalid_json(tmp_path: Path) -> None:
    codex_hooks = tmp_path / ".codex" / "hooks.json"
    codex_hooks.parent.mkdir(parents=True)
    codex_hooks.write_text("{not valid json", encoding="utf-8")
    _write_json(tmp_path / ".claude" / "settings.json", _make_valid_settings_json())
    result = check_stop_hook_schema(tmp_path)
    assert result.ok is False


# ---------------------------------------------------------------------------
# C4 — marker_glob_coverage
# ---------------------------------------------------------------------------


def test_marker_glob_coverage_pass(tmp_path: Path) -> None:
    _make_minimal_marker_files(tmp_path)
    result = check_marker_glob_coverage(tmp_path)
    assert result.ok is True


def test_marker_glob_coverage_fail_no_consume(tmp_path: Path) -> None:
    _make_minimal_marker_files(tmp_path)
    # overwrite stop hook without consume_phase2_markers
    stop_py = tmp_path / ".codex" / "hooks" / "stop-sync-reminder.py"
    stop_py.write_text("# no marker cleanup here", encoding="utf-8")
    result = check_marker_glob_coverage(tmp_path)
    assert result.ok is False
    assert "consume_phase2_markers" in result.detail


def test_marker_glob_coverage_fail_no_exception_token_glob(tmp_path: Path) -> None:
    _make_minimal_marker_files(tmp_path)
    markers_py = tmp_path / ".agents" / "shared" / "governor" / "markers.py"
    markers_py.write_text("# no glob here", encoding="utf-8")
    result = check_marker_glob_coverage(tmp_path)
    assert result.ok is False
    assert "exception-token-*.json" in result.detail


def test_marker_glob_coverage_fail_no_verify_log_glob(tmp_path: Path) -> None:
    _make_minimal_marker_files(tmp_path)
    gate_py = tmp_path / ".codex" / "hooks" / "completion_gate.py"
    gate_py.write_text("# no verify-log glob", encoding="utf-8")
    result = check_marker_glob_coverage(tmp_path)
    assert result.ok is False
    assert "verify-log-*.json" in result.detail


# ---------------------------------------------------------------------------
# C5 — hook_interpreter
# ---------------------------------------------------------------------------


def test_hook_interpreter_fail_missing_hook_file(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".codex" / "hooks.json",
        _make_valid_hooks_json("python3 .codex/hooks/nonexistent.py"),
    )
    _write_json(tmp_path / ".claude" / "settings.json", _make_valid_settings_json())
    # Stop .py for governor import check — make it missing too
    result = check_hook_interpreter(tmp_path)
    assert result.ok is False
    assert "not found" in result.detail.lower()


def test_hook_interpreter_fail_sh_no_exec_bit(tmp_path: Path) -> None:
    # Create a .sh hook without exec bit
    sh_path = tmp_path / ".claude" / "hooks" / "stop-sync-reminder.sh"
    sh_path.parent.mkdir(parents=True, exist_ok=True)
    sh_path.write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
    sh_path.chmod(0o644)  # no exec bit

    _write_json(
        tmp_path / ".codex" / "hooks.json",
        _make_valid_hooks_json("python3 .codex/hooks/stop-sync-reminder.py"),
    )
    _write_json(
        tmp_path / ".claude" / "settings.json",
        _make_valid_settings_json(f"bash {sh_path.relative_to(tmp_path)}"),
    )
    # Create stub stop .py so existence check passes
    stop_py = tmp_path / ".codex" / "hooks" / "stop-sync-reminder.py"
    stop_py.parent.mkdir(parents=True, exist_ok=True)
    stop_py.write_text("", encoding="utf-8")

    result = check_hook_interpreter(tmp_path)
    assert result.ok is False
    assert "exec bit" in result.detail


# ---------------------------------------------------------------------------
# C6 — stale_stats
# ---------------------------------------------------------------------------


def test_stale_stats_no_dirs(tmp_path: Path) -> None:
    result = check_stale_stats(tmp_path)
    assert result.ok is True  # informational — never fails
    assert result.data["total_stale"] == 0


def test_stale_stats_with_stale_markers(tmp_path: Path) -> None:
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True)

    # Write two stale markers (mtime set 48h ago)
    stale_ts = time.time() - (48 * 3600)
    for i in range(2):
        marker = state_dir / f"exception-token-20260101T000000-{i:012d}.json"
        marker.write_text('{"matched": true, "token": "trivial"}', encoding="utf-8")
        os.utime(marker, (stale_ts, stale_ts))

    # Write one fresh marker
    fresh = state_dir / "exception-token-20260101T000001-fresh000001.json"
    fresh.write_text('{"matched": true, "token": "trivial"}', encoding="utf-8")

    result = check_stale_stats(tmp_path)
    assert result.ok is True
    assert result.data["total_stale"] == 2

    dir_stats = result.data["state_dirs"][".claude/state"]
    assert dir_stats["exception_token"]["total"] == 3
    assert dir_stats["exception_token"]["stale"] == 2


def test_stale_stats_verify_log_counted(tmp_path: Path) -> None:
    state_dir = tmp_path / ".codex" / "state"
    state_dir.mkdir(parents=True)

    stale_ts = time.time() - (48 * 3600)
    vlog = state_dir / "verify-log-oldsession.json"
    vlog.write_text("{}", encoding="utf-8")
    os.utime(vlog, (stale_ts, stale_ts))

    result = check_stale_stats(tmp_path)
    assert result.data["state_dirs"][".codex/state"]["verify_log"]["stale"] == 1
    assert result.data["total_stale"] == 1


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------


def test_run_all_returns_seven_results() -> None:
    with patch("governor_state_doctor.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        results = run_all(_REPO_ROOT)
    assert len(results) == 7
    assert all(isinstance(r, CheckResult) for r in results)


def test_run_all_names_are_unique() -> None:
    with patch("governor_state_doctor.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        results = run_all(_REPO_ROOT)
    names = [r.name for r in results]
    assert len(names) == len(set(names)), "Duplicate check names"


def test_run_all_real_project_all_pass() -> None:
    """Integration smoke: all seven checks must pass on the real project."""
    results = run_all(_REPO_ROOT)
    failures = [f"{r.name}: {r.detail}" for r in results if not r.ok]
    assert not failures, "Doctor found issues:\n" + "\n".join(failures)


def test_c5_governor_markers_real_import() -> None:
    """C5 launcher import: governor.markers must be importable via PYTHONPATH.

    This test is NOT mocked so it exercises the real launcher path that
    check_hook_interpreter validates. A broken governor package or wrong
    PYTHONPATH setup will cause this test (not just the mocked run_all) to fail.
    """
    shared = _REPO_ROOT / ".agents" / "shared"
    launcher = shared / "harness-python.sh"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(shared)
    env["HARNESS_LAUNCHER_STRICT"] = "1"
    import_code = "from governor.markers import consume_phase2_markers; print('ok')"
    proc = subprocess.run(
        ["sh", str(launcher), "-c", import_code],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, (
        f"governor.markers import failed via PYTHONPATH={shared}:\n{proc.stderr}"
    )
    assert "ok" in proc.stdout


def test_c6_hook_command_canaries_real_state_unchanged() -> None:
    before = {
        path: path.stat().st_mtime_ns
        for rel in (".codex/state", ".claude/state", ".agents/state")
        for path in (_REPO_ROOT / rel).rglob("*")
        if (_REPO_ROOT / rel).exists() and path.is_file()
    }
    result = check_hook_command_canaries(_REPO_ROOT)
    after = {
        path: path.stat().st_mtime_ns
        for rel in (".codex/state", ".claude/state", ".agents/state")
        for path in (_REPO_ROOT / rel).rglob("*")
        if (_REPO_ROOT / rel).exists() and path.is_file()
    }
    assert result.ok is True, result.detail
    assert before == after
