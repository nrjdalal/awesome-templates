"""Tests for tools/check_examples_copyflow.py (issue #260)."""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "check_examples_copyflow.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_examples_copyflow", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_examples_copyflow"] = module
    spec.loader.exec_module(module)
    return module


cec = _load_module()


def _write(tmp_path: Path, rel_path: str, content: str) -> Path:
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


class TestFindViolations:
    def test_absolute_examples_from_import_is_flagged(self, tmp_path):
        target = _write(
            tmp_path,
            "examples/todo/service.py",
            "from examples.todo.domain.dtos.todo_dto import TodoDTO\n",
        )

        violations = cec.find_violations(target, repo_root=tmp_path)

        assert len(violations) == 1
        assert violations[0].path == "examples/todo/service.py"
        assert violations[0].line_number == 1
        assert "examples.*" in violations[0].reason

    def test_plain_import_examples_is_flagged(self, tmp_path):
        target = _write(
            tmp_path,
            "examples/todo/service.py",
            "import examples.todo.domain\n",
        )

        violations = cec.find_violations(target, repo_root=tmp_path)

        assert len(violations) == 1

    def test_relative_and_src_imports_are_clean(self, tmp_path):
        target = _write(
            tmp_path,
            "examples/blog/post/service.py",
            "from src.author.domain.protocols.author_repository_protocol import (\n"
            "    AuthorRepositoryProtocol,\n"
            ")\n"
            "from src._core.domain.services.base_service import BaseService\n"
            "from ..dtos.post_dto import PostDTO\n"
            "from ...interface.server.schemas.post_schema import CreatePostRequest\n",
        )

        assert cec.find_violations(target, repo_root=tmp_path) == []

    def test_mentions_in_comments_and_docstrings_are_ignored(self, tmp_path):
        target = _write(
            tmp_path,
            "examples/todo/service.py",
            '"""Docs may say `from examples.todo import x` freely."""\n'
            "# from examples.todo.domain import TodoDTO\n"
            "VALUE = 'from examples.todo import literal'\n",
        )

        assert cec.find_violations(target, repo_root=tmp_path) == []

    def test_unparseable_file_is_reported(self, tmp_path):
        target = _write(tmp_path, "examples/todo/broken.py", "def broken(:\n")

        violations = cec.find_violations(target, repo_root=tmp_path)

        assert len(violations) == 1
        assert "unparseable" in violations[0].reason


class TestRun:
    def test_argv_mode_flags_violation(self, tmp_path, capsys):
        _write(
            tmp_path,
            "examples/todo/service.py",
            "from examples.todo.domain import TodoDTO\n",
        )

        exit_code = cec.run(["examples/todo/service.py"], repo_root=tmp_path)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "violations found" in captured.err
        assert "cp -r examples/<name> src/<name>" in captured.err

    def test_argv_mode_clean_file_passes(self, tmp_path, capsys):
        _write(
            tmp_path,
            "examples/todo/service.py",
            "from ..dtos.todo_dto import TodoDTO\n",
        )

        exit_code = cec.run(["examples/todo/service.py"], repo_root=tmp_path)

        assert exit_code == 0
        assert "0 violations" in capsys.readouterr().out

    def test_argv_mode_ignores_paths_outside_examples(self, tmp_path, capsys):
        _write(
            tmp_path,
            "tests/unit/todo/test_service.py",
            "from examples.todo.domain import TodoDTO\n",
        )

        exit_code = cec.run(["tests/unit/todo/test_service.py"], repo_root=tmp_path)

        assert exit_code == 0
        assert "0 violations across 0 scanned files" in capsys.readouterr().out


class TestRealRepo:
    def test_tracked_examples_have_no_violations(self):
        """The live guard: every git-tracked example file must stay clean."""
        exit_code = cec.run([], repo_root=REPO_ROOT)

        assert exit_code == 0

    def test_discovery_only_returns_tracked_python_files(self):
        files = cec.discover_tracked_example_files(REPO_ROOT)

        assert files, "expected tracked example files"
        assert all(path.suffix == ".py" for path in files)
        assert all("examples" in path.parts for path in files)
