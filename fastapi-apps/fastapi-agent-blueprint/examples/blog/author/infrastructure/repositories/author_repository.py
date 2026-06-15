from examples.blog.author.domain.dtos.author_dto import AuthorDTO
from examples.blog.author.infrastructure.database.models.author_model import AuthorModel
from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database


class AuthorRepository(BaseRepository[AuthorDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=AuthorModel,
            return_entity=AuthorDTO,
        )
