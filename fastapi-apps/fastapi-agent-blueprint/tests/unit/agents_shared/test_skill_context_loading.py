"""Keep skill context loading lean without leaking Claude paths across tools."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
READ_RULE = re.compile(r"\bRead\s+`\.claude/rules/", re.I)


@pytest.mark.parametrize(
    "skill", sorted(CLAUDE_SKILLS.glob("*/SKILL.md")), ids=lambda path: path.parent.name
)
def test_claude_wrappers_do_not_reread_auto_loaded_rules(skill: Path) -> None:
    violations = [
        line
        for line in skill.read_text(encoding="utf-8").splitlines()
        if READ_RULE.search(line) and "auto-loaded" not in line.lower()
    ]
    assert not violations, f"{skill.relative_to(REPO_ROOT)}: {violations}"


def test_claude_rule_paths_stay_out_of_tool_neutral_and_codex_skills() -> None:
    paths = [
        *(REPO_ROOT / ".agents" / "skills").rglob("*.md"),
        *(REPO_ROOT / "docs" / "ai" / "shared" / "skills").glob("*.md"),
    ]
    violations = [
        str(path.relative_to(REPO_ROOT))
        for path in paths
        if path != REPO_ROOT / "docs/ai/shared/skills/sync-guidelines.md"
        and ".claude/rules/" in path.read_text(encoding="utf-8")
    ]
    assert not violations, violations


@pytest.mark.parametrize(
    "line",
    [
        "Read `.claude/rules/a.md`",
        "1. Read `.claude/rules/a.md`",
        "- Phase 5 CLI commands: Read `.claude/rules/a.md`",
    ],
)
def test_rule_read_detection_includes_embedded_phase_instructions(line: str) -> None:
    assert READ_RULE.search(line)
