from dependency_injector.wiring import Provide, inject

from src._apps.worker.broker import broker
from src._core.config import settings
from src.user.domain.services.user_service import UserService
from src.user.infrastructure.di.user_container import UserContainer
from src.user.interface.worker.payloads.user_payload import UserTestPayload


@broker.task(task_name=f"{settings.task_name_prefix}.user.test")
@inject
async def consume_task(
    user_service: UserService = Provide[UserContainer.user_service],
    **kwargs,
) -> None:
    payload = UserTestPayload.model_validate(kwargs)

    await user_service.get_data_by_data_id(data_id=payload.id)
