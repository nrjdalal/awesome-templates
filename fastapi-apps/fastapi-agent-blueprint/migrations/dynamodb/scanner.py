"""DynamoDB model auto-discovery scanner.

Scans domain directories for DynamoModel subclasses,
analogous to Alembic's model discovery for SQLAlchemy.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import DynamoModel


def scan_dynamo_models(src_root: Path) -> list[type[DynamoModel]]:
    """Discover all DynamoModel subclasses under ``src/`` domains.

    Scans ``{domain}/infrastructure/dynamodb/models/`` for each domain
    discovered by the same convention as ``discover_domains()``.
    """
    from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import (
        DynamoModel as BaseDynamoModel,
    )

    models: list[type[DynamoModel]] = []

    for domain_dir in sorted(src_root.iterdir()):
        if not domain_dir.is_dir():
            continue
        if domain_dir.name.startswith(("_", ".")):
            continue
        if not (domain_dir / "__init__.py").exists():
            continue

        models_dir = domain_dir / "infrastructure" / "dynamodb" / "models"
        if not models_dir.is_dir():
            continue

        for py_file in sorted(models_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            module_path = (
                str(py_file.relative_to(src_root.parent))
                .replace("/", ".")
                .removesuffix(".py")
            )

            try:
                module = importlib.import_module(module_path)
            except Exception as exc:
                print(f"  [WARN] Failed to import {module_path}: {exc}")
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseDynamoModel)
                    and attr is not BaseDynamoModel
                    and hasattr(attr, "__dynamo_meta__")
                ):
                    models.append(attr)

    return models
