"""`make quickstart` must keep telling a developer what it just uninstalled.

`uv sync --extra admin` installs exactly that, so every other extra — aws, otel,
pydantic-ai, sqs, rabbitmq — is uninstalled. That is correct for a first-time user
and a trap inside a dev checkout: `pytest tests/` then aborts during collection
(two modules import `aioboto3`) and `uv run pyright` reports 47 unresolved imports.
The `dev` group itself survives, because uv syncs default groups regardless of
`--extra` — which is why the first version of this guard probed for `pytest` and
never fired.

The target detects the case rather than warning everyone, by checking whether a
module that only a *removed* extra provides was present before the sync and gone
after. That detection has one assumption, and it is silent when it breaks: if the
probe module ever ships in the core dependencies or in the `admin` extra, it is
installed either way, the before/after comparison never flips, and the warning
disappears without any test going red.

This file pins the assumption, not the wording.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE = _REPO_ROOT / "Makefile"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# The extra `make quickstart` does install. Anything the probe relies on must not
# come from here, or from the core dependency list.
_QUICKSTART_EXTRA = "admin"


def _quickstart_recipe() -> str:
    body = _MAKEFILE.read_text()
    start = body.index("\nquickstart:")
    # A recipe ends at the first line that is neither indented nor blank.
    lines = body[start + 1 :].splitlines()
    out = [lines[0]]
    for line in lines[1:]:
        if line and not line.startswith(("\t", " ")):
            break
        out.append(line)
    return "\n".join(out)


def _pyproject() -> dict:
    with _PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def _probe_module() -> str:
    """The module name the recipe uses to detect a pre-existing dev environment."""
    match = re.search(r"site-packages/([A-Za-z0-9_]+)", _quickstart_recipe())
    assert match, (
        "the quickstart recipe no longer probes site-packages for a removed "
        "extra, so a developer gets no warning that this sync uninstalled the "
        "aws / otel / pydantic-ai extras out from under their tooling"
    )
    return match.group(1)


def test_the_recipe_still_warns_after_syncing() -> None:
    recipe = _quickstart_recipe()

    assert "uv sync --extra admin" in recipe, "the recipe stopped syncing"
    assert "make setup" in recipe, (
        "the warning must name the command that restores the extras; a warning "
        "without the fix is just noise"
    )


def test_the_probe_module_is_not_installed_by_quickstart() -> None:
    """The assumption that makes the before/after comparison mean anything."""
    probe = _probe_module()
    data = _pyproject()
    core = data["project"]["dependencies"]
    quickstart_extra = data["project"]["optional-dependencies"][_QUICKSTART_EXTRA]

    for where, requirements in (
        ("core dependencies", core),
        ("the admin extra", quickstart_extra),
    ):
        offenders = [
            r for r in requirements if r.split(">")[0].split("[")[0].strip() == probe
        ]
        assert not offenders, (
            f"{probe!r} is in {where} ({offenders}), so `make quickstart` installs "
            "it either way. The recipe's before/after check can never flip and the "
            "warning is dead — probe a module that only a removed extra provides."
        )


def test_the_probe_module_comes_from_an_extra_quickstart_removes() -> None:
    probe = _probe_module()
    extras = _pyproject()["project"]["optional-dependencies"]

    providers = [
        name
        for name, reqs in extras.items()
        if any(r.split(">")[0].split("[")[0].strip() == probe for r in reqs)
    ]
    assert providers, (
        f"{probe!r} is not declared by any extra, so nothing guarantees it is "
        "present in a dev environment and absent after the quickstart sync"
    )
    assert _QUICKSTART_EXTRA not in providers, (
        f"{probe!r} is provided by the {_QUICKSTART_EXTRA!r} extra, which "
        "quickstart installs"
    )


@pytest.mark.parametrize("group", ["dev"])
def test_the_probe_is_not_a_default_group_dependency(group: str) -> None:
    """uv syncs default groups regardless of `--extra`.

    This is the exact mistake the first version of the guard made: it probed for
    `pytest`, which survives the sync, so the warning never appeared.
    """
    probe = _probe_module()
    groups = _pyproject().get("dependency-groups", {})
    reqs = groups.get(group, [])

    offenders = [r for r in reqs if r.split(">")[0].split("[")[0].strip() == probe]
    assert not offenders, (
        f"{probe!r} is in the {group!r} dependency group, which uv keeps on every "
        "`uv sync`. It cannot signal that anything was removed."
    )
