from examples.todo.domain.dtos.todo_dto import TodoDTO
from examples.todo.domain.protocols.todo_repository_protocol import (
    TodoRepositoryProtocol,
)
from examples.todo.interface.server.schemas.todo_schema import (
    CreateTodoRequest,
    UpdateTodoRequest,
)
from src._core.domain.services.base_service import BaseService


class TodoService(BaseService[CreateTodoRequest, UpdateTodoRequest, TodoDTO]):
    def __init__(self, todo_repository: TodoRepositoryProtocol) -> None:
        super().__init__(repository=todo_repository)
