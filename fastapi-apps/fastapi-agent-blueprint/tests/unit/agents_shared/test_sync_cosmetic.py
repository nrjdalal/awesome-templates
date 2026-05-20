"""Tests for ADR 047 D4 — `/sync-guidelines` cosmetic carve-out."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED = REPO_ROOT / ".agents" / "shared"


def _import(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gov():
    sys.path.insert(0, str(SHARED))
    try:
        from governor import (  # type: ignore[import-not-found]
            completion_gate,
            sync_cosmetic,
        )

        return sync_cosmetic, completion_gate
    finally:
        sys.path.pop(0)


COSMETIC_DIFF_PROJECT_STATUS = """\
@@ -1,3 +1,3 @@
 # Project Status
-> Last synced: 2026-04-30 via /sync-guidelines (#152 reviewed)
+> Last synced: 2026-05-01 via /sync-guidelines (#156 docs selector)
"""

COSMETIC_DIFF_TABLE_ROW_ADDITION = """\
@@ -45,6 +45,7 @@
 | A | B | C |
 | --- | --- | --- |
 | foo | bar | baz |
+| Feature X | Issue #99 | Notes go here |
 | qux | quux | corge |
"""

SEMANTIC_DIFF_PROJECT_STATUS = """\
@@ -10,2 +10,7 @@
 # Project Status
+## Architecture Violations
+
+- new section content
+- with more rules
+
 > Last synced: 2026-05-01 via /sync-guidelines (#157)
"""

COSMETIC_DIFF_OVERVIEW = """\
@@ -1,1 +1,1 @@
-> Last synced: 2026-04-30 via /sync-guidelines (#152)
+> Last synced: 2026-05-01 via /sync-guidelines (#157)
"""


def test_changed_lines_strips_diff_headers(gov):
    sync, _ = gov
    assert sync._changed_lines(COSMETIC_DIFF_PROJECT_STATUS) == [
        "> Last synced: 2026-04-30 via /sync-guidelines (#152 reviewed)",
        "> Last synced: 2026-05-01 via /sync-guidelines (#156 docs selector)",
    ]


def test_cosmetic_diff_last_synced_only_passes(gov):
    sync, _ = gov
    assert sync._is_cosmetic_diff(
        ".claude/rules/project-status.md", COSMETIC_DIFF_PROJECT_STATUS
    )


def test_cosmetic_diff_table_row_addition_passes(gov):
    sync, _ = gov
    assert sync._is_cosmetic_diff(
        ".claude/rules/project-status.md", COSMETIC_DIFF_TABLE_ROW_ADDITION
    )


def test_semantic_diff_with_new_heading_fails(gov):
    sync, _ = gov
    assert not sync._is_cosmetic_diff(
        ".claude/rules/project-status.md", SEMANTIC_DIFF_PROJECT_STATUS
    )


def test_overview_cosmetic_only_accepts_last_synced(gov):
    sync, _ = gov
    assert sync._is_cosmetic_diff(
        ".claude/rules/project-overview.md", COSMETIC_DIFF_OVERVIEW
    )


def test_overview_rejects_table_row_outside_status(gov):
    """`Recent Major Changes` table only exists in project-status.md.

    project-overview.md / commands.md may NOT add table rows under the
    sync-cosmetic carve-out.
    """

    sync, _ = gov
    assert not sync._is_cosmetic_diff(
        ".claude/rules/project-overview.md", COSMETIC_DIFF_TABLE_ROW_ADDITION
    )


def test_path_outside_carve_out_set_rejected(gov):
    sync, _ = gov
    assert not sync._is_cosmetic_diff(
        ".claude/rules/architecture-conventions.md", COSMETIC_DIFF_OVERVIEW
    )


def test_is_sync_cosmetic_only_subset_must_be_in_carve_out_set(gov):
    sync, _ = gov

    def diff_for(path):
        return COSMETIC_DIFF_PROJECT_STATUS

    # Subset includes a non-carve-out path → False even if the cosmetic file is also there.
    assert not sync.is_sync_cosmetic_only(
        [".claude/rules/project-status.md", "AGENTS.md"], diff_for
    )


def test_is_sync_cosmetic_only_all_paths_cosmetic_passes(gov):
    sync, _ = gov

    def diff_for(path):
        if path == ".claude/rules/project-status.md":
            return COSMETIC_DIFF_PROJECT_STATUS
        if path == ".claude/rules/project-overview.md":
            return COSMETIC_DIFF_OVERVIEW
        return ""

    assert sync.is_sync_cosmetic_only(
        [
            ".claude/rules/project-status.md",
            ".claude/rules/project-overview.md",
        ],
        diff_for,
    )


def test_is_sync_cosmetic_only_one_semantic_diff_fails(gov):
    sync, _ = gov

    def diff_for(path):
        if path == ".claude/rules/project-status.md":
            return SEMANTIC_DIFF_PROJECT_STATUS
        return COSMETIC_DIFF_OVERVIEW

    assert not sync.is_sync_cosmetic_only(
        [
            ".claude/rules/project-status.md",
            ".claude/rules/project-overview.md",
        ],
        diff_for,
    )


def test_is_sync_cosmetic_only_empty_subset_returns_false(gov):
    sync, _ = gov
    assert not sync.is_sync_cosmetic_only([], lambda _path: "")


def test_evaluate_gate_silences_for_cosmetic_only(gov, tmp_path: Path):
    """Self-loop scenario from ADR 047 Background — feature PR + cosmetic sync edit."""

    _, gate = gov

    def diff_for(path):
        return (
            COSMETIC_DIFF_PROJECT_STATUS if path.endswith("project-status.md") else ""
        )

    result = gate.evaluate_gate(
        state_dir=tmp_path,
        changed_files=[
            "src/user/domain/services/user_service.py",
            ".claude/rules/project-status.md",
        ],
        pr_number=200,
        diff_source=diff_for,
    )
    assert result.status == "silent_sync_cosmetic"
    assert result.governor_changing is False


def test_evaluate_gate_triggers_when_governor_subset_has_non_carve_out(
    gov, tmp_path: Path
):
    """AGENTS.md + cosmetic project-status edit must still trigger."""

    _, gate = gov

    def diff_for(path):
        return (
            COSMETIC_DIFF_PROJECT_STATUS if path.endswith("project-status.md") else ""
        )

    result = gate.evaluate_gate(
        state_dir=tmp_path,
        changed_files=["AGENTS.md", ".claude/rules/project-status.md"],
        pr_number=300,
        diff_source=diff_for,
    )
    assert result.governor_changing is True
    assert result.status in ("missing", "match", "mismatch", "unknown")


def test_evaluate_gate_triggers_when_project_status_has_semantic_edit(
    gov, tmp_path: Path
):
    """Semantic edit to project-status.md is not cosmetic — must trigger."""

    _, gate = gov

    def diff_for(path):
        return SEMANTIC_DIFF_PROJECT_STATUS

    result = gate.evaluate_gate(
        state_dir=tmp_path,
        changed_files=[".claude/rules/project-status.md"],
        pr_number=301,
        diff_source=diff_for,
    )
    assert result.governor_changing is True


def test_evaluate_gate_silences_when_only_overview_last_synced(gov, tmp_path: Path):
    _, gate = gov

    def diff_for(path):
        return COSMETIC_DIFF_OVERVIEW

    result = gate.evaluate_gate(
        state_dir=tmp_path,
        changed_files=[".claude/rules/project-overview.md"],
        pr_number=302,
        diff_source=diff_for,
    )
    assert result.status == "silent_sync_cosmetic"
    assert result.governor_changing is False
