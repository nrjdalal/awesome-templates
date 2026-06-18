from dependency_injector.wiring import Provide, inject

from src._apps.worker.broker import broker
from src._core.config import settings

from ....domain.services.link_service import LinkService
from ....infrastructure.di.url_shortener_container import UrlShortenerContainer


@broker.task(
    task_name=f"{settings.task_name_prefix}.url_shortener.cleanup_expired_links"
)
@inject
async def cleanup_expired_links_task(
    link_service: LinkService = Provide[UrlShortenerContainer.link_service],
) -> int:
    return await link_service.delete_expired()
