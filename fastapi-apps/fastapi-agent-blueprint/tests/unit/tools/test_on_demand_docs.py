"""Protect the lightweight documentation's ownership and load boundaries."""

from __future__ import annotations

import ast
import fnmatch
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_commands_are_consulted_and_remain_language_governed(monkeypatch):
    assert not (ROOT / ".claude/rules/commands.md").exists()
    commands = ROOT / "docs/ai/shared/commands.md"
    assert commands.is_file()
    assert "## Run" in commands.read_text()
    name = "on_demand_language_checker"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools/check_language_policy.py"
    )
    assert spec and spec.loader
    checker = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, checker)
    spec.loader.exec_module(checker)
    assert commands.resolve() in checker.discover_tier1_paths(ROOT)


SCOPE_CASES = {
    "architecture-conventions.md": {
        "src/user/domain/services/user_service.py": True,
        "examples/todo/domain/services/todo_service.py": True,
        "tests/unit/test_example.py": True,
        "migrations/versions/001_example.py": True,
        "README.md": False,
        "docs/ai/shared/project-dna.md": False,
        "Makefile": False,
    },
    "project-overview.md": {
        "src/_apps/server/bootstrap.py": True,
        "src/_core/config.py": True,
        "src/_core/infrastructure/di/core_container.py": True,
        "_env/local.env.example": True,
        "pyproject.toml": True,
        "docker-compose.local.yml": True,
        "Makefile": True,
        "run_worker_local.py": True,
        "README.md": False,
        "docs/ai/shared/project-dna.md": False,
        "tests/unit/test_example.py": False,
        "src/user/domain/services/user_service.py": False,
    },
}


@pytest.mark.parametrize(
    ("filename", "source", "expected"),
    [
        (filename, source, expected)
        for filename, cases in SCOPE_CASES.items()
        for source, expected in cases.items()
    ],
)
def test_context_projection_scope_smoke_cases(filename, source, expected):
    """Smoke-test simple globs with fnmatch, not the native Claude matcher."""
    content = (ROOT / ".claude/rules" / filename).read_text()
    assert content.startswith("---\n")
    paths = yaml.safe_load(content.split("---", 2)[1])["paths"]
    assert any(fnmatch.fnmatchcase(source, pattern) for pattern in paths) is expected


def test_each_declared_scope_pattern_has_a_positive_case():
    for filename, cases in SCOPE_CASES.items():
        content = (ROOT / ".claude/rules" / filename).read_text()
        paths = yaml.safe_load(content.split("---", 2)[1])["paths"]
        for pattern in paths:
            assert any(
                expected and fnmatch.fnmatchcase(source, pattern)
                for source, expected in cases.items()
            ), (filename, pattern)


def test_admin_read_audit_identifier_matches_the_source_field():
    source = (ROOT / "src/_core/infrastructure/admin/base_admin_page.py").read_text()
    fields = {
        node.target.id: node.value.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert fields["log_reads"] is False
    text = (ROOT / "docs/ai/shared/project-dna.md").read_text()
    assert "`log_reads=False`" in text
    assert "audit_reads" not in text


def test_project_dna_preserves_section_numbers_and_non_derivable_policy():
    current = (ROOT / "docs/ai/shared/project-dna.md").read_text()
    historical = (
        ROOT / "docs/history/archive/harness-context/project-dna.md"
    ).read_text()
    assert len(current.encode("utf-8")) <= 49_152
    assert re.findall(r"^## §.*$", current, re.M) == re.findall(
        r"^## §.*$", historical, re.M
    )
    policy_start = "| Component | Provider Type | Notes |"
    policy_end = "### App-level Container (Auto-discovery)"
    assert (
        current.split(policy_start)[1].split(policy_end)[0]
        == historical.split(policy_start)[1].split(policy_end)[0]
    )
    guardrails = current.split("### Prompt-injection guardrails (#197)")[1].split(
        "## §15."
    )[0]
    for obligation in (
        "escape_for_prompt_xml",
        "Final[LiteralString]",
        "detect_prompt_injection",
        "scan_pii",
        "GUARDRAILS_ENABLED",
        "is_guardrail_block",
        "capture.set_result",
        "Document.trust_level",
    ):
        assert obligation in guardrails


def test_sample_workflow_traces_remain_live():
    current = (ROOT / "docs/ai/shared/target-operating-model.md").read_text()
    assert "## Appendix B — Sample Workflow Traces" in current
    for trace in range(1, 5):
        assert f"### Trace {trace}" in current
    assert "## Appendix A" not in current
    assert "## Appendix C" not in current
