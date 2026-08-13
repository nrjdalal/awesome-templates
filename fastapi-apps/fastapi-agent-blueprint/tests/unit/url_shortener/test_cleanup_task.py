from datetime import UTC, datetime, timedelta

import pytest

from examples.url_shortener.domain.dtos.link_dto import LinkDTO
from examples.url_shortener.domain.services.link_service import LinkService
from tests.support.fake_repository import FakeRepositoryBase


class InMemoryLinkRepository(FakeRepositoryBase[LinkDTO]):
    def __init__(self, links: list[LinkDTO]) -> None:
        self.links = {link.short_code: link for link in links}

    async def delete_expired(self, cutoff: datetime) -> int:
        expired_codes = [
            short_code
            for short_code, link in self.links.items()
            if link.expires_at is not None and link.expires_at < cutoff
        ]
        for short_code in expired_codes:
            self.links.pop(short_code)
        return len(expired_codes)

    # The domain half of LinkRepositoryProtocol; this test only exercises
    # delete_expired. Raising rather than absent, so the double satisfies the
    # protocol and a future caller fails loudly.
    async def select_data_by_short_code(self, short_code: str) -> LinkDTO:
        raise self._unsupported("select_data_by_short_code")

    async def delete_data_by_short_code(self, short_code: str) -> bool:
        raise self._unsupported("delete_data_by_short_code")


def make_link(short_code: str, expires_at: datetime | None) -> LinkDTO:
    now = datetime.now(UTC).replace(tzinfo=None)
    return LinkDTO(
        id=len(short_code),
        short_code=short_code,
        target_url=f"https://example.com/{short_code}",
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_delete_expired_removes_only_expired_links() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    repo = InMemoryLinkRepository(
        [
            make_link("old", now - timedelta(minutes=1)),
            make_link("fresh", now + timedelta(minutes=1)),
            make_link("permanent", None),
        ]
    )
    service = LinkService(link_repository=repo)

    deleted = await service.delete_expired(cutoff=now)

    assert deleted == 1  # noqa: S101
    assert "old" not in repo.links  # noqa: S101
    assert "fresh" in repo.links  # noqa: S101
    assert "permanent" in repo.links  # noqa: S101
