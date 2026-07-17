"""Unit tests for the web search chatbot example."""

import pytest
import pytest_asyncio

# Force registration of chatbot model onto Base.metadata
from examples.web_search_chatbot.infrastructure.database.models.chatbot_model import (
    ChatMessageModel,
)
from src._core.infrastructure.persistence.rdb.config import DatabaseConfig
from src._core.infrastructure.persistence.rdb.database import (
    Base,
    Database,
)


def _build_test_database() -> Database:
    config = DatabaseConfig(echo=False)
    return Database(
        database_engine="sqlite",
        database_user="",
        database_password="",
        database_host="",
        database_port=0,
        database_name=":memory:",
        config=config,
    )


@pytest_asyncio.fixture(scope="module")
async def test_db():
    db = _build_test_database()
    async with db.async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield db
    async with db.async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db.dispose()


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"
