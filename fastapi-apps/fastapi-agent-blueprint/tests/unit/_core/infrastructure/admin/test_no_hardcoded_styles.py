"""AST guard: admin pages must use centralized theme classes, not hardcoded
Quasar/Tailwind color classes or inline grid heights (#193).

Scope: every ``@ui.page`` admin page file PLUS the two shared shell modules
(``layout.py``, ``base_admin_page.py``) that previously held hardcoded colors.
``theme.py`` is the single allowed home for raw color/metric values and is
excluded.

Pure AST + regex (no nicegui import) so it runs under ``make check-core``
regardless of the ``admin`` extra.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

_SRC_ROOT = pathlib.Path("src")

# Named Quasar palette colors. Hardcoding any of these (with or without a
# numeric shade) bypasses the theme tokens and does not flip in dark mode.
# Semantic classes (``text-negative`` / ``text-warning`` / ``color=primary``)
# resolve via the ``--q-*`` vars and are intentionally NOT listed here.
# Order matters: longer names precede the prefixes they contain (e.g.
# ``light-blue`` before ``blue``, ``blue-grey`` before ``grey``).
_PALETTE = (
    r"(?:red|pink|deep-purple|purple|indigo|light-blue|blue-grey|blue-gray|blue"
    r"|cyan|teal|light-green|green|lime|yellow|amber|deep-orange|orange|brown"
    r"|grey|gray)"
)
_COLOR_CLASS_RE = re.compile(rf"\b(?:bg|text|border)-{_PALETTE}(?:-\d+)?\b")

# Inline grid height, e.g. ``.style("height: 600px")``. Note skeleton sizing uses
# the ``height="44px"`` kwarg form (a bare "44px" literal, no "height:" prefix),
# which is intentionally NOT matched here.
_INLINE_HEIGHT_RE = re.compile(r"height:\s*\d+px")

# Shared shell modules to guard in addition to the page files.
_EXTRA_GUARDED = (
    _SRC_ROOT / "_core" / "infrastructure" / "admin" / "layout.py",
    _SRC_ROOT / "_core" / "infrastructure" / "admin" / "base_admin_page.py",
)


def _find_admin_page_files() -> list[pathlib.Path]:
    return [
        p
        for p in _SRC_ROOT.rglob("*.py")
        if "admin" in p.parts and "pages" in p.parts and "__init__" not in p.name
    ]


_COMPONENTS_DIR = _SRC_ROOT / "_core" / "infrastructure" / "admin" / "components"


def _guarded_files() -> list[pathlib.Path]:
    files = _find_admin_page_files()
    files.extend(p for p in _EXTRA_GUARDED if p.exists())
    # The design-system component library is the single place tokens become
    # elements — guard it too (glob so new submodules are covered automatically).
    files.extend(p for p in _COMPONENTS_DIR.rglob("*.py") if "__init__" not in p.name)
    return files


def _string_literals(source: str):
    """Yield (lineno, value) for every string literal, including the static
    text parts of f-strings (which ``ast.walk`` exposes as ``ast.Constant``)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def _find_style_violations(filepath: pathlib.Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    violations: list[str] = []
    for lineno, value in _string_literals(source):
        if _COLOR_CLASS_RE.search(value):
            violations.append(
                f"{filepath}:{lineno}: hardcoded color class -> {value!r}"
            )
        if _INLINE_HEIGHT_RE.search(value):
            violations.append(f"{filepath}:{lineno}: inline grid height -> {value!r}")
    return violations


def test_admin_pages_have_no_hardcoded_styles():
    """No admin page (or shared shell module) hardcodes brand colors or grid
    heights — they must reference AdminClasses / AdminMetrics from theme.py."""
    violations: list[str] = []
    for filepath in _guarded_files():
        violations.extend(_find_style_violations(filepath))

    assert not violations, (
        "Hardcoded styles found — use theme.py AdminClasses / AdminMetrics:\n  "
        + "\n  ".join(violations)
    )


def test_theme_module_is_not_in_guard_scope():
    """theme.py is the single allowed home for raw values; it must be excluded."""
    theme_path = _SRC_ROOT / "_core" / "infrastructure" / "admin" / "theme.py"
    assert theme_path.exists()
    assert theme_path not in _guarded_files()


# ── Detector unit tests (self-check the guard logic) ──


@pytest.mark.parametrize(
    "snippet",
    [
        'ui.icon("a").classes("text-blue-800")',
        'ui.label("x").classes("text-orange")',  # named color, no shade
        'ui.card().classes("bg-light-blue-1")',
        'ui.label("y").classes("text-blue-grey-7")',
    ],
)
def test_detector_flags_planted_color_class(tmp_path: pathlib.Path, snippet: str):
    bad = tmp_path / "bad_page.py"
    bad.write_text(snippet + "\n", encoding="utf-8")
    assert _find_style_violations(bad)


def test_detector_flags_planted_grid_height(tmp_path: pathlib.Path):
    bad = tmp_path / "bad_grid.py"
    bad.write_text('g = ui.aggrid({}).style("height: 600px")\n', encoding="utf-8")
    assert _find_style_violations(bad)


def test_detector_allows_theme_and_semantic_classes(tmp_path: pathlib.Path):
    """Theme classes, Quasar semantic colors, and skeleton heights are allowed."""
    good = tmp_path / "good_page.py"
    good.write_text(
        'a = ui.element().classes("admin-grid admin-text-muted")\n'
        'b = ui.label("x").classes("text-negative text-warning text-positive")\n'
        'c = ui.label("y").classes("text-h5 text-caption text-weight-bold")\n'
        'd = ui.skeleton(type="rect", width="100%", height="44px")\n',
        encoding="utf-8",
    )
    assert _find_style_violations(good) == []
