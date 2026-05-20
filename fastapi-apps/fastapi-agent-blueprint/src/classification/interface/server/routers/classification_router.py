from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from src._core.application.dtos.base_response import SuccessResponse
from src.classification.domain.services.classification_service import (
    ClassificationService,
)
from src.classification.infrastructure.di.classification_container import (
    ClassificationContainer,
)
from src.classification.interface.server.schemas.classification_schema import (
    ClassificationResponse,
    ClassifyRequest,
)

router = APIRouter()


@router.post(
    "/classify",
    summary="Classify text",
    response_model=SuccessResponse[ClassificationResponse],
    response_model_exclude={"pagination"},
)
@inject
async def classify_text(
    item: ClassifyRequest,
    classification_service: ClassificationService = Depends(
        Provide[ClassificationContainer.classification_service]
    ),
) -> SuccessResponse[ClassificationResponse]:
    result = await classification_service.classify(
        text=item.text,
        categories=item.categories,
    )
    return SuccessResponse(
        data=ClassificationResponse(**result.model_dump()),
    )
