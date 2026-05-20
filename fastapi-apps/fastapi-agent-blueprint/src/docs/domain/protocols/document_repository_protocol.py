from __future__ import annotations

from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.docs.domain.dtos.document_dto import DocumentDTO


class DocumentRepositoryProtocol(BaseRepositoryProtocol[DocumentDTO], Protocol):
    pass
