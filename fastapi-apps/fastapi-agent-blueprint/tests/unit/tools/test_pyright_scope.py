"""Guard the pyright gate against silently shrinking.

pyright is the only type checker (#375) and the scope it checks is
`[tool.pyright] include`. Every failure mode of that arrangement is silent, which
is the whole reason this file exists:

- **Narrowing.** Replace an include path with a subset and pyright checks less,
  exits 0, and the gate shrinks with CI still green. It does not warn.
- **A dot-directory that is never analysed.** pyright's default `exclude` contains
  `**/.*`, so naming `.agents` in `include` without overriding `exclude` skips it
  entirely. Measured before this was fixed: `.claude/hooks` reported `0 errors`
  while analysing **0 of its 7 files**. "0 errors" and "nothing checked" print
  identically.
- **Losing `tests/`.** It joined the scope last (155 findings, cleared across
  #394–#399) and is the newest thing a future widening-under-pressure would drop
  first. Two of those findings were doubles that had silently stopped matching the
  protocols they impersonate, which is the coverage this buys.
- **Suppression creep.** `# pyright: ignore` is the other way to hold a tree at 0
  errors without fixing anything. 48 exist, in 26 files, each with its cause
  written at the call site. That is defensible *because* it is pinned; unpinned,
  it is a trend. #387 is the counter-example worth remembering: the three harness
  hook directories carried **88** `# type: ignore` comments, every one of them
  unnecessary, because they were written for a checker that had not run in two
  releases. None of them was replaced by a suppression.

The third one is the same illusion the retired mypy hook sustained for two
releases: it aborted on a duplicate module name, inspected nothing, and reported
one error — which nobody read as "no coverage".
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SRC = _REPO_ROOT / "src"

# Every suppression in the checked scope, by file and count. Each is a framework
# contract with its reason at the call site: dependency-injector's dynamic
# provider attributes (admin bootstrap, the demo-admin seeder), module-attribute
# injection, Starlette's `add_exception_handler` handler signature, a deliberately
# widened `on_send` parameter taskiq's base middleware does not declare, and the
# two `examples/blog` cross-domain imports that only resolve after the example is
# copied into `src/`.
#
# Adding an entry is allowed. Adding a suppression to a file that is *not* listed
# is what this pins — if it is a genuine third-party limitation, add the file and
# say why in the same commit; if it is not, fix the finding.
_ALLOWED_SUPPRESSIONS = {
    "examples/blog/post/domain/services/post_service.py": 1,
    "examples/blog/post/infrastructure/di/post_container.py": 1,
    "scripts/seed_demo_admin.py": 3,
    "src/_apps/admin/bootstrap.py": 6,
    "src/_apps/server/bootstrap.py": 3,
    "src/_core/domain/services/rag_pipeline.py": 1,
    "src/_core/infrastructure/admin/audit/logger.py": 2,
    "src/_core/infrastructure/admin/auth.py": 1,
    "src/_core/infrastructure/admin/error_handler.py": 2,
    "src/_core/infrastructure/logging/taskiq_middleware.py": 1,
    "tests/e2e/ai_usage/test_ai_usage_router.py": 1,
    "tests/unit/_apps/worker/test_task_bootstrap_order.py": 3,
    "tests/unit/_core/domain/value_objects/test_agent_usage_record.py": 1,
    "tests/unit/_core/exceptions/test_exception_handler_logging.py": 2,
    "tests/unit/_core/infrastructure/logging/test_retry_middleware_inline_broker.py": 1,
    "tests/unit/_core/infrastructure/notification/test_notification_adapters.py": 2,
    "tests/unit/_core/infrastructure/persistence/nosql/dynamodb/test_batch_semantics.py": 1,
    "tests/unit/_core/infrastructure/test_object_storage_list_files.py": 1,
    "tests/unit/_core/infrastructure/test_provider_error_curation.py": 3,
    "tests/unit/_core/infrastructure/vectors/s3/test_base_store.py": 1,
    "tests/unit/_core/test_dead_code_stays_deleted.py": 1,
    "tests/unit/agents_shared/test_antigravity_hardening.py": 1,
    "tests/unit/agents_shared/test_fail_open.py": 2,
    "tests/unit/agents_shared/test_harness_hook_surface.py": 1,
    "tests/unit/agents_shared/test_locale.py": 1,
    "tests/unit/blog/domain/test_post_service.py": 5,
}

# Matches a real directive, not a mention of one in prose. Pyright itself is this
# permissive — it reads a directive inside a comment even when it is only being
# quoted as an example, which is why the explanation in `admin/bootstrap.py` is
# worded to avoid containing one.
_SUPPRESSION = re.compile(r"#\s*pyright:\s*ignore")


def _pyright_config() -> dict:
    with _PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)["tool"]["pyright"]


def _include_paths() -> list[str]:
    return list(_pyright_config()["include"])


def _src_packages() -> list[str]:
    """Top-level importable packages under `src/`."""
    return sorted(
        child.name
        for child in _SRC.iterdir()
        if child.is_dir() and (child / "__init__.py").exists()
    )


# This file quotes the directive syntax in prose, and the scan below matches text
# rather than parsing comments — so it would count itself. Pyright is unaffected:
# a mention inside a docstring is a string, not a comment.
_SELF = Path(__file__).resolve()


def _checked_files() -> list[Path]:
    files: list[Path] = []
    for path in _include_paths():
        resolved = _REPO_ROOT / path
        if resolved.is_file():
            files.append(resolved)
        else:
            files.extend(sorted(resolved.rglob("*.py")))
    return [f for f in files if f.resolve() != _SELF]


def test_pyright_is_configured() -> None:
    config = _pyright_config()

    assert config["include"], "an empty include list checks the whole repo by accident"
    assert config["pythonVersion"] == "3.12"


def test_unnecessary_suppressions_are_an_error() -> None:
    """Otherwise a suppression outlives the limitation it was added for."""
    assert _pyright_config().get("reportUnnecessaryTypeIgnoreComment") == "error"


@pytest.mark.parametrize("path", _include_paths())
def test_every_include_path_exists(path: str) -> None:
    resolved = _REPO_ROOT / path

    assert resolved.exists(), (
        f"[tool.pyright] include lists {path!r}, which no longer exists. "
        "pyright does not error on a missing include — it just checks less, "
        "so the CI type gate would shrink without anything going red."
    )
    if resolved.is_dir():
        assert any(resolved.rglob("*.py")), f"{path!r} contains no Python to check"


def test_the_shared_governor_package_is_on_the_resolution_path() -> None:
    """`extraPaths` is what makes the harness hooks checkable at all (#387).

    The hooks insert `.agents/shared` on `sys.path` at import time, so
    `harness_debug` and `governor.*` are top-level names no static resolver finds
    on its own. Dropping this line does surface as 70 unresolved-import errors
    rather than silence — but the tempting way to quiet those is to relax
    `reportMissingImports`, which would also blind the gate to a genuinely missing
    module. This says which of the two is the fix.
    """
    assert ".agents/shared" in _pyright_config().get("extraPaths", []), (
        "the harness hooks and tools/check_governor_footer.py resolve their shared "
        "imports through this path; without it 70 imports go unresolved"
    )


def test_dot_directory_includes_require_an_explicit_exclude() -> None:
    """The trap: a dot-path in `include` is skipped unless `exclude` is overridden.

    pyright's default `exclude` is `["**/node_modules", "**/__pycache__", "**/.*"]`
    and specifying any `exclude` replaces it. So `.agents` is only really checked
    because `exclude` is set and omits `**/.*`. Without this test the config could
    lose its `exclude` line and the dot-path coverage would vanish in silence —
    same error count, fewer files.
    """
    config = _pyright_config()
    dotted = [p for p in _include_paths() if p.startswith(".")]
    if not dotted:
        pytest.skip("no dot-directory include paths to protect")

    assert "exclude" in config, (
        f"include names {dotted}, but `exclude` is unset — pyright's default "
        "`**/.*` then skips those paths while still reporting 0 errors"
    )
    assert "**/.*" not in config["exclude"], (
        f"`exclude` contains `**/.*`, which cancels the {dotted} include paths"
    )


@pytest.mark.parametrize("package", _src_packages())
def test_every_src_package_is_covered(package: str) -> None:
    """Narrowing `src` to a subset has to fail here.

    Asserted per package rather than as `include == [...]` so that adding roots
    stays legal — only losing coverage fails.
    """
    covered = [
        path
        for path in _include_paths()
        if path == "src" or path.split("/")[:2] == ["src", package]
    ]

    assert covered, (
        f"src/{package} is not covered by [tool.pyright] include "
        f"{_include_paths()!r}. The type gate reached 0 errors across the whole "
        "scope; excluding a package to get past its errors gives that up "
        "silently, because pyright exits 0 on a narrower scope."
    )


@pytest.mark.parametrize(
    "path",
    [
        "tools",
        "scripts",
        "examples",
        ".agents",
        "run_scheduler_local.py",
        "tests",
        ".claude/hooks",
        ".antigravity/hooks",
        ".codex/hooks",
    ],
)
def test_the_scope_mypy_nominally_covered_stays_covered(path: str) -> None:
    """Retiring mypy (#375) must not quietly reduce what is checked.

    The retired hook nominally covered everything except `migrations/`, `tests/`
    and the root `run_*.py` files — nominally, because it aborted before reading
    any of it. `run_scheduler_local.py` is in this list because including it is
    what found that `make scheduler` never ran the scheduler.
    """
    assert path in _include_paths(), (
        f"{path!r} left [tool.pyright] include. pyright is the only type checker "
        "since #375, so dropping a path here means nothing checks it at all."
    )


def test_suppressions_stay_where_they_are_accounted_for() -> None:
    found: dict[str, int] = {}
    for path in _checked_files():
        count = len(_SUPPRESSION.findall(path.read_text(encoding="utf-8")))
        if count:
            found[str(path.relative_to(_REPO_ROOT))] = count

    assert found == _ALLOWED_SUPPRESSIONS, (
        f"pyright suppressions changed: expected {_ALLOWED_SUPPRESSIONS}, found "
        f"{found}. A suppression is the other way to keep the tree at 0 errors "
        "without fixing anything, so each one is accounted for by file and count. "
        "If the new one is a genuine framework limitation, add it here with its "
        "reason; if it is not, fix the finding instead."
    )
