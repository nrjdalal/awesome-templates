from __future__ import annotations

from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src.docs.domain.dtos.document_dto import DocumentDTO
from src.docs.infrastructure.database.models.document_model import DocumentModel


class DocumentRepository(BaseRepository[DocumentDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=DocumentModel,
            return_entity=DocumentDTO,
        )
