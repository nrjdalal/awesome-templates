import os

import pytest
import pytest_asyncio
import structlog

from src._core.infrastructure.persistence.rdb.config import DatabaseConfig
from src._core.infrastructure.persistence.rdb.database import Base, Database


@pytest.fixture(autouse=True)
def _reset_structlog() -> None:
    """Reset structlog to library defaults before each test.

    Production ``configure_logging()`` sets ``cache_logger_on_first_use=True``.
    Once an app-startup test (e2e) runs, that caching persists for the whole
    session, so the first use of any module-level ``get_logger`` proxy caches a
    concrete bound logger that ``structlog.testing.capture_logs()`` can no
    longer intercept — making capture-based assertions order-dependent (#197
    Phase 5 surfaced this). Resetting to the (non-caching) defaults before each
    test keeps ``capture_logs`` deterministic; tests that need the configured
    pipeline call ``configure_logging()`` themselves.
    """
    structlog.reset_defaults()


def _build_test_database() -> Database:
    """Construct the test Database based on ``TEST_DB_ENGINE``.

    Default: SQLite in-memory — no external infra, fast, CI-friendly.
    ``TEST_DB_ENGINE=postgresql``: connect to the local docker PostgreSQL
    (see ``docker-compose.local.yml``). Use ``make test-pg`` for this path.
    """
    engine = os.environ.get("TEST_DB_ENGINE", "sqlite").lower()
    config = DatabaseConfig(echo=False)

    if engine == "postgresql":
        return Database(
            database_engine="postgresql",
            database_user=os.environ.get("TEST_DB_USER", "postgres"),
            database_password=os.environ.get("TEST_DB_PASSWORD", "postgres"),
            database_host=os.environ.get("TEST_DB_HOST", "localhost"),
            database_port=int(os.environ.get("TEST_DB_PORT", "5432")),
            database_name=os.environ.get("TEST_DB_NAME", "postgres"),
            config=config,
        )

    return Database(
        database_engine="sqlite",
        database_user="",
        database_password="",
        database_host="",
        database_port=0,
        database_name=":memory:",
        config=config,
    )


@pytest_asyncio.fixture(scope="session")
async def test_db():
    db = _build_test_database()
    async with db.async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield db
    async with db.async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db.dispose()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
