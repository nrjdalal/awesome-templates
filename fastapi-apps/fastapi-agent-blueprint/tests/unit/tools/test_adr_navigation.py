"""The ADR discovery index must render active decisions inside Markdown tables.

A blank line before newly appended rows twice orphaned real decisions despite
valid links. Link checks alone cannot prove the index still renders as a table.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_active_adr_links_are_inside_index_tables() -> None:
    history = ROOT / "docs/history"
    active = {path.name for path in history.glob("[0-9][0-9][0-9]-*.md")}
    lines = (history / "README.md").read_text(encoding="utf-8").splitlines()
    indexed: set[str] = set()
    in_table = False
    for number, line in enumerate(lines):
        if (
            number > 0
            and lines[number - 1].startswith("|")
            and re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+\s*", line)
        ):
            in_table = True
            continue
        if not line.startswith("|"):
            in_table = False
        if in_table:
            indexed.update(re.findall(r"\]\((\d{3}-[^/)#]+\.md)(?:#[^)]*)?\)", line))
    assert active, "The check must discover real active ADRs"
    assert active <= indexed, (
        f"Active ADRs outside rendered index tables: {sorted(active - indexed)}"
    )
