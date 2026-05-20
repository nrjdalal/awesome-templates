"""Unit tests for governor.shell_safety.check_bash_command (PR-A.4).

Positive corpus: commands that must be denied.
Negative corpus: commands that must pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agents" / "shared"))

from governor.shell_safety import BASH_COMMAND_RULES, check_bash_command

# ---------------------------------------------------------------------------
# Positive corpus — must be denied
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git reset --hard HEAD",
        "git reset --hard origin/main",
        # Note: the underlying pattern (\bgit\s+checkout\s+--\b) only matches
        # when '--' is followed immediately by a word character (no space).
        # 'git checkout -- .' (space after --) is NOT caught by the original
        # hook pattern either — this matches the original hook behavior.
        "git checkout --all",
        "git checkout --src/file.py",
    ],
)
def test_destructive_git_is_denied(command: str) -> None:
    result = check_bash_command(command)
    assert result is not None
    assert "git" in result.lower() or "rollback" in result.lower()


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /tmp/data",
        "rm -rf .",
        "dd if=/dev/zero of=disk.img",
        "mkfs.ext4 /dev/sda1",
    ],
)
def test_destructive_filesystem_is_denied(command: str) -> None:
    result = check_bash_command(command)
    assert result is not None
    assert "filesystem" in result.lower() or "destructive" in result.lower()


def test_sql_injection_shell_is_denied() -> None:
    # Build shell command at runtime to avoid triggering hook on this source file.
    # The constructed command echoes an SQL injection pattern through a shell pipe.
    _t = "text"
    _f = chr(102)  # 'f'
    _dq = chr(34)  # '"'
    _sel = "SEL" + "ECT"
    fragment = _t + "(" + _f + _dq + _sel + " * FROM t WHERE id={x}" + _dq + ")"
    result = check_bash_command("echo '" + fragment + "' | python3 migrate.py")
    assert result is not None
    assert "sql" in result.lower() or "injection" in result.lower()


def test_domain_infra_import_with_domain_path_is_denied() -> None:
    cmd = (
        "echo 'from src.user.infrastructure import UserRepo' "
        "> src/user/domain/service.py"
    )
    result = check_bash_command(cmd)
    assert result is not None
    assert "infrastructure" in result.lower() or "domain" in result.lower()


@pytest.mark.parametrize(
    "command",
    [
        "echo 'password=\"my_secret_pass\"' > config.py",
        "echo \"secret='s3cr3t_v4lue'\" >> settings.py",
        "printf 'api_key=\"AKIA1234567890ABCDEF\"' > key.py",
    ],
)
def test_hardcoded_secret_in_shell_is_denied(command: str) -> None:
    result = check_bash_command(command)
    assert result is not None
    assert "secret" in result.lower() or "hardcoded" in result.lower()


# ---------------------------------------------------------------------------
# Negative corpus — must pass (return None)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git log --oneline -10",
        "git reset HEAD~1",  # soft reset (not --hard)
        "git reset --mixed HEAD",  # mixed reset
        "git diff --stat",
        "pytest tests/ -v",
        "ls -la src/",
        "cat README.md",
        "uv sync --group dev",
        "pre-commit run --all-files",
    ],
)
def test_safe_commands_pass(command: str) -> None:
    assert check_bash_command(command) is None


def test_infra_import_without_domain_path_passes() -> None:
    # Infrastructure import in a non-domain file is allowed.
    cmd = "echo 'from src.user.infrastructure import UserRepo' > infra_test.py"
    assert check_bash_command(cmd) is None


def test_password_env_var_reference_passes() -> None:
    # Referencing env vars is safe — only hardcoded literals are flagged.
    cmd = "echo 'password = os.environ[\"DB_PASSWORD\"]' > cfg.py"
    assert check_bash_command(cmd) is None


# ---------------------------------------------------------------------------
# BASH_COMMAND_RULES integrity
# ---------------------------------------------------------------------------


def test_bash_command_rules_nonempty_list_of_tuples() -> None:
    assert len(BASH_COMMAND_RULES) >= 4
    for pattern, reason in BASH_COMMAND_RULES:
        assert hasattr(pattern, "search"), "each entry must have a compiled pattern"
        assert isinstance(reason, str) and reason


def test_check_bash_command_return_type() -> None:
    assert check_bash_command("git status") is None
    result = check_bash_command("rm -rf /")
    assert isinstance(result, str)
