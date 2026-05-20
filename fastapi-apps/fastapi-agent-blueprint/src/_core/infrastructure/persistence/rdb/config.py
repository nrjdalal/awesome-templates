from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Environment profiles: base pool/connection settings per environment
# ---------------------------------------------------------------------------
_ENV_PROFILES: dict[str, dict[str, Any]] = {
    "local": {"echo": True, "pool_size": 5, "max_overflow": 10},
    "dev": {"echo": True, "pool_size": 5, "max_overflow": 10},
    "stg": {"echo": False, "pool_size": 10, "max_overflow": 20},
    "prod": {"echo": False, "pool_size": 10, "max_overflow": 20},
}

# ---------------------------------------------------------------------------
# Engine-specific connect_args for production-like environments (stg, prod)
# ---------------------------------------------------------------------------
_PG_STRICT_CONNECT_ARGS: dict[str, Any] = {
    "timeout": 10,
    "connect_timeout": 10,
    "command_timeout": 30,
    "server_settings": {
        "statement_timeout": "30000",
        "idle_in_transaction_session_timeout": "300000",
        "application_name": "server_api",
    },
}

_MYSQL_STRICT_CONNECT_ARGS: dict[str, Any] = {
    "connect_timeout": 10,
    "read_timeout": 30,
    "write_timeout": 30,
}


def _build_connect_args(engine: str, env: str) -> dict[str, Any]:
    """Build engine-specific connect_args for production-like environments."""
    if env not in ("stg", "prod"):
        return {}
    if engine == "postgresql":
        return dict(_PG_STRICT_CONNECT_ARGS)
    if engine == "mysql":
        return dict(_MYSQL_STRICT_CONNECT_ARGS)
    return {}


class DatabaseConfig(BaseModel):
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    connect_args: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_env(
        cls,
        env: str,
        engine: str = "postgresql",
        *,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        pool_recycle: int | None = None,
        echo: bool | None = None,
    ) -> "DatabaseConfig":
        """Create configuration based on environment and engine.

        Environment profiles provide sensible defaults.
        Explicit keyword arguments override profile values.
        """
        profile = _ENV_PROFILES.get(env, _ENV_PROFILES["local"])
        connect_args = _build_connect_args(engine, env)

        config = {
            "pool_recycle": 3600,
            "pool_pre_ping": True,
            **profile,
            "connect_args": connect_args,
        }

        # Apply explicit overrides (from DATABASE_* env vars via Settings)
        if pool_size is not None:
            config["pool_size"] = pool_size
        if max_overflow is not None:
            config["max_overflow"] = max_overflow
        if pool_recycle is not None:
            config["pool_recycle"] = pool_recycle
        if echo is not None:
            config["echo"] = echo

        return cls(**config)
