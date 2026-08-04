"""Guard the pyright allow-list against silent shrinkage.

The CI type check is blocking but scoped: `[tool.pyright] include` lists the
packages that are clean today rather than all of `src/`, which reports 58
errors. That trade is only honest while the list means something.

Two ways it stops meaning anything, both silent:

- A path is renamed or removed and pyright quietly checks less. It still exits
  0, CI still passes, and nobody notices the gate shrank.
- The list is emptied. pyright with an empty `include` checks the whole
  execution root, which would fail — but an intermediate state where the list
  drops to one leftover package would not.

These tests fail loudly in both cases. They deliberately do not assert *which*
packages are listed: widening the list is the goal, and a test that has to be
edited for every widening is a tax on the thing it is meant to encourage.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _pyright_config() -> dict:
    with _PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)["tool"]["pyright"]


def _include_paths() -> list[str]:
    return list(_pyright_config()["include"])


def test_pyright_is_configured() -> None:
    config = _pyright_config()

    assert config["include"], "an empty include list checks the whole repo by accident"
    assert config["pythonVersion"] == "3.12"


@pytest.mark.parametrize("path", _include_paths())
def test_every_include_path_exists(path: str) -> None:
    resolved = _REPO_ROOT / path

    assert resolved.is_dir(), (
        f"[tool.pyright] include lists {path!r}, which no longer exists. "
        "pyright does not error on a missing include — it just checks less, "
        "so the CI type gate would shrink without anything going red."
    )


@pytest.mark.parametrize("path", _include_paths())
def test_every_include_path_holds_python(path: str) -> None:
    resolved = _REPO_ROOT / path

    assert any(resolved.rglob("*.py")), f"{path!r} contains no Python to check"
