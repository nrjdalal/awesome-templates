"""AST-based test: every @ui.page("/admin/...") route must call an auth gate.

Exempt routes (with justification):
  /admin/login   — this IS the auth entry point; no gate needed
  /admin/setup   — guarded by setup_granted session flag (ephemeral bootstrap gate,
                   not a regular auth gate; only reachable via login redirect)
  /admin/error   — critical-failure page (#195); a critical error may be a DB/auth
                   outage and the auth gate hits the DB, so gating here would loop.
                   Shows only a generic message + validated correlation id; no DB,
                   no session mutation, no sensitive data.
"""

from __future__ import annotations

import ast
import pathlib

_SRC_ROOT = pathlib.Path("src")

_AUTH_GATE_NAMES = frozenset({"require_auth", "require_auth_allowlisted"})

# Routes that intentionally have no require_auth call (with documented reason above).
_EXEMPT_ROUTES: frozenset[str] = frozenset(
    {"/admin/login", "/admin/setup", "/admin/error"}
)


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


def _is_auth_gate_call(value: ast.expr | None) -> bool:
    """True if ``value`` is a (possibly awaited) call to an auth-gate function."""
    if isinstance(value, ast.Await):
        value = value.value
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    if isinstance(func, ast.Name) and func.id in _AUTH_GATE_NAMES:
        return True
    return isinstance(func, ast.Attribute) and func.attr in _AUTH_GATE_NAMES


def _body_has_auth_gate(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the auth gate is the FIRST real statement (after any docstring).

    Stronger than "exists somewhere": project-dna requires ``require_auth*`` to
    be the first statement of every gated /admin route, so nothing renders
    before the gate. Accepts ``session = await require_auth(...)`` (Assign) or a
    bare ``await require_auth(...)`` (Expr)."""
    body = list(func_node.body)
    # Skip a leading docstring.
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body:
        return False
    first = body[0]
    if isinstance(first, (ast.Assign, ast.AnnAssign)):
        return _is_auth_gate_call(first.value)
    if isinstance(first, ast.Expr):
        return _is_auth_gate_call(first.value)
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


# ── #195: raw-exception leakage guard ──────────────────────────────────────

# Variable names that conventionally hold a caught exception. A ui.notify that
# interpolates one of these is leaking internal detail to the operator.
_EXC_VAR_NAMES = frozenset({"exc", "e", "err", "error", "exception"})


def _is_ui_notify(func: ast.expr) -> bool:
    return isinstance(func, ast.Attribute) and func.attr == "notify"


def _is_str_call(arg: ast.expr) -> bool:
    return (
        isinstance(arg, ast.Call)
        and isinstance(arg.func, ast.Name)
        and arg.func.id == "str"
    )


def _is_exception_fstring(arg: ast.expr) -> bool:
    if not isinstance(arg, ast.JoinedStr):
        return False
    return any(
        isinstance(value, ast.FormattedValue)
        and isinstance(value.value, ast.Name)
        and value.value.id in _EXC_VAR_NAMES
        for value in arg.values
    )


def _find_notify_leaks(filepath: pathlib.Path) -> list[str]:
    """Return 'file:line' for each ui.notify that leaks a raw exception."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    leaks: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_ui_notify(node.func)):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if _is_str_call(first) or _is_exception_fstring(first):
            leaks.append(f"{filepath}:{node.lineno}")
    return leaks


def test_admin_pages_do_not_leak_raw_exception_to_ui():
    """#195: ui.notify must never surface str(exc) or an exception f-string.

    Sanitized messages flow through AdminErrorHandler instead, so the raw
    exception text reaches the structured server log only.
    """
    leaks: list[str] = []
    for filepath in _find_admin_page_files():
        leaks.extend(_find_notify_leaks(filepath))

    assert not leaks, (
        "ui.notify must not surface a raw exception (use AdminErrorHandler.handle "
        "or a sanitized message):\n  " + "\n  ".join(leaks)
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
