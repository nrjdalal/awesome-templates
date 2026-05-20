"""S3 Vectors model auto-discovery scanner.

Scans domain directories for VectorModel subclasses,
analogous to the DynamoDB model scanner.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src._core.infrastructure.vectors.vector_model import VectorModel


def scan_s3vector_models(src_root: Path) -> list[type[VectorModel]]:
    """Discover all VectorModel subclasses under ``src/`` domains.

    Scans ``{domain}/infrastructure/vectors/models/`` for each domain.
    Same convention as ``scan_dynamo_models()``.
    """
    from src._core.infrastructure.vectors.vector_model import (
        VectorModel as BaseVectorModel,
    )

    models: list[type[VectorModel]] = []

    for domain_dir in sorted(src_root.iterdir()):
        if not domain_dir.is_dir():
            continue
        if domain_dir.name.startswith(("_", ".")):
            continue
        if not (domain_dir / "__init__.py").exists():
            continue

        models_dir = domain_dir / "infrastructure" / "s3vectors" / "models"
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
                print("  [WARN] Failed to import " + module_path + ": " + str(exc))
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseVectorModel)
                    and attr is not BaseVectorModel
                    and hasattr(attr, "__vector_meta__")
                ):
                    models.append(attr)

    return models
