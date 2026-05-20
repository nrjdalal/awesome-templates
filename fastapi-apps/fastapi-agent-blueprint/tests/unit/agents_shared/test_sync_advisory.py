"""Unit tests for governor.sync_advisory.classify_advisory (PR-A.5 + F-1).

Positive corpus: file paths that must trigger foundation or structure advisory.
Negative corpus: file paths that must return (None, []).
Section 7: CLI bridge (sync_advisory_cli) output format and fail-open.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agents" / "shared"))

from governor.sync_advisory import (
    FOUNDATION_PREFIXES,
    STRUCTURE_MARKERS,
    classify_advisory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _level(paths: list[str]) -> str | None:
    level, _ = classify_advisory(paths)
    return level


def _files(paths: list[str]) -> list[str]:
    _, matched = classify_advisory(paths)
    return matched


# ---------------------------------------------------------------------------
# 1. Foundation positive corpus
# ---------------------------------------------------------------------------


def test_agents_md_is_foundation() -> None:
    assert _level(["AGENTS.md"]) == "foundation"


def test_claude_md_is_foundation() -> None:
    assert _level(["CLAUDE.md"]) == "foundation"


def test_codex_hook_is_foundation() -> None:
    assert _level([".codex/hooks/pre-tool-security.py"]) == "foundation"


def test_agents_shared_is_foundation() -> None:
    assert _level([".agents/shared/governor/shell_safety.py"]) == "foundation"


def test_claude_hook_is_foundation() -> None:
    assert _level([".claude/hooks/pre_tool_security.py"]) == "foundation"


def test_claude_rules_is_foundation() -> None:
    assert _level([".claude/rules/project-status.md"]) == "foundation"


def test_claude_settings_is_foundation() -> None:
    assert _level([".claude/settings.json"]) == "foundation"


def test_docs_ai_shared_is_foundation() -> None:
    assert _level(["docs/ai/shared/harness-asset-matrix.md"]) == "foundation"


def test_src_apps_is_foundation() -> None:
    assert _level(["src/_apps/server/app.py"]) == "foundation"


def test_src_core_is_foundation() -> None:
    assert _level(["src/_core/domain/base_service.py"]) == "foundation"


def test_pyproject_toml_is_foundation() -> None:
    assert _level(["pyproject.toml"]) == "foundation"


def test_pre_commit_config_is_foundation() -> None:
    assert _level([".pre-commit-config.yaml"]) == "foundation"


def test_foundation_files_returned_in_matched() -> None:
    paths = ["AGENTS.md", "src/user/service.py"]
    level, matched = classify_advisory(paths)
    assert level == "foundation"
    assert "AGENTS.md" in matched
    assert "src/user/service.py" not in matched


# ---------------------------------------------------------------------------
# 2. Foundation takes precedence over structure
# ---------------------------------------------------------------------------


def test_foundation_beats_structure() -> None:
    paths = [
        "AGENTS.md",
        "src/user/infrastructure/di/container.py",
    ]
    assert _level(paths) == "foundation"


# ---------------------------------------------------------------------------
# 3. Structure positive corpus
# ---------------------------------------------------------------------------


def test_infra_di_is_structure() -> None:
    assert _level(["src/user/infrastructure/di/container.py"]) == "structure"


def test_server_routers_is_structure() -> None:
    assert _level(["src/user/interface/server/routers/user_router.py"]) == "structure"


def test_domain_protocols_is_structure() -> None:
    assert _level(["src/user/domain/protocols/user_repo_protocol.py"]) == "structure"


def test_domain_dtos_is_structure() -> None:
    assert _level(["src/user/domain/dtos/user_dto.py"]) == "structure"


def test_structure_files_returned_in_matched() -> None:
    paths = ["src/user/infrastructure/di/container.py", "src/user/service.py"]
    level, matched = classify_advisory(paths)
    assert level == "structure"
    assert "src/user/infrastructure/di/container.py" in matched
    assert "src/user/service.py" not in matched


# ---------------------------------------------------------------------------
# 4. Structure negative: paths with /_ segment excluded from structure
# ---------------------------------------------------------------------------


def test_underscore_segment_path_is_not_structure() -> None:
    # Paths with /_ in them are excluded from structure detection.
    # e.g. src/user/_archive/infrastructure/di/ is not a domain structure path.
    # (src/_core/ is a foundation prefix, so it returns "foundation" — not "structure")
    assert _level(["src/user/_archive/infrastructure/di/container.py"]) is None


# ---------------------------------------------------------------------------
# 5. Negative corpus — must return (None, [])
# ---------------------------------------------------------------------------


def test_plain_src_file_passes() -> None:
    assert _level(["src/user/service.py"]) is None


def test_test_file_passes() -> None:
    assert _level(["tests/unit/test_user.py"]) is None


def test_readme_passes() -> None:
    assert _level(["README.md"]) is None


def test_docs_non_ai_shared_passes() -> None:
    assert _level(["docs/operations/observability-otel.md"]) is None


def test_empty_list_passes() -> None:
    assert _level([]) is None
    assert _files([]) == []


# ---------------------------------------------------------------------------
# 6. Constants integrity
# ---------------------------------------------------------------------------


def test_foundation_prefixes_nonempty_tuple() -> None:
    assert isinstance(FOUNDATION_PREFIXES, tuple)
    assert len(FOUNDATION_PREFIXES) >= 10


def test_structure_markers_nonempty_tuple() -> None:
    assert isinstance(STRUCTURE_MARKERS, tuple)
    assert len(STRUCTURE_MARKERS) >= 4


# ---------------------------------------------------------------------------
# 7. CLI bridge (sync_advisory_cli) — output format and fail-open (F-1)
# ---------------------------------------------------------------------------


def _run_cli(stdin_text: str) -> list[str]:
    """Run sync_advisory_cli.main() with the given stdin, return stdout lines."""
    import governor.sync_advisory_cli as cli_mod

    captured = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(stdin_text)),
        patch("sys.stdout", captured),
    ):
        cli_mod.main()
    return [line for line in captured.getvalue().splitlines() if line]


def test_cli_foundation_output() -> None:
    lines = _run_cli("AGENTS.md\nsrc/user/service.py\n")
    assert lines[0] == "foundation"
    assert "AGENTS.md" in lines[1:]


def test_cli_structure_output() -> None:
    lines = _run_cli("src/user/infrastructure/di/container.py\n")
    assert lines[0] == "structure"
    assert "src/user/infrastructure/di/container.py" in lines[1:]


def test_cli_none_output() -> None:
    lines = _run_cli("src/user/service.py\n")
    assert lines == ["none"]


def test_cli_empty_stdin_returns_none() -> None:
    lines = _run_cli("")
    assert lines == ["none"]


def test_cli_fail_open_on_classify_error() -> None:
    """Any exception inside main() must produce 'none' cleanly (HC-5.5 fail-open)."""
    import governor.sync_advisory as adv_mod
    import governor.sync_advisory_cli as cli_mod

    captured = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO("AGENTS.md\n")),
        patch("sys.stdout", captured),
        patch.object(adv_mod, "classify_advisory", side_effect=RuntimeError("boom")),
    ):
        cli_mod.main()
    assert captured.getvalue().strip() == "none"
