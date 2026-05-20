from examples.todo.domain.dtos.todo_dto import TodoDTO
from examples.todo.infrastructure.database.models.todo_model import TodoModel
from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database


class TodoRepository(BaseRepository[TodoDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=TodoModel,
            return_entity=TodoDTO,
        )
