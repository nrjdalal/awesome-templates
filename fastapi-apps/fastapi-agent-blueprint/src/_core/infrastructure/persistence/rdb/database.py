import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src._core.infrastructure.persistence.rdb.config import DatabaseConfig
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException

# ---------------------------------------------------------------------------
# Driver mappings per engine
# ---------------------------------------------------------------------------
ASYNC_DRIVERS: dict[str, str] = {
    "postgresql": "asyncpg",
    "mysql": "aiomysql",
    "sqlite": "aiosqlite",
}

SYNC_DRIVERS: dict[str, str] = {
    "postgresql": "psycopg",
    "mysql": "pymysql",
    "sqlite": "",
}

# Pool kwargs that SQLite does not support
_SQLITE_EXCLUDED_POOL_KEYS = frozenset({"pool_size", "max_overflow", "pool_pre_ping"})


# ---------------------------------------------------------------------------
# DSN builders
# ---------------------------------------------------------------------------
def _build_dsn(
    engine: str,
    driver: str,
    database_user: str,
    database_password: str,
    database_host: str,
    database_port: int,
    database_name: str,
) -> str:
    dialect = f"{engine}+{driver}" if driver else engine
    if engine == "sqlite":
        return f"{dialect}:///{database_name}"
    return (
        f"{dialect}://{database_user}:{database_password}"
        f"@{database_host}:{database_port}/{database_name}"
    )


def create_async_dsn(
    engine: str,
    database_user: str,
    database_password: str,
    database_host: str,
    database_port: int,
    database_name: str,
) -> str:
    return _build_dsn(
        engine=engine,
        driver=ASYNC_DRIVERS[engine],
        database_user=database_user,
        database_password=database_password,
        database_host=database_host,
        database_port=database_port,
        database_name=database_name,
    )


def create_sync_dsn(
    engine: str,
    database_user: str,
    database_password: str,
    database_host: str,
    database_port: int,
    database_name: str,
) -> str:
    return _build_dsn(
        engine=engine,
        driver=SYNC_DRIVERS[engine],
        database_user=database_user,
        database_password=database_password,
        database_host=database_host,
        database_port=database_port,
        database_name=database_name,
    )


# ---------------------------------------------------------------------------
# Engine kwargs helper
# ---------------------------------------------------------------------------
def _engine_kwargs(
    config: DatabaseConfig,
    engine: str,
    *,
    exclude_connect_args: bool = False,
) -> dict[str, Any]:
    """Build SQLAlchemy create_engine kwargs from DatabaseConfig.

    ``echo`` is intentionally stripped from the kwargs — SQLAlchemy's
    ``create_engine(echo=True)`` attaches its own ``StreamHandler`` to
    the ``sqlalchemy.engine`` logger, which double-emits every query
    when the structlog ``ProcessorFormatter`` handler is also installed
    on root. Instead, ``Database.__init__`` translates the flag into
    ``logging.getLogger('sqlalchemy.engine').setLevel(INFO)`` so SQL
    queries flow through the structlog pipeline exactly once.
    """
    exclude: set[str] = {"echo"}
    if exclude_connect_args:
        exclude.add("connect_args")
    if engine == "sqlite":
        exclude.update(_SQLITE_EXCLUDED_POOL_KEYS)
    return config.model_dump(exclude=exclude)


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(
        self,
        database_engine: str,
        database_user: str,
        database_password: str,
        database_host: str,
        database_port: int,
        database_name: str,
        config: DatabaseConfig,
    ) -> None:
        engine = database_engine.lower()

        dsn = create_sync_dsn(
            engine=engine,
            database_user=quote_plus(database_user),
            database_password=quote_plus(database_password),
            database_host=database_host,
            database_port=database_port,
            database_name=database_name,
        )

        async_dsn = create_async_dsn(
            engine=engine,
            database_user=quote_plus(database_user),
            database_password=quote_plus(database_password),
            database_host=database_host,
            database_port=database_port,
            database_name=database_name,
        )

        self.engine = create_engine(
            url=dsn,
            **_engine_kwargs(config, engine, exclude_connect_args=True),
        )

        self.async_engine = create_async_engine(
            url=async_dsn,
            **_engine_kwargs(config, engine),
        )

        # ``DatabaseConfig.echo`` used to be passed to ``create_engine``,
        # which in turn installs a ``StreamHandler`` on
        # ``sqlalchemy.engine``. That bypasses the configured structlog
        # pipeline and double-emits every query. Translate the flag into
        # a logger level instead so SQL records flow through the root
        # structlog handler exactly once (#9).
        if config.echo:
            logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

        self.async_session_factory = sessionmaker(
            bind=self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        session = None

        try:
            session = self.async_session_factory()
            yield session
        except IntegrityError:
            if session:
                await session.rollback()
            raise DatabaseException(
                status_code=400,
                message="Data integrity error",
                error_code="DB_INTEGRITY_ERROR",
            )
        except Exception as e:
            if session:
                await session.rollback()
            from src._core.config import settings

            raise DatabaseException(
                status_code=500,
                message="Internal database error",
                error_code="DB_INTERNAL_ERROR",
                details={"original_error": str(e)} if settings.is_dev else None,
            )
        finally:
            if session:
                await session.close()

    async def dispose(self) -> None:
        await self.async_engine.dispose()
        self.engine.dispose()

    async def check_connection(self) -> bool:
        try:
            async with self.async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            from src._core.config import settings

            raise DatabaseException(
                status_code=503,
                message="Database health check failed",
                error_code="DATABASE_UNHEALTHY",
                details={"original_error": str(e)} if settings.is_dev else None,
            )
