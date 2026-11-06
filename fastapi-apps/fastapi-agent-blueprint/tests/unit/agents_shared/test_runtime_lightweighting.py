"""Pin intentional hook retirement while retaining live safety and continuity."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".agents/shared"))
from governor.code_safety import check_code_safety  # noqa: E402


@pytest.mark.parametrize("harness", [".claude", ".codex", ".antigravity"])
def test_retired_verify_modules_have_no_active_consumers(harness):
    hooks = ROOT / harness / "hooks"
    assert not (hooks / "verify_first.py").exists()
    for path in hooks.glob("*.py"):
        source = path.read_text()
        assert not re.search(r"(?:import|from) verify_first\b", source), path
        assert "append_verify_log(" not in source, path
        assert "cleanup_stale_verify_logs(" not in source, path


def test_claude_edit_hooks_keep_stage_gate_without_runtime_content_scan():
    hooks = json.loads((ROOT / ".claude/settings.json").read_text())["hooks"]
    before = str(hooks["PreToolUse"])
    after = str(hooks["PostToolUse"])
    assert "pre-tool-security" not in before
    assert "pre-tool-stage-block" in before
    assert "stage-gate" in after
    assert "verify-first" not in after and "verify-log" not in after


def test_code_safety_compatibility_does_not_restore_retired_runtime_checks():
    assert (
        check_code_safety(
            "src/example/domain/services/a.py",
            'text(f"SELECT {x}")\npassword="12345"\nfrom src.x.infrastructure import y\nlogger.info(password)',
        )
        == []
    )


@pytest.mark.parametrize(
    "content,leak",
    [
        ('logger.info("created", password=value)', True),
        ("logger.bind(api_key=credential)", True),
        ('logging.error("failed: %s", access_token)', True),
        ("print(secret)", True),
        ('logger.info("request_complete", status=200)', False),
        ("password = settings.password", False),
    ],
)
def test_sensitive_logging_is_a_blocking_production_hook(content, leak):
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hook = next(
        h for r in config["repos"] for h in r["hooks"] if h["id"] == "sensitive-logging"
    )
    assert hook["language"] == "pygrep"
    assert re.search(hook["files"], "src/user/service.py")
    assert re.search(hook["files"], "examples/demo/domain/services/a.py")
    assert not re.search(hook["files"], "tests/test_logging.py")
    assert bool(re.search(hook["entry"], content)) is leak


def test_retirement_covers_configuration_shell_facade_locale_and_readers():
    import ast

    import governor
    from governor import locale

    for relative in [
        ".claude/settings.json",
        ".codex/hooks.json",
        ".gemini/settings.json",
    ]:
        payload = json.loads((ROOT / relative).read_text())
        for groups in payload["hooks"].values():
            for group in groups:
                for hook in group["hooks"]:
                    assert not re.search(r"verify[-_](?:first|log)", hook["command"])
    for path in (ROOT / ".claude/hooks").glob("*.sh"):
        assert not re.search(r"verify[-_](?:first|log)", path.read_text()), path
    assert not (ROOT / ".agents/shared/governor/verify.py").exists()
    retired = {
        "REMINDER_TEXT",
        "VERIFY_PATTERNS",
        "append_verify_log",
        "verify_log_path",
        "cleanup_stale_verify_logs",
        "should_remind_claude",
        "extract_file_path",
        "is_python_source",
    }
    assert retired.isdisjoint(governor.__all__)
    assert not any(hasattr(governor, name) for name in retired)
    assert "REMINDER_TEXT" not in locale._LOCALE_EN
    assert "REMINDER_TEXT" not in locale._LOCALE_KO
    for relative in [
        "tools/governor_state_doctor.py",
        "tools/check_state_lifecycle.py",
    ]:
        constants = [
            n.value
            for n in ast.walk(ast.parse((ROOT / relative).read_text()))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        assert not any("verify-log-*" in value for value in constants), relative


def test_sensitive_logging_real_precommit_hook_and_deliberate_skip(tmp_path):
    import os
    import subprocess

    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hook = next(
        h for r in config["repos"] for h in r["hooks"] if h["id"] == "sensitive-logging"
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    config_path = tmp_path / ".pre-commit-config.yaml"
    config_path.write_text(
        yaml.safe_dump({"repos": [{"repo": "local", "hooks": [hook]}]})
    )
    (tmp_path / "src").mkdir()
    source = tmp_path / "src/probe.py"
    source.write_text('logger.info("request_complete", status=200)\n')
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    env = {k: v for k, v in os.environ.items() if k != "SKIP"}
    command = [
        sys.executable,
        "-m",
        "pre_commit",
        "run",
        "sensitive-logging",
        "--all-files",
    ]

    def run(extra=None):
        return subprocess.run(
            command,
            cwd=tmp_path,
            env={**env, **(extra or {})},
            capture_output=True,
            text=True,
            check=False,
        )

    assert run().returncode == 0
    # This legitimate event name is a documented lexical false positive.
    source.write_text('logger.warning("invalid_token", status=401)\n')
    result = run()
    assert result.returncode == 1 and "src/probe.py" in result.stdout + result.stderr
    assert run({"SKIP": "sensitive-logging"}).returncode == 0
    source.write_text('logger.info("created", password=value)\n')
    assert run().returncode == 1
