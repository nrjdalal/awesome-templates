from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_antigravity_repo_local_harness_assets_exist() -> None:
    expected = [
        ".gemini/settings.json",
        ".antigravity/plugin.json",
        ".antigravity/gemini-extension.json",
        ".antigravity/mcp_config.json",
        ".antigravity/permissions.json",
        ".antigravity/rules/project-harness.md",
        ".antigravity/hooks/_shared.py",
        ".antigravity/hooks/session-start.py",
        ".antigravity/hooks/user-prompt-submit.py",
        ".antigravity/hooks/pre-tool-security.py",
        ".antigravity/hooks/post-tool-format.py",
        ".antigravity/hooks/verify_first.py",
        ".antigravity/hooks/completion_gate.py",
        ".antigravity/hooks/stop-sync-reminder.py",
    ]

    missing = [path for path in expected if not (REPO_ROOT / path).exists()]

    assert missing == []


def test_gemini_settings_wires_antigravity_hooks_through_shared_launcher() -> None:
    settings = json.loads((REPO_ROOT / ".gemini/settings.json").read_text())
    hooks = settings["hooks"]

    expected_events = {
        "SessionStart",
        "BeforeAgent",
        "BeforeTool",
        "AfterTool",
        "AfterAgent",
    }
    assert expected_events <= set(hooks)

    commands = [
        hook["command"]
        for blocks in hooks.values()
        for block in blocks
        for hook in block.get("hooks", [])
    ]

    assert commands
    assert all(
        command.startswith("sh .agents/shared/harness-python.sh .antigravity/hooks/")
        for command in commands
    )
    assert all(".claude/hooks/" not in command for command in commands)
    assert all(".codex/hooks/" not in command for command in commands)


def test_antigravity_plugin_and_extension_manifests_are_aligned() -> None:
    plugin = json.loads((REPO_ROOT / ".antigravity/plugin.json").read_text())
    extension = json.loads(
        (REPO_ROOT / ".antigravity/gemini-extension.json").read_text()
    )

    assert plugin["name"] == "fastapi-agent-blueprint"
    assert extension["name"] == plugin["name"]
    assert plugin["version"] == extension["version"]


def test_antigravity_hooks_import_shared_governor_policy() -> None:
    hook_files = [
        ".antigravity/hooks/user-prompt-submit.py",
        ".antigravity/hooks/pre-tool-security.py",
        ".antigravity/hooks/verify_first.py",
        ".antigravity/hooks/completion_gate.py",
        ".antigravity/hooks/stop-sync-reminder.py",
    ]

    for rel_path in hook_files:
        text = (REPO_ROOT / rel_path).read_text()
        assert "from governor" in text


def _run_hook(
    rel_path: str, payload: dict, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HARNESS_STATE_ROOT"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / rel_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )


def test_antigravity_user_prompt_hook_writes_token_marker(
    tmp_path: Path,
) -> None:
    result = _run_hook(
        ".antigravity/hooks/user-prompt-submit.py",
        {"prompt": "[trivial] rename local variable"},
        tmp_path,
    )

    assert result.returncode == 0
    marker_dir = tmp_path / ".antigravity" / "state"
    markers = list(marker_dir.glob("exception-token-*.json"))
    assert len(markers) == 1
    marker = json.loads(markers[0].read_text())
    assert marker["matched"] is True
    assert marker["token"] == "trivial"


def test_antigravity_pre_tool_hook_blocks_shared_shell_safety(
    tmp_path: Path,
) -> None:
    result = _run_hook(
        ".antigravity/hooks/pre-tool-security.py",
        {
            "tool_name": "run_shell_command",
            "tool_input": {"command": "git reset --hard"},
        },
        tmp_path,
    )

    assert result.returncode == 2
    assert "Destructive git rollback" in result.stderr


def test_antigravity_session_start_emits_json_context(tmp_path: Path) -> None:
    """SessionStart stdout must be valid JSON on exit 0 (Gemini CLI parses it as
    JSON and rejects plain text); the banner rides in additionalContext."""
    result = _run_hook(".antigravity/hooks/session-start.py", {}, tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "Antigravity repo harness active" in context
