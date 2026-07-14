#!/usr/bin/env python3
"""Standalone diagnostic CLI for governor state lifecycle health.

Seven checks:

    C1  gitignore_registered  — tool state dirs in .gitignore
    C2  no_git_tracked_state  — no state/*.json files tracked by git
    C3  stop_hook_schema      — session-end hook entries are valid
    C4  marker_glob_coverage  — Stop hooks reference all known marker globs
    C5  hook_interpreter      — Hook files exist; .sh exec bit; launcher imports governor
    C6  hook_command_canaries — Runs configured hook commands in isolated state
    C7  stale_stats           — Counts stale (>24 h) markers in tool state dirs

Usage:
    python3 tools/governor_state_doctor.py [--json]

    --json  (default) emit results as a single JSON object to stdout
    --text  human-readable summary to stdout

Exit codes:
    0 — all seven checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SCRIPT_DIR.parent  # tools/ is one level below root


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# C1 — .gitignore registration
# ---------------------------------------------------------------------------

_REQUIRED_GITIGNORE_PATTERNS = (
    ".claude/state/",
    ".codex/state/",
    ".antigravity/state/",
)


def check_gitignore_registered(root: Path = PROJECT_ROOT) -> CheckResult:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return CheckResult("C1_gitignore_registered", False, ".gitignore not found")

    text = gitignore.read_text(encoding="utf-8")
    missing = [p for p in _REQUIRED_GITIGNORE_PATTERNS if p not in text]
    if missing:
        return CheckResult(
            "C1_gitignore_registered",
            False,
            f"Missing gitignore patterns: {missing}",
            {"missing": missing},
        )
    return CheckResult(
        "C1_gitignore_registered",
        True,
        "All tool state/ patterns present in .gitignore",
    )


# ---------------------------------------------------------------------------
# C2 — no state files tracked by git
# ---------------------------------------------------------------------------


def check_no_git_tracked_state(root: Path = PROJECT_ROOT) -> CheckResult:
    try:
        result = subprocess.run(
            [
                "git",
                "ls-files",
                ".claude/state/",
                ".codex/state/",
                ".antigravity/state/",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            "C2_no_git_tracked_state",
            False,
            f"git ls-files failed: {exc}",
        )
    tracked = result.stdout.strip()
    if tracked:
        files = tracked.splitlines()
        return CheckResult(
            "C2_no_git_tracked_state",
            False,
            f"{len(files)} state file(s) tracked by git",
            {"tracked_files": files},
        )
    return CheckResult(
        "C2_no_git_tracked_state",
        True,
        "No state files tracked by git",
    )


# ---------------------------------------------------------------------------
# C3 — Stop hook entry schema
# ---------------------------------------------------------------------------


def _validate_event_entries(
    config: dict,
    label: str,
    event_name: str,
) -> list[str]:
    """Return a list of issues found in a hooks config dict."""
    issues: list[str] = []
    event_blocks = config.get("hooks", {}).get(event_name, [])
    if not event_blocks:
        issues.append(f"{label}: no {event_name} entry found")
        return issues
    for event_block in event_blocks:
        for hook in event_block.get("hooks", []):
            if hook.get("type") != "command":
                issues.append(
                    f"{label}: {event_name} hook type is not 'command': {hook.get('type')!r}"
                )
            cmd = hook.get("command", "").strip()
            if not cmd:
                issues.append(f"{label}: {event_name} hook has empty command")
    return issues


def check_stop_hook_schema(root: Path = PROJECT_ROOT) -> CheckResult:
    issues: list[str] = []

    codex_hooks_json = root / ".codex" / "hooks.json"
    if not codex_hooks_json.exists():
        issues.append(".codex/hooks.json not found")
    else:
        try:
            data = json.loads(codex_hooks_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(f".codex/hooks.json JSON parse error: {exc}")
            data = {}
        issues.extend(_validate_event_entries(data, "Codex hooks.json", "Stop"))

    claude_settings = root / ".claude" / "settings.json"
    if not claude_settings.exists():
        issues.append(".claude/settings.json not found")
    else:
        try:
            data = json.loads(claude_settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(f".claude/settings.json JSON parse error: {exc}")
            data = {}
        issues.extend(_validate_event_entries(data, "Claude settings.json", "Stop"))

    gemini_settings = root / ".gemini" / "settings.json"
    if not gemini_settings.exists():
        issues.append(".gemini/settings.json not found")
    else:
        try:
            data = json.loads(gemini_settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(f".gemini/settings.json JSON parse error: {exc}")
            data = {}
        issues.extend(
            _validate_event_entries(data, "Gemini settings.json", "AfterAgent")
        )

    if issues:
        return CheckResult(
            "C3_stop_hook_schema",
            False,
            "; ".join(issues),
            {"issues": issues},
        )
    return CheckResult(
        "C3_stop_hook_schema",
        True,
        "Session-end hook entries valid in Codex, Claude, and Gemini settings",
    )


# ---------------------------------------------------------------------------
# C4 — marker glob coverage
# ---------------------------------------------------------------------------


def check_marker_glob_coverage(root: Path = PROJECT_ROOT) -> CheckResult:
    issues: list[str] = []

    # Codex Stop hook must call consume_phase2_markers
    codex_stop = root / ".codex" / "hooks" / "stop-sync-reminder.py"
    if not codex_stop.exists():
        issues.append(".codex/hooks/stop-sync-reminder.py not found")
    else:
        if "consume_phase2_markers" not in codex_stop.read_text(encoding="utf-8"):
            issues.append(
                ".codex/hooks/stop-sync-reminder.py: consume_phase2_markers not referenced"
            )

    antigravity_stop = root / ".antigravity" / "hooks" / "stop-sync-reminder.py"
    if not antigravity_stop.exists():
        issues.append(".antigravity/hooks/stop-sync-reminder.py not found")
    else:
        if "consume_phase2_markers" not in antigravity_stop.read_text(encoding="utf-8"):
            issues.append(
                ".antigravity/hooks/stop-sync-reminder.py: consume_phase2_markers not referenced"
            )

    # governor/markers.py must define the exception-token glob
    markers_py = root / ".agents" / "shared" / "governor" / "markers.py"
    if not markers_py.exists():
        issues.append(".agents/shared/governor/markers.py not found")
    else:
        text = markers_py.read_text(encoding="utf-8")
        if "exception-token-*.json" not in text:
            issues.append(
                "governor/markers.py: exception-token-*.json glob pattern not found"
            )

    # completion_gate.py must define the verify-log glob
    gate_py = root / ".codex" / "hooks" / "completion_gate.py"
    if not gate_py.exists():
        issues.append(".codex/hooks/completion_gate.py not found")
    else:
        if "verify-log-*.json" not in gate_py.read_text(encoding="utf-8"):
            issues.append(
                ".codex/hooks/completion_gate.py: verify-log-*.json glob pattern not found"
            )

    antigravity_gate_py = root / ".antigravity" / "hooks" / "completion_gate.py"
    if not antigravity_gate_py.exists():
        issues.append(".antigravity/hooks/completion_gate.py not found")
    else:
        if "verify-log-*.json" not in antigravity_gate_py.read_text(encoding="utf-8"):
            issues.append(
                ".antigravity/hooks/completion_gate.py: verify-log-*.json glob pattern not found"
            )

    if issues:
        return CheckResult(
            "C4_marker_glob_coverage",
            False,
            "; ".join(issues),
            {"issues": issues},
        )
    return CheckResult(
        "C4_marker_glob_coverage",
        True,
        "All expected marker glob patterns present",
    )


# ---------------------------------------------------------------------------
# C5 — hook file existence, .sh exec bit, launcher governor import
# ---------------------------------------------------------------------------


def _collect_hook_commands(root: Path) -> list[str]:
    """Return all hook command strings from hooks.json and settings.json."""
    commands: list[str] = []

    for cfg_path in (
        root / ".codex" / "hooks.json",
        root / ".claude" / "settings.json",
        root / ".gemini" / "settings.json",
    ):
        if not cfg_path.exists():
            continue
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for event_blocks in data.get("hooks", {}).values():
            for block in event_blocks:
                for hook in block.get("hooks", []):
                    cmd = hook.get("command", "").strip()
                    if cmd:
                        commands.append(cmd)
    return commands


def check_hook_interpreter(root: Path = PROJECT_ROOT) -> CheckResult:
    issues: list[str] = []

    commands = _collect_hook_commands(root)
    for cmd in commands:
        parts = cmd.split()
        if not parts:
            continue
        # Use the last token as the hook file path. For simple commands like
        # "bash script.sh" or "python3 hook.py" this is always correct.
        # Complex forms (e.g. "bash -c '...'") are not used in this repo's
        # hooks.json, so the last-token heuristic is sufficient here.
        hook_rel = parts[-1]

        hook_path = (
            (root / hook_rel).resolve()
            if not hook_rel.startswith("/")
            else Path(hook_rel)
        )
        if not hook_path.exists():
            issues.append(f"Hook file not found: {hook_rel}")
            continue

        # .sh files must have exec bit
        if hook_path.suffix == ".sh":
            mode = hook_path.stat().st_mode
            if not (mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                issues.append(f"{hook_rel}: .sh hook missing exec bit")

    # Import check: verify the configured launcher can import governor.markers.
    # PYTHONPATH is set to .agents/shared so the subprocess can resolve governor.*
    # without an f-string path injection.
    stop_py = root / ".codex" / "hooks" / "stop-sync-reminder.py"
    if stop_py.exists():
        shared = root / ".agents" / "shared"
        launcher = root / ".agents" / "shared" / "harness-python.sh"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(shared)
        env["HARNESS_LAUNCHER_STRICT"] = "1"
        import_code = "from governor.markers import consume_phase2_markers; print('ok')"
        try:
            proc = subprocess.run(  # noqa: S603
                ["sh", str(launcher), "-c", import_code],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            if proc.returncode != 0 or "ok" not in proc.stdout:
                issues.append(
                    "launcher governor.markers import failed: "
                    f"{proc.stderr.strip()[:200]}"
                )
        except subprocess.TimeoutExpired:
            issues.append("launcher governor.markers import check timed out")
    else:
        issues.append(
            ".codex/hooks/stop-sync-reminder.py not found (skip import check)"
        )

    if issues:
        return CheckResult(
            "C5_hook_interpreter",
            False,
            "; ".join(issues),
            {"issues": issues},
        )
    return CheckResult(
        "C5_hook_interpreter",
        True,
        "All hook files exist; .sh exec bits OK; launcher imports governor.markers",
    )


# ---------------------------------------------------------------------------
# C6 — configured hook command canaries with isolated state
# ---------------------------------------------------------------------------

_STATE_SNAPSHOT_DIRS = (
    Path(".claude/state"),
    Path(".codex/state"),
    Path(".antigravity/state"),
    Path(".agents/state"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_real_state(root: Path) -> dict[str, tuple[int, int, str]]:
    snapshot: dict[str, tuple[int, int, str]] = {}
    for rel_dir in _STATE_SNAPSHOT_DIRS:
        base = root / rel_dir
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            stat_result = path.stat()
            snapshot[str(path.relative_to(root))] = (
                stat_result.st_size,
                stat_result.st_mtime_ns,
                _sha256(path),
            )
    return snapshot


def _first_codex_command(root: Path, event_name: str) -> str | None:
    hooks_json = root / ".codex" / "hooks.json"
    try:
        data = json.loads(hooks_json.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    for block in data.get("hooks", {}).get(event_name, []):
        for hook in block.get("hooks", []):
            command = hook.get("command", "").strip()
            if command:
                return command
    return None


def _first_gemini_command(root: Path, event_name: str) -> str | None:
    settings_json = root / ".gemini" / "settings.json"
    try:
        data = json.loads(settings_json.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    for block in data.get("hooks", {}).get(event_name, []):
        for hook in block.get("hooks", []):
            command = hook.get("command", "").strip()
            if command:
                return command
    return None


def _run_configured_hook(
    root: Path,
    command: str,
    payload: str,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        shlex.split(command),
        input=payload,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _load_single_json_stream(text: str, *, allow_empty: bool = False) -> dict | None:
    stripped = text.strip()
    if not stripped:
        if allow_empty:
            return None
        raise ValueError("empty JSON stream")
    return json.loads(stripped)


def _find_json_line(text: str) -> dict:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        return json.loads(stripped)
    raise ValueError("no JSON object line found")


def _assert_system_message_stdout(stdout: str, *, allow_empty: bool = False) -> None:
    data = _load_single_json_stream(stdout, allow_empty=allow_empty)
    if data is None:
        return
    if not isinstance(data, dict) or not isinstance(data.get("systemMessage"), str):
        raise ValueError("stdout JSON missing systemMessage string")


def _assert_additional_context_contains(stdout: str, expected: str) -> None:
    """Gemini / Antigravity SessionStart injects context via JSON
    ``hookSpecificOutput.additionalContext`` (stdout is parsed as JSON on
    exit 0 — plain text is rejected)."""
    data = _load_single_json_stream(stdout)
    output = data.get("hookSpecificOutput", {}) if isinstance(data, dict) else {}
    context = output.get("additionalContext", "")
    if not isinstance(context, str) or expected not in context:
        raise ValueError(f"additionalContext missing expected text: {expected}")


def _assert_pre_tool_deny(stdout: str) -> None:
    data = _load_single_json_stream(stdout)
    output = data.get("hookSpecificOutput", {}) if isinstance(data, dict) else {}
    if output.get("hookEventName") != "PreToolUse":
        raise ValueError("PreToolUse output missing hookEventName")
    if output.get("permissionDecision") != "deny":
        raise ValueError("PreToolUse did not deny destructive command")


def _assert_user_prompt_token(stderr: str) -> None:
    data = _find_json_line(stderr)
    if data.get("matched") is not True or data.get("token") != "trivial":
        raise ValueError("UserPromptSubmit did not parse [trivial] token")


def _assert_stdout_empty_or_json(stdout: str) -> None:
    if not stdout.strip():
        return
    _load_single_json_stream(stdout)


def _assert_plaintext_contains(stdout: str, expected: str) -> None:
    if expected not in stdout:
        raise ValueError(f"stdout missing expected text: {expected}")


def _assert_exit_code(proc: subprocess.CompletedProcess[str], expected: int) -> None:
    if proc.returncode != expected:
        raise ValueError(f"expected exit {expected}, got {proc.returncode}")


def check_hook_command_canaries(root: Path = PROJECT_ROOT) -> CheckResult:
    """Run configured hook commands against isolated temp state."""

    payloads = {
        "SessionStart": "",
        "UserPromptSubmit": json.dumps({"prompt": "[trivial] doctor canary"}),
        "PreToolUse": json.dumps({"tool_input": {"command": "git reset --hard"}}),
        "PostToolUse": json.dumps(
            {"tool_input": {"command": "uv run pytest tests/unit/agents_shared -q"}}
        ),
        "Stop": "",
    }
    validators = {
        "SessionStart": lambda proc: _assert_system_message_stdout(proc.stdout),
        "UserPromptSubmit": lambda proc: _assert_user_prompt_token(proc.stderr),
        "PreToolUse": lambda proc: _assert_pre_tool_deny(proc.stdout),
        "PostToolUse": lambda proc: _assert_stdout_empty_or_json(proc.stdout),
        "Stop": lambda proc: _assert_system_message_stdout(
            proc.stdout, allow_empty=True
        ),
    }
    antigravity_payloads = {
        "SessionStart": "",
        "BeforeAgent": json.dumps({"prompt": "[trivial] doctor canary"}),
        "BeforeTool": json.dumps(
            {
                "tool_name": "run_shell_command",
                "tool_input": {"command": "git reset --hard"},
            }
        ),
        "AfterTool": json.dumps(
            {
                "tool_name": "run_shell_command",
                "tool_input": {
                    "command": "pytest tests/unit/agents_shared/test_antigravity_harness.py -q"
                },
                # Real Gemini AfterTool contract: tool_response = {llmContent,
                # returnDisplay, optional data/error}. A SUCCESSFUL foreground
                # shell emits neither an "Exit Code:" line nor a `data` object
                # (the code is appended only on non-zero exit), so a realistic
                # success payload is just an "Output:" body.
                "tool_response": {
                    "llmContent": "Output: 1 passed in 0.10s",
                    "returnDisplay": "1 passed",
                },
            }
        ),
        "AfterAgent": "",
    }
    antigravity_validators = {
        "SessionStart": lambda proc: _assert_additional_context_contains(
            proc.stdout, "Antigravity repo harness active"
        ),
        "BeforeAgent": lambda proc: _assert_user_prompt_token(proc.stderr),
        "BeforeTool": lambda proc: (
            _assert_exit_code(proc, 2),
            _assert_plaintext_contains(proc.stderr, "Destructive git rollback"),
        ),
        "AfterTool": lambda proc: _assert_stdout_empty_or_json(proc.stdout),
        "AfterAgent": lambda proc: _assert_system_message_stdout(
            proc.stdout, allow_empty=True
        ),
    }

    issues: list[str] = []
    event_data: dict[str, dict] = {}
    before = _snapshot_real_state(root)

    with tempfile.TemporaryDirectory(prefix="harness-doctor-state-") as temp_state:
        env = os.environ.copy()
        env["HARNESS_STATE_ROOT"] = temp_state
        env["HARNESS_LAUNCHER_STRICT"] = "1"
        env["HARNESS_DEBUG"] = "1"
        env.setdefault("CODEX_THREAD_ID", "doctor-canary")
        env.setdefault("GEMINI_SESSION_ID", "doctor-canary")

        for event_name, payload in payloads.items():
            command = _first_codex_command(root, event_name)
            if command is None:
                issues.append(f"{event_name}: no configured Codex hook command")
                continue
            try:
                proc = _run_configured_hook(root, command, payload, env)
            except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as exc:
                issues.append(f"{event_name}: command failed to run: {exc}")
                continue

            event_data[event_name] = {
                "command": command,
                "returncode": proc.returncode,
                "stdout_bytes": len(proc.stdout.encode("utf-8")),
                "stderr_bytes": len(proc.stderr.encode("utf-8")),
            }
            if proc.returncode != 0:
                issues.append(
                    f"{event_name}: exit {proc.returncode}; stderr={proc.stderr[:200]!r}"
                )
                continue
            try:
                validators[event_name](proc)
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                issues.append(
                    f"{event_name}: contract validation failed: {exc}; "
                    f"stdout={proc.stdout[:200]!r}; stderr={proc.stderr[:200]!r}"
                )

        for event_name, payload in antigravity_payloads.items():
            command = _first_gemini_command(root, event_name)
            if command is None:
                issues.append(f"{event_name}: no configured Gemini hook command")
                continue
            try:
                proc = _run_configured_hook(root, command, payload, env)
            except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as exc:
                issues.append(f"{event_name}: Gemini command failed to run: {exc}")
                continue

            key = f"Gemini:{event_name}"
            event_data[key] = {
                "command": command,
                "returncode": proc.returncode,
                "stdout_bytes": len(proc.stdout.encode("utf-8")),
                "stderr_bytes": len(proc.stderr.encode("utf-8")),
            }
            # Assert the process exit code per event (mirrors the Codex loop):
            # BeforeTool must block (exit 2); every other event must succeed
            # (exit 0). Without this a hook that dies with a nonzero code but
            # prints plausible output would still pass its content validator.
            expected_rc = 2 if event_name == "BeforeTool" else 0
            if proc.returncode != expected_rc:
                issues.append(
                    f"{key}: exit {proc.returncode} (expected {expected_rc}); "
                    f"stderr={proc.stderr[:200]!r}"
                )
                continue
            try:
                antigravity_validators[event_name](proc)
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                issues.append(
                    f"{key}: contract validation failed: {exc}; "
                    f"stdout={proc.stdout[:200]!r}; stderr={proc.stderr[:200]!r}"
                )

    after = _snapshot_real_state(root)
    if before != after:
        before_keys = set(before)
        after_keys = set(after)
        added = sorted(after_keys - before_keys)
        removed = sorted(before_keys - after_keys)
        changed = sorted(k for k in before_keys & after_keys if before[k] != after[k])
        issues.append("real state changed during isolated canary run")
        event_data["state_diff"] = {
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    if issues:
        return CheckResult(
            "C6_hook_command_canaries",
            False,
            "; ".join(issues),
            {"issues": issues, "events": event_data},
        )
    return CheckResult(
        "C6_hook_command_canaries",
        True,
        "Configured Codex and Antigravity hook canaries passed with real state unchanged",
        {"events": event_data},
    )


# ---------------------------------------------------------------------------
# C7 — stale marker statistics
# ---------------------------------------------------------------------------

_STATE_DIRS = (
    Path(".claude/state"),
    Path(".codex/state"),
    Path(".antigravity/state"),
)
_STALE_THRESHOLD_S = 86_400  # 24 hours


def _count_stale(state_dir: Path, glob: str, threshold_s: float) -> dict:
    now = time.time()
    all_files = list(state_dir.glob(glob)) if state_dir.exists() else []
    stale = [f for f in all_files if (now - f.stat().st_mtime) > threshold_s]
    return {"total": len(all_files), "stale": len(stale)}


def check_stale_stats(root: Path = PROJECT_ROOT) -> CheckResult:
    stats: dict[str, dict] = {}
    total_stale = 0

    for rel_dir in _STATE_DIRS:
        abs_dir = root / rel_dir
        dir_key = str(rel_dir)
        token_counts = _count_stale(
            abs_dir, "exception-token-*.json", _STALE_THRESHOLD_S
        )
        verify_counts = _count_stale(abs_dir, "verify-log-*.json", _STALE_THRESHOLD_S)
        stats[dir_key] = {
            "exception_token": token_counts,
            "verify_log": verify_counts,
        }
        total_stale += token_counts["stale"] + verify_counts["stale"]

    detail = f"{total_stale} stale marker(s) found across tool state dirs"
    return CheckResult(
        "C7_stale_stats",
        True,  # informational — never fails on its own
        detail,
        {"state_dirs": stats, "total_stale": total_stale},
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_CHECKS = [
    check_gitignore_registered,
    check_no_git_tracked_state,
    check_stop_hook_schema,
    check_marker_glob_coverage,
    check_hook_interpreter,
    check_hook_command_canaries,
    check_stale_stats,
]


def run_all(root: Path = PROJECT_ROOT) -> list[CheckResult]:
    return [fn(root) for fn in _CHECKS]


def main() -> int:
    args = sys.argv[1:]
    text_mode = "--text" in args

    results = run_all()
    all_ok = all(r.ok for r in results)

    output = {
        "project_root": str(PROJECT_ROOT),
        "all_ok": all_ok,
        "checks": [asdict(r) for r in results],
    }

    if text_mode:
        for r in results:
            status = "PASS" if r.ok else "FAIL"
            print(f"[{status}] {r.name}: {r.detail}")
        if not all_ok:
            failed = [r.name for r in results if not r.ok]
            print(f"\nFailed checks: {', '.join(failed)}")
    else:
        print(json.dumps(output, indent=2))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
