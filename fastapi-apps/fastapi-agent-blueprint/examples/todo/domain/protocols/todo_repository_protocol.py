from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

from ..dtos.todo_dto import TodoDTO


class TodoRepositoryProtocol(BaseRepositoryProtocol[TodoDTO], Protocol):
    pass
