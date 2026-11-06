"""Context budgets must block factual growth without interpreting code examples."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "check_context_budget", ROOT / "tools/check_context_budget.py"
)
assert spec is not None and spec.loader is not None
budget = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = budget
spec.loader.exec_module(budget)


def check(tmp_path: Path, files: dict[str, str]):
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return budget.check_budget(tmp_path, files)


def test_agents_absolute_utf8_byte_cap(tmp_path):
    failures, _ = check(tmp_path, {"AGENTS.md": "é" * (budget.AGENTS_MAX // 2 + 1)})
    assert len(failures) == 1
    message = str(failures[0])
    assert "AGENTS.md:1:" in message
    assert str(budget.AGENTS_MAX + 2) in message
    assert str(budget.AGENTS_MAX) in message
    assert "docs/ai/shared/" in message


def test_rule_file_and_unconditional_total_caps(tmp_path):
    files = {"CLAUDE.md": "x" * budget.AUTOLOAD_MAX}
    files[".claude/rules/one.md"] = "x" * (budget.RULE_FILE_MAX + 1)
    failures, total = check(tmp_path, files)
    assert total > budget.AUTOLOAD_MAX
    assert {item.kind for item in failures} == {"file", "total auto-loaded"}


@pytest.mark.parametrize("frontmatter", ["paths: src/**", "paths:\n  - src/**"])
def test_scoped_rules_excluded_from_total_but_keep_file_cap(tmp_path, frontmatter):
    files = {
        "CLAUDE.md": "x" * budget.AUTOLOAD_MAX,
        ".claude/rules/scoped.md": f"---\n{frontmatter}\n---\n"
        + "x" * budget.RULE_FILE_MAX,
    }
    failures, total = check(tmp_path, files)
    assert total == budget.AUTOLOAD_MAX
    assert [item.kind for item in failures] == ["file"]


@pytest.mark.parametrize(
    "empty",
    [
        "[]",
        "[ ]",
        "[\"\", '']",
        "null",
        "Null",
        "NULL",
        "~",
        "''",
        '""',
        "\n  - ''\n  - \"\"",
    ],
)
def test_empty_paths_still_count_as_unscoped(tmp_path, empty):
    files = {".claude/rules/a.md": f"---\npaths: {empty}\n---\nhello\n"}
    _, total = check(tmp_path, files)
    assert total == len(files[".claude/rules/a.md"].encode())


def test_fenced_examples_do_not_trigger_line_caps(tmp_path):
    files = {
        ".claude/rules/project-status.md": (
            "# Status\n```markdown\n> Last synced: "
            + "x" * 220
            + "\n## Recent Major Changes\n| "
            + "x" * 320
            + " |\n```\n~~~\n> Last synced: "
            + "x" * 220
            + "\n~~~\n"
        )
    }
    assert check(tmp_path, files)[0] == []


def test_header_bytes_and_remediation(tmp_path):
    failures, _ = check(tmp_path, {".claude/rules/a.md": "> Last synced: " + "é" * 100})
    assert len(failures) == 1
    assert failures[0].line == 1
    assert "docs/history/archive/project-status/" in str(failures[0])


def test_row_cap_only_applies_to_recent_table(tmp_path):
    row = "| Feature | #1 | " + "x" * 310 + " |\n"
    source = (
        "## Another Table\n"
        + row
        + "## Recent Major Changes\n"
        + row
        + "## Next\n"
        + row
    )
    failures, _ = check(tmp_path, {".claude/rules/project-status.md": source})
    assert len(failures) == 1
    assert failures[0].line == 4
    assert "CHANGELOG" in str(failures[0])


def test_untracked_rules_cannot_change_scan(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "CLAUDE.md").write_text("# Instructions\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "CLAUDE.md"], check=True)
    extra = tmp_path / ".claude/rules/ignored.md"
    extra.parent.mkdir(parents=True)
    extra.write_text("x" * budget.AUTOLOAD_MAX)
    tracked = budget.tracked_paths(tmp_path)
    assert tracked == ["CLAUDE.md"]
    assert budget.check_budget(tmp_path, tracked)[0] == []
    subprocess.run(["git", "-C", str(tmp_path), "add", ".claude"], check=True)
    assert budget.check_budget(tmp_path, budget.tracked_paths(tmp_path))[0]


def test_missing_tracked_context_fails_closed(tmp_path):
    failures, _ = budget.check_budget(tmp_path, ["AGENTS.md"])
    assert [item.kind for item in failures] == ["read"]


def test_hook_pins_full_repository_blocking_scan():
    source = (ROOT / ".pre-commit-config.yaml").read_text()
    block = source.split("- id: context-budget\n", 1)[1].split("\n      - id:", 1)[0]
    assert "entry: python3 tools/check_context_budget.py" in block
    assert "pass_filenames: false" in block
    assert "always_run: true" in block
    assert "language: system" in block


def test_real_repository_scans_context():
    paths = budget.tracked_paths(ROOT)
    assert "AGENTS.md" in paths and "CLAUDE.md" in paths
    failures, total = budget.check_budget(ROOT, paths)
    assert total > 1000
    assert failures == [], "Run the closing sync through its own context budgets"


def test_unclosed_fence_cannot_hide_status_rows(tmp_path):
    failures, _ = check(
        tmp_path,
        {
            ".claude/rules/project-status.md": "```\n## Recent Major Changes\n| "
            + "x" * 400
        },
    )
    assert [item.kind for item in failures] == ["unclosed fence"]
    assert failures[0].line == 1


@pytest.mark.parametrize(
    "header",
    [
        "> Last synced: 2026-11-06 via #416 Prior: old history",
        "> Prior: old history",
        "> Last synced: 2026-11-06 (reviewed without change)",
    ],
)
def test_retrospective_headers_do_not_regrow_under_byte_cap(tmp_path, header):
    failures, _ = check(tmp_path, {".claude/rules/a.md": header})
    assert len(failures) == 1
    assert failures[0].line == 1


@pytest.mark.parametrize(
    "source",
    [
        "- Example:\n\n    ```markdown\n    > Prior: example\n   ```\n",
        "- Example:\n\n    ```markdown\n    > Prior: example\n    ```\n",
    ],
)
def test_list_nested_fences_stay_fences(tmp_path, source):
    assert check(tmp_path, {".claude/rules/a.md": source})[0] == []


def test_fence_indented_up_to_three_spaces_still_hides_examples(tmp_path):
    source = "1. Example:\n   ```markdown\n   > Prior: old history\n   ```\n"
    assert check(tmp_path, {".claude/rules/a.md": source})[0] == []


def test_second_sync_header_is_rejected(tmp_path):
    source = (
        "# Rules\n\n> Last synced: 2026-11-06 via #416\n\n"
        "> Last synced: 2026-11-05 via #415\n"
    )
    failures, _ = check(tmp_path, {".claude/rules/a.md": source})
    assert [(item.kind, item.line) for item in failures] == [
        ("duplicate sync header", 5)
    ]
