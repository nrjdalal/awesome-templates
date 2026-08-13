"""A test must load the harness copy its name claims (#401).

Eight hook basenames exist in more than one harness directory — `verify_first.py`
and `completion_gate.py` in all three — so `import verify_first` after a
`sys.path.insert` is ambiguous, and `sys.modules` decides it. The suite leaves
those keys pointing at the Codex copies:

    verify_first     -> .codex/hooks/verify_first.py
    completion_gate  -> .codex/hooks/completion_gate.py

**No test was getting the wrong copy.** #401 was filed claiming they were, on a
misreading — the end state of `sys.modules` is not what an earlier test received —
and the tier-2 tests in `test_fail_open.py` had guarded themselves with a
`sys.modules.pop` plus `sys.path[0]`. What was missing is that nothing said so and
nothing enforced it: the next test to import a colliding basename without both
halves gets whichever copy is cached, and would pass while exercising another
harness. The two copies of `verify_first.py` differ by 228 lines.

**The pollution is not the tests' fault and cannot be fixed by renaming.** The hook
files import their own siblings by bare name — `.codex/hooks/completion_gate.py`
does `import _shared` and `import verify_first` — which is correct for a standalone
hook process, where one harness directory is on `sys.path`. It only collides inside
a shared pytest process that loads more than one harness's copies. So the invariant
this file pins is the one a test *can* control: load by path, never by bare name.

Two tests, in the order they matter:

1. No test in this directory imports a colliding harness basename. That is the
   structural rule; the AST check cannot be satisfied by accident.
2. The tier-2 fail-open tests actually receive `.claude/hooks` modules. That is the
   behaviour the rule exists to protect, checked directly rather than inferred.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTS_DIR = Path(__file__).resolve().parent
_HARNESS_DIRS = (
    _REPO_ROOT / ".claude" / "hooks",
    _REPO_ROOT / ".codex" / "hooks",
    _REPO_ROOT / ".antigravity" / "hooks",
)


def _colliding_basenames() -> set[str]:
    """Module names that exist in more than one harness directory."""
    seen: dict[str, int] = {}
    for directory in _HARNESS_DIRS:
        for path in directory.glob("*.py"):
            seen[path.stem] = seen.get(path.stem, 0) + 1
    return {stem for stem, count in seen.items() if count > 1}


def _real_loader():
    """`test_fail_open._load_claude_hook`, loaded by path.

    By path rather than `from test_fail_open import ...` so this guard does not
    depend on the directory being an importable package, and so the module it pulls
    in cannot be shadowed by anything already in `sys.modules`.
    """
    target = _TESTS_DIR / "test_fail_open.py"
    spec = importlib.util.spec_from_file_location("fail_open_under_guard", str(target))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fail_open_under_guard"] = module
    spec.loader.exec_module(module)
    loader = getattr(module, "_load_claude_hook", None)
    assert loader is not None, (
        "test_fail_open._load_claude_hook is gone — if the loading helper was "
        "renamed, point this guard at the new one; do not delete the check"
    )
    return loader


def test_more_than_one_harness_copy_exists() -> None:
    """The precondition. If this ever fails the rest of the file is moot."""
    colliding = _colliding_basenames()

    assert "verify_first" in colliding, (
        "verify_first no longer exists in multiple harness directories — if the "
        "copies were consolidated, this whole file can go"
    )
    assert len(colliding) >= 2, f"expected several colliding basenames, got {colliding}"


def test_no_test_imports_a_colliding_harness_module_by_name() -> None:
    """`import verify_first` cannot say which copy it means.

    Checked by AST rather than by grep, so a mention inside a docstring or a
    subprocess script string — both of which exist in this directory and are
    correct, because a subprocess gets its own `sys.modules` — does not count.
    """
    colliding = _colliding_basenames()
    offenders: list[str] = []

    for path in sorted(_TESTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in colliding:
                        offenders.append(
                            f"{path.name}:{node.lineno} import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module in colliding:
                offenders.append(
                    f"{path.name}:{node.lineno} from {node.module} import ..."
                )

    assert not offenders, (
        "these imports name a module that exists in more than one harness copy, so "
        f"`sys.modules` decides which one arrives: {offenders}. Load it by path "
        "instead — `importlib.util.spec_from_file_location('claude_verify_first', "
        "path)` — which is what the rest of this directory already does."
    )


@pytest.mark.parametrize(
    "stem", ["user_prompt_submit", "verify_first", "completion_gate"]
)
def test_claude_hooks_load_from_the_claude_directory(stem: str) -> None:
    """The behaviour the rule protects, for the three modules tier 2 exercises.

    Loading by path under a harness-qualified alias must yield a module whose
    `__file__` is the Claude copy, no matter what a previously-run test left in
    `sys.modules` under the bare name. Asserted on `__file__` because that is the
    thing a wrong resolution would silently change, and the reason a passing test
        is not evidence of which copy ran.
    """
    path = _REPO_ROOT / ".claude" / "hooks" / f"{stem}.py"
    assert path.is_file(), f"{path} is missing"

    # Poison the bare key first — this is the state a real suite run produces.
    # Saved and restored, not just popped: dropping a key another test cached would
    # let this guard mask the very misresolution it exists to catch. Same discipline
    # as `test_locale.py::_load_codex_completion_gate`.
    saved = sys.modules.get(stem)
    codex_copy = _REPO_ROOT / ".codex" / "hooks" / f"{stem}.py"
    if codex_copy.is_file():
        poisoned = importlib.util.spec_from_file_location(stem, str(codex_copy))
        assert poisoned is not None
        sys.modules[stem] = importlib.util.module_from_spec(poisoned)

    try:
        # The *real* loader, not a copy of it. Reproducing the correct logic here
        # would let `_load_claude_hook` regress to a dynamic `import_module(stem)` —
        # invisible to the AST rule above, since it is not an import statement —
        # while this test kept passing on its own private implementation.
        module = _real_loader()(stem)

        assert module.__file__ is not None
        assert Path(module.__file__).parent == path.parent, (
            f"loaded {module.__file__} while asking for {path} — path-based loading "
            "is supposed to be immune to whatever occupies the bare name"
        )
    finally:
        if isinstance(saved, ModuleType):
            sys.modules[stem] = saved
        else:
            sys.modules.pop(stem, None)
        sys.modules.pop(f"claude_{stem}", None)
