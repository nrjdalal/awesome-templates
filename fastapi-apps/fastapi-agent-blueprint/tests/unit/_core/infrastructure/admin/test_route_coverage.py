"""AST-based test: every @ui.page("/admin/...") route must call an auth gate.

Exempt routes (with justification):
  /admin/login   — this IS the auth entry point; no gate needed
  /admin/setup   — guarded by setup_granted session flag (ephemeral bootstrap gate,
                   not a regular auth gate; only reachable via login redirect)
"""

from __future__ import annotations

import ast
import pathlib

_SRC_ROOT = pathlib.Path("src")

_AUTH_GATE_NAMES = frozenset({"require_auth", "require_auth_allowlisted"})

# Routes that intentionally have no require_auth call (with documented reason above).
_EXEMPT_ROUTES: frozenset[str] = frozenset({"/admin/login", "/admin/setup"})


def _collect_admin_routes(filepath: pathlib.Path) -> list[tuple[str, bool]]:
    """Return (route_path, has_auth_gate) for each @ui.page("/admin/...") handler."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    results: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in node.decorator_list:
            route = _extract_ui_page_route(decorator)
            if route is None or not route.startswith("/admin/"):
                continue
            results.append((route, _body_has_auth_gate(node)))
    return results


def _extract_ui_page_route(decorator: ast.expr) -> str | None:
    """Return the first string argument of @ui.page(...), or None."""
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not (isinstance(func, ast.Attribute) and func.attr == "page"):
        return None
    if not decorator.args:
        return None
    first = decorator.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _body_has_auth_gate(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the function body contains a call to any auth gate function."""
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _AUTH_GATE_NAMES:
            return True
        if isinstance(func, ast.Attribute) and func.attr in _AUTH_GATE_NAMES:
            return True
    return False


def _find_admin_page_files() -> list[pathlib.Path]:
    return [
        p
        for p in _SRC_ROOT.rglob("*.py")
        if "admin" in p.parts and "pages" in p.parts and "__init__" not in p.name
    ]


def test_every_admin_route_has_auth_gate():
    """No /admin/... route is reachable without going through an auth gate."""
    ungated: list[str] = []

    for filepath in _find_admin_page_files():
        for route, has_gate in _collect_admin_routes(filepath):
            if route in _EXEMPT_ROUTES:
                continue
            if not has_gate:
                ungated.append(f"{filepath}: {route}")

    assert not ungated, (
        "The following /admin routes are missing an auth gate "
        "(require_auth or require_auth_allowlisted):\n  " + "\n  ".join(ungated)
    )


def test_exempt_routes_are_still_registered_as_ui_pages():
    """Sanity: exempt routes must actually exist as @ui.page routes."""
    found_routes: set[str] = set()
    for filepath in _find_admin_page_files():
        for route, _ in _collect_admin_routes(filepath):
            found_routes.add(route)

    for exempt_route in _EXEMPT_ROUTES:
        assert exempt_route in found_routes, (
            f"Exempt route {exempt_route!r} is listed as exempt but is not registered "
            "as a @ui.page. Update _EXEMPT_ROUTES if the route was removed."
        )
