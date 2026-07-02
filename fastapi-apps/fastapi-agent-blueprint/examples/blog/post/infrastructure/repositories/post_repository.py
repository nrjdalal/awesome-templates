from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database

from ...domain.dtos.post_dto import PostDTO
from ..database.models.post_model import PostModel


class PostRepository(BaseRepository[PostDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=PostModel,
            return_entity=PostDTO,
        )
