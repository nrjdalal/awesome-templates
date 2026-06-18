import pytest

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException


@pytest.mark.asyncio
async def test_session_propagates_domain_exception(test_db):
    """Regression for #245.

    A ``BaseCustomException`` raised inside the ``session()`` block — e.g. the
    404 a repository raises on a missing row — must propagate unchanged. It must
    NOT be masked as a 500 ``DB_INTERNAL_ERROR`` by the catch-all wrapper.
    """
    with pytest.raises(BaseCustomException) as exc_info:
        async with test_db.session():
            raise BaseCustomException(
                status_code=404, message="missing", error_code="NOT_FOUND"
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "NOT_FOUND"
    # The wrapper must not have re-typed it into a DatabaseException.
    assert not isinstance(exc_info.value, DatabaseException)


@pytest.mark.asyncio
async def test_session_wraps_unexpected_error(test_db):
    """A non-domain error inside the block is still wrapped as a 500."""
    with pytest.raises(DatabaseException) as exc_info:
        async with test_db.session():
            raise RuntimeError("boom")

    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == "DB_INTERNAL_ERROR"
