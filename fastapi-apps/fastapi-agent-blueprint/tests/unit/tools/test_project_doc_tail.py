"""Keep the shared constitution complete at Codex's default project-doc budget."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TAIL_MARKER = "## Drift Management"


def test_shared_constitution_tail_survives_default_codex_budget():
    """The default budget must include every byte, including the closing rules."""
    content = (ROOT / "AGENTS.md").read_bytes()
    assert len(content) <= 30_720
    loaded = content[:32_768].decode("utf-8")
    assert loaded == content.decode("utf-8")
    assert TAIL_MARKER in loaded.splitlines()


def test_healthcheck_marker_is_the_last_shared_constitution_section():
    """A moved tail marker would turn the healthcheck back into a head check."""
    headings = [
        line
        for line in (ROOT / "AGENTS.md").read_text().splitlines()
        if line.startswith("## ")
    ]
    assert headings[-1] == TAIL_MARKER
