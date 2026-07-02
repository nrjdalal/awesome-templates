"""Forbid absolute ``examples.*`` imports inside ``examples/`` (issue #260).

Every example is activated by copying it into ``src/``
(``cp -r examples/<name> src/<name>``), so example code must never import
through the ``examples.`` package path: intra-domain imports are
package-relative, and cross-domain imports reference ``src.<other>`` (the
post-copy layout). An absolute ``examples.*`` import survives the copy
textually but binds different class objects at runtime — dependency-injector
``Provide`` markers stop resolving (HTTP 500) and duplicate SQLAlchemy table
registration crashes the boot.

Scope: git-tracked ``*.py`` files under ``examples/`` (untracked local
scratch directories are ignored). Detection is AST-based so comments and
docstrings that merely mention ``examples.`` never false-positive.

Usage:
    python3 tools/check_examples_copyflow.py [FILE ...]

With no arguments, scans every git-tracked ``examples/**/*.py``. With
arguments (pre-commit passes changed files), scans only the given files
that live under ``examples/``.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_TOP_LEVEL = "examples"
_REASON = (
    "absolute `examples.*` import — use a package-relative import "
    "(intra-domain) or `src.<other_domain>` (cross-domain)"
)


@dataclass(frozen=True)
class Violation:
    path: str
    line_number: int
    line_content: str
    reason: str

    def format(self) -> str:
        return f"{self.path}:{self.line_number}: {self.reason}\n  {self.line_content!r}"


def _module_is_forbidden(module: str | None) -> bool:
    if not module:
        return False
    return module == FORBIDDEN_TOP_LEVEL or module.startswith(f"{FORBIDDEN_TOP_LEVEL}.")


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def find_violations(path: Path, *, repo_root: Path = REPO_ROOT) -> list[Violation]:
    rel = _relative_path(path, repo_root)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, ValueError) as exc:
        lineno = getattr(exc, "lineno", 0) or 0
        return [Violation(rel, lineno, "", f"unparseable file: {type(exc).__name__}")]

    lines = source.splitlines()
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if not any(_module_is_forbidden(alias.name) for alias in node.names):
                continue
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level > 0) are exactly the sanctioned pattern.
            if node.level or not _module_is_forbidden(node.module):
                continue
        else:
            continue
        line = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
        violations.append(Violation(rel, node.lineno, line, _REASON))
    return violations


def discover_tracked_example_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    result = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z", "--", "examples"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        repo_root / entry
        for entry in result.stdout.split("\0")
        if entry.endswith(".py")
    ]


def filter_to_examples(paths: list[Path], repo_root: Path) -> list[Path]:
    kept: list[Path] = []
    for path in paths:
        rel = _relative_path(path, repo_root)
        if rel.startswith("examples/") and rel.endswith(".py"):
            kept.append(path)
    return kept


def run(argv_paths: list[str], *, repo_root: Path = REPO_ROOT) -> int:
    if argv_paths:
        resolved = [
            Path(raw) if Path(raw).is_absolute() else repo_root / raw
            for raw in argv_paths
        ]
        candidates = filter_to_examples(resolved, repo_root)
    else:
        candidates = discover_tracked_example_files(repo_root)

    all_violations: list[Violation] = []
    for path in candidates:
        all_violations.extend(find_violations(path, repo_root=repo_root))

    if all_violations:
        print(
            f"Examples copy-flow violations found "
            f"({len(all_violations)} across "
            f"{len({v.path for v in all_violations})} files):",
            file=sys.stderr,
        )
        for violation in all_violations:
            print(violation.format(), file=sys.stderr)
        print(
            "\nExamples must survive `cp -r examples/<name> src/<name>` — "
            "see examples/README.md and issue #260.",
            file=sys.stderr,
        )
        return 1

    print(f"Examples copy-flow: 0 violations across {len(candidates)} scanned files.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
