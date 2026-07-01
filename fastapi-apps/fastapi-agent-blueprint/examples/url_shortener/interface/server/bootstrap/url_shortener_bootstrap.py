"""URL shortener domain independent server bootstrap."""

from fastapi import FastAPI

from ....infrastructure.di.url_shortener_container import UrlShortenerContainer
from ..routers import link_router


def create_url_shortener_container(
    url_shortener_container: UrlShortenerContainer,
) -> None:
    url_shortener_container.wire(modules=[link_router])


def setup_url_shortener_routes(app: FastAPI) -> None:
    app.include_router(router=link_router.router, prefix="/v1", tags=["Link"])


def bootstrap_url_shortener_domain(
    app: FastAPI,
    url_shortener_container: UrlShortenerContainer,
) -> None:
    create_url_shortener_container(url_shortener_container=url_shortener_container)
    setup_url_shortener_routes(app=app)
