"""Domain auto-discovery utility.

Automatically detects domain packages under src/ so that DI Containers
and Bootstrap can load domains without manual registration.

Reference: Uses the same scan pattern as load_models() in migrations/env_utils.py.
"""

import importlib
from pathlib import Path


def discover_domains() -> list[str]:
    """Auto-detect valid domain packages under src/.

    A valid domain must satisfy:
    - Directory name does not start with '_' or '.'
    - Contains __init__.py
    - Contains infrastructure/di/{name}_container.py

    Returns:
        Alphabetically sorted list of domain names.
    """
    src_path = Path(__file__).parent.parent.parent  # src/
    domains = []

    for item in sorted(src_path.iterdir()):
        if item.name.startswith(("_", ".")) or not item.is_dir():
            continue
        if not (item / "__init__.py").exists():
            continue

        container_file = item / "infrastructure" / "di" / f"{item.name}_container.py"
        if container_file.exists():
            domains.append(item.name)

    return domains


def to_class_name(domain_name: str) -> str:
    """Convert a snake_case domain name to PascalCase.

    Examples:
        >>> to_class_name("user")
        'User'
        >>> to_class_name("user_profile")
        'UserProfile'
    """
    return "".join(word.capitalize() for word in domain_name.split("_"))


def load_domain_container(domain_name: str):
    """Dynamically load a domain's DI Container class.

    Args:
        domain_name: Domain name (e.g. "user").

    Returns:
        Container class (e.g. UserContainer).
    """
    module_path = f"src.{domain_name}.infrastructure.di.{domain_name}_container"
    module = importlib.import_module(module_path)
    class_name = f"{to_class_name(domain_name)}Container"
    return getattr(module, class_name)
