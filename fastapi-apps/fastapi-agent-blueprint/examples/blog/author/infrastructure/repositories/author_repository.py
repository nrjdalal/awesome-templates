from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database

from ...domain.dtos.author_dto import AuthorDTO
from ..database.models.author_model import AuthorModel


class AuthorRepository(BaseRepository[AuthorDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=AuthorModel,
            return_entity=AuthorDTO,
        )
