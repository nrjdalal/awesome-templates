import pytest_asyncio


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _override_app_database(test_db):
    """Swap the app's Database with ``test_db`` for the entire e2e session.

    The FastAPI app boots a real Database Singleton at import time
    (`src._apps.server.app.app`). E2E tests must run without external infra,
    so we override the wired container instance exposed via ``app.state``.

    Scoped to ``tests/e2e`` because unit/integration tests do not (and should
    not) import the app — forcing an app import on them makes the unit suite
    unnecessarily depend on Settings env vars.
    """
    from src._apps.server.app import app
    from src._apps.server.testing import override_database, reset_database_override

    override_database(app, test_db)
    yield
    reset_database_override(app)
