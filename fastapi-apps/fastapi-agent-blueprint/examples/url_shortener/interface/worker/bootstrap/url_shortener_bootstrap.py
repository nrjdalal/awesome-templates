from ....infrastructure.di.url_shortener_container import UrlShortenerContainer
from ..tasks import cleanup_expired_links_task


def create_url_shortener_container(
    url_shortener_container: UrlShortenerContainer,
) -> None:
    url_shortener_container.wire(modules=[cleanup_expired_links_task])


def bootstrap_url_shortener_domain(
    url_shortener_container: UrlShortenerContainer,
) -> None:
    create_url_shortener_container(url_shortener_container=url_shortener_container)
