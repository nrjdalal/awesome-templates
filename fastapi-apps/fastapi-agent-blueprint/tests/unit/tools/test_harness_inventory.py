"""Inventory discovery and reviewed judgment must remain independent and complete."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "harness_inventory", ROOT / "tools/generate_harness_inventory.py"
)
assert spec is not None and spec.loader is not None
inventory = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inventory
spec.loader.exec_module(inventory)


def baseline():
    tracked = set(inventory.CONSTITUTIONAL) | set(inventory.ENFORCEMENT)
    tracked |= {root + "entry.md" for root in inventory.SHARED_GROUPS}
    assets = inventory.discover(tracked)
    mapping = {item.path: "Keep" for item in assets}
    return tracked, {"schema_version": 1, "buckets": mapping, "retired": {}}


def test_new_shared_file_requires_reviewed_decision_and_removed_file_is_stale():
    tracked, decisions = baseline()
    path = "docs/ai/shared/new-reference.md"
    tracked.add(path)
    with pytest.raises(ValueError, match="missing=.*new-reference"):
        inventory.render(inventory.discover(tracked), decisions, tracked)
    decisions["buckets"][path] = "Overlay"
    result = inventory.render(inventory.discover(tracked), decisions, tracked)
    assert path in result
    tracked.remove(path)
    with pytest.raises(ValueError, match="stale=.*new-reference"):
        inventory.render(inventory.discover(tracked), decisions, tracked)


def test_triple_missing_member_or_disagreeing_judgment_fails():
    tracked, decisions = baseline()
    members = {
        "docs/ai/shared/skills/demo.md",
        ".claude/skills/demo/SKILL.md",
        ".agents/skills/demo/SKILL.md",
    }
    tracked |= members - {".agents/skills/demo/SKILL.md"}
    with pytest.raises(ValueError, match="Incomplete skill triple demo"):
        inventory.discover(tracked)
    tracked |= members
    for path in members:
        decisions["buckets"][path] = "Keep"
    decisions["buckets"][".claude/skills/demo/SKILL.md"] = "Overlay"
    with pytest.raises(ValueError, match="buckets disagree"):
        inventory.render(inventory.discover(tracked), decisions, tracked)
    decisions["buckets"][".claude/skills/demo/SKILL.md"] = "Keep"
    rows = list(
        csv.DictReader(
            io.StringIO(
                inventory.render(inventory.discover(tracked), decisions, tracked)
            )
        )
    )
    assert sum(row["tier"] == "2" for row in rows) == 1


def test_retirement_requires_absence_and_drop_and_preserves_original_tier():
    tracked, decisions = baseline()
    path = ".claude/hooks/removed.py"
    decisions["retired"][path] = 3
    decisions["buckets"][path] = "Keep"
    with pytest.raises(ValueError, match="must be Drop"):
        inventory.render(inventory.discover(tracked), decisions, tracked)
    decisions["buckets"][path] = "Drop"
    result = inventory.render(inventory.discover(tracked), decisions, tracked)
    assert f"3,{path},Drop,retired" in result
    tracked.add(path)
    with pytest.raises(ValueError, match="Retired asset exists"):
        inventory.render(inventory.discover(tracked), decisions, tracked)


def test_local_settings_and_cache_do_not_change_generated_output():
    tracked, decisions = baseline()
    expected = inventory.render(inventory.discover(tracked), decisions, tracked)
    tracked |= {
        inventory.LOCAL_ONLY,
        ".claude/hooks/__pycache__/foo.pyc",
        ".codex/hooks/entry.pyc",
        "docs/history/archive/old-matrix.md",
    }
    assert inventory.render(inventory.discover(tracked), decisions, tracked) == expected


def test_missing_required_constitution_is_not_silently_dropped():
    tracked, _ = baseline()
    tracked.remove("AGENTS.md")
    with pytest.raises(ValueError, match="Required scope assets missing: AGENTS.md"):
        inventory.discover(tracked)


def test_check_rejects_tampered_output_then_accepts_regenerated_file(
    tmp_path, monkeypatch
):
    tracked, decisions = baseline()
    monkeypatch.setattr(inventory, "ROOT", tmp_path)
    monkeypatch.setattr(inventory, "tracked_files", lambda root: tracked)
    monkeypatch.setattr(sys, "argv", ["inventory", "--check"])
    map_path = tmp_path / inventory.MAP_PATH
    map_path.parent.mkdir(parents=True)
    map_path.write_text(json.dumps(decisions))
    output = tmp_path / inventory.OUTPUT_PATH
    output.write_text("pretend-valid\n")
    assert inventory.main() == 1
    output.write_text(inventory.generate(tmp_path))
    assert inventory.main() == 0
