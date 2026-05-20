from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from examples.todo.domain.dtos.todo_dto import TodoDTO
from examples.todo.domain.services.todo_service import TodoService
from examples.todo.interface.server.schemas.todo_schema import (
    CreateTodoRequest,
    UpdateTodoRequest,
)


def make_todo_dto(**kwargs):
    defaults = {
        "id": 123,
        "title": "Test Todo",
        "description": "Test desc",
        "done": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return TodoDTO(**defaults)


@pytest.mark.asyncio
async def test_create_todo():
    mock_repo = AsyncMock()
    mock_repo.insert_data.return_value = make_todo_dto()
    service = TodoService(todo_repository=mock_repo)
    request = CreateTodoRequest(title="Test Todo", description="Test desc")
    result = await service.create_data(entity=request)
    assert result.title == "Test Todo"
    assert result.done is False


@pytest.mark.asyncio
async def test_get_todo():
    mock_repo = AsyncMock()
    mock_repo.select_data_by_id.return_value = make_todo_dto(title="Fetched Todo")
    service = TodoService(todo_repository=mock_repo)
    result = await service.get_data_by_data_id(data_id=123)
    assert result.title == "Fetched Todo"
