import ast
from pathlib import Path

ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "collections",
    "contextlib",
    "datetime",
    "decimal",
    "time",
    "typing",
    "structlog",
}
ALLOWED_SRC_PREFIXES = ("src._core.domain",)


def test_usage_tracker_does_not_import_provider_or_ai_usage_domain():
    source = Path("src/_core/application/usage_tracker.py").read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] in ALLOWED_IMPORT_ROOTS
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "src":
                imported_names = {alias.name for alias in node.names}
                assert "ai_usage" not in imported_names
                continue
            if module.startswith("src."):
                assert module.startswith(ALLOWED_SRC_PREFIXES)
                continue
            assert module.split(".", 1)[0] in ALLOWED_IMPORT_ROOTS
