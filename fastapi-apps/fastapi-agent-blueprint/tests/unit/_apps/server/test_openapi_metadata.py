"""Contract tests for the OpenAPI metadata served at `/docs`.

Two independent drifts made this file necessary, and both were visible to every
anonymous visitor of the running server rather than only to contributors:

1. `description=` advertised "MCP server". No MCP surface exists anywhere in the
   repo — no `mcp`/`fastmcp`/`modelcontextprotocol` dependency, no module, no
   route. It is issue #18, tracked as roadmap in `README.md` and unchecked in
   `docs/reference.md`. Only the OpenAPI string presented it as shipped.
2. `version=` said `1.0.0` while `pyproject.toml` said `0.9.0`. The two had
   never agreed; the release process bumps `pyproject.toml` and the `CHANGELOG`,
   and nothing pointed back at this call site.

The version cannot be resolved at runtime: `pyproject.toml` declares no
`[build-system]`, so the project is never installed as a distribution and
`importlib.metadata.version("fastapi-agent-blueprint")` raises
`PackageNotFoundError` under both `uv run` and an activated `.venv`. Reading and
parsing `pyproject.toml` at import time to avoid one literal would put file I/O
in the server's import path, so the literal stays and this test is the guard.

Scope note: these assert the *metadata contract* only. Route-level OpenAPI shape
is covered by the per-domain router tests.

These read the module-level ``app`` rather than calling ``create_app()``. With
the ``admin`` extra installed, ``create_app`` reaches ``ui.run_with``, and
NiceGUI's ``core.app`` is a process-wide singleton that refuses
``add_middleware`` once it has been started — so a second ``create_app()`` in a
worker that already imported the app raises. The failure is order-dependent:
these tests pass alone and fail in the full suite. ``import app`` is the
pattern the rest of the suite uses (see
``tests/integration/_core/test_minimal_install.py``) and it asserts against the
object actually served.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from src._apps.server.app import app

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# Substrings that must never reappear in the public API description. Each names
# a capability the repo does not ship; see the module docstring.
_UNSHIPPED_CAPABILITIES = ("mcp", "fastmcp", "modelcontextprotocol")


def _pyproject_version() -> str:
    with _PYPROJECT.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def test_openapi_version_matches_pyproject() -> None:
    assert app.version == _pyproject_version()


def test_openapi_description_advertises_no_unshipped_capability() -> None:
    description = (app.description or "").lower()

    for capability in _UNSHIPPED_CAPABILITIES:
        assert capability not in description, (
            f"OpenAPI description advertises {capability!r}, which the repo does "
            f"not ship (issue #18). Description: {app.description!r}"
        )


def test_openapi_title_is_the_project_name() -> None:
    assert app.title == "FastAPI Agent Blueprint"


def test_pyproject_version_is_semver() -> None:
    # A malformed version here would make the equality test above pass for the
    # wrong reason (both sides equally wrong).
    assert re.fullmatch(r"\d+\.\d+\.\d+", _pyproject_version())
