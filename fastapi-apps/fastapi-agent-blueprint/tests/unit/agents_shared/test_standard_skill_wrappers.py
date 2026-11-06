"""Keep standard wrappers thin without losing invocation or source contracts."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
STANDARD_SKILLS = sorted(
    path.parent.name
    for path in (ROOT / ".agents/skills").glob("*/SKILL.md")
    if path.parent.name not in {"trace", "why"}
)


def _overview(text: str) -> str:
    return re.split(
        r"^## ", text.split("## Procedure Overview\n", 1)[1], maxsplit=1, flags=re.M
    )[0].strip()


def test_standard_pairs_load_authority_and_share_the_same_outline():
    assert len(STANDARD_SKILLS) == 15
    for name in STANDARD_SKILLS:
        texts = [
            (ROOT / harness / "skills" / name / "SKILL.md").read_text()
            for harness in (".claude", ".agents")
        ]
        for text in texts:
            assert "## Procedure Authority" in text
            assert f"docs/ai/shared/skills/{name}.md" in text
            assert "before acting; it owns requirements, gates and outputs" in text
        assert _overview(texts[0]) == _overview(texts[1]), name


def test_manual_only_claude_skills_are_visible_in_onboarding():
    onboard = (ROOT / ".claude/skills/onboard/SKILL.md").read_text()
    checklist = (ROOT / "docs/ai/shared/drift-checklist.md").read_text()
    for name in ("sync-guidelines", "migrate-domain", "trace", "why"):
        text = (ROOT / ".claude/skills" / name / "SKILL.md").read_text()
        metadata = yaml.safe_load(text.split("---", 2)[1])
        assert metadata["disable-model-invocation"] is True
        assert f"/{name}" in onboard
        assert f"`{name}`" in checklist
    assert "scoped" in onboard
    assert "docs/ai/shared/commands.md" in onboard
