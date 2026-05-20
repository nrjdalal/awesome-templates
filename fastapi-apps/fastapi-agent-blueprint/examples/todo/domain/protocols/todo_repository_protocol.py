from typing import Protocol

from examples.todo.domain.dtos.todo_dto import TodoDTO
from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol


class TodoRepositoryProtocol(BaseRepositoryProtocol[TodoDTO], Protocol):
    pass
