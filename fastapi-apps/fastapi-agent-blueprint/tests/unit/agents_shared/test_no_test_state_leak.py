"""AST guard: no pytest fixture may write directly to real state dirs (PR-A.1).

Rationale: if a test fixture writes exception-token or verify-log markers to
the real ``.claude/state/``, ``.codex/state/``, or ``.antigravity/state/``
directories (not tmp_path), it poisons the production lifecycle and causes
the very stale-marker accumulation this PR is diagnosing.

This guard scans every ``tests/`` file for string literals that reference the
real state dir paths inside function bodies decorated with ``@pytest.fixture``.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTS_DIR = _REPO_ROOT / "tests"

# Patterns that, if found as string literals inside a fixture body, indicate
# a direct write to a real (non-tmp) state directory.
_FORBIDDEN_LITERAL_SUBSTRINGS = (
    ".claude/state",
    ".codex/state",
    ".antigravity/state",
)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _is_fixture_decorator(node: ast.expr) -> bool:
    """Return True if *node* is ``pytest.fixture`` or ``@fixture``."""
    if isinstance(node, ast.Attribute):
        return node.attr == "fixture"
    if isinstance(node, ast.Name):
        return node.id == "fixture"
    # @pytest.fixture(scope=...)
    if isinstance(node, ast.Call):
        return _is_fixture_decorator(node.func)
    return False


def _has_fixture_decorator(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_is_fixture_decorator(d) for d in func.decorator_list)


def _string_literals_in_node(node: ast.AST) -> list[str]:
    """Collect all string literal values found anywhere inside *node*."""
    literals: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            literals.append(child.value)
    return literals


def _scan_file(path: Path) -> list[str]:
    """Return a list of violation messages for *path*, empty if clean."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _has_fixture_decorator(node):
            continue

        literals = _string_literals_in_node(node)
        for literal in literals:
            for forbidden in _FORBIDDEN_LITERAL_SUBSTRINGS:
                if forbidden in literal:
                    try:
                        display = path.relative_to(_REPO_ROOT)
                    except ValueError:
                        display = path
                    violations.append(
                        f"{display}:{node.lineno}: fixture '{node.name}' "
                        f"references real state dir via literal {literal!r}"
                    )
                    break  # one report per literal

    return violations


def _scan_all_test_files() -> list[str]:
    violations: list[str] = []
    for py_file in _TESTS_DIR.rglob("*.py"):
        violations.extend(_scan_file(py_file))
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_fixture_writes_real_state_dir() -> None:
    """No pytest fixture in tests/ may reference a real state dir path."""
    violations = _scan_all_test_files()
    assert not violations, (
        "Fixture(s) reference real state dirs (use tmp_path instead):\n"
        + "\n".join(violations)
    )


def test_scanner_detects_bad_fixture(tmp_path: Path) -> None:
    """Self-test: scanner must flag a synthetic offending fixture."""
    bad_source = """\
import pytest

@pytest.fixture
def bad_fixture(tmp_path):
    state = tmp_path / ".claude/state"
    state.mkdir()
"""
    bad_file = tmp_path / "test_bad.py"
    bad_file.write_text(bad_source, encoding="utf-8")
    violations = _scan_file(bad_file)
    assert violations, "Scanner should have detected the .claude/state reference"
    assert ".claude/state" in violations[0]


def test_scanner_allows_tmp_path_only(tmp_path: Path) -> None:
    """Scanner must NOT flag fixtures that only use tmp_path (no real paths)."""
    good_source = """\
import pytest

@pytest.fixture
def good_fixture(tmp_path):
    state = tmp_path / "some_state"
    state.mkdir()
"""
    good_file = tmp_path / "test_good.py"
    good_file.write_text(good_source, encoding="utf-8")
    violations = _scan_file(good_file)
    assert not violations, f"False positive: {violations}"


def test_scanner_allows_real_path_outside_fixture(tmp_path: Path) -> None:
    """Real state dir references outside fixtures (e.g. in test helpers) are OK."""
    ok_source = """\
import pytest

REAL_DIR = ".claude/state"  # top-level constant — not a fixture

def test_something():
    path = ".codex/state/marker.json"
    assert path
"""
    ok_file = tmp_path / "test_ok.py"
    ok_file.write_text(ok_source, encoding="utf-8")
    violations = _scan_file(ok_file)
    assert not violations, f"False positive outside fixture: {violations}"


def test_scanner_flags_async_fixture(tmp_path: Path) -> None:
    """AST scanner covers async fixtures too."""
    async_source = """\
import pytest

@pytest.fixture
async def async_bad(tmp_path):
    return ".codex/state/foo.json"
"""
    async_file = tmp_path / "test_async.py"
    async_file.write_text(async_source, encoding="utf-8")
    violations = _scan_file(async_file)
    assert violations, "Scanner should flag async fixture with real state path"


def test_scanner_flags_antigravity_state_fixture(tmp_path: Path) -> None:
    """AST scanner covers Antigravity state paths too."""
    bad_source = """\
import pytest

@pytest.fixture
def bad_antigravity_fixture(tmp_path):
    return ".antigravity/state/foo.json"
"""
    bad_file = tmp_path / "test_antigravity_bad.py"
    bad_file.write_text(bad_source, encoding="utf-8")
    violations = _scan_file(bad_file)
    assert violations, "Scanner should flag fixture with Antigravity state path"
