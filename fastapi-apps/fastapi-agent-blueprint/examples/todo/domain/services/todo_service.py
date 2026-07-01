from src._core.domain.services.base_service import BaseService

from ...interface.server.schemas.todo_schema import (
    CreateTodoRequest,
    UpdateTodoRequest,
)
from ..dtos.todo_dto import TodoDTO
from ..protocols.todo_repository_protocol import (
    TodoRepositoryProtocol,
)


class TodoService(BaseService[CreateTodoRequest, UpdateTodoRequest, TodoDTO]):
    def __init__(self, todo_repository: TodoRepositoryProtocol) -> None:
        super().__init__(repository=todo_repository)
