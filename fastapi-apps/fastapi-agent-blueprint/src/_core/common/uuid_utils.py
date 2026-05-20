from __future__ import annotations

import uuid


def generate_vector_id() -> str:
    """Generate a unique vector ID (UUID v4 hex without dashes)."""
    return uuid.uuid4().hex
