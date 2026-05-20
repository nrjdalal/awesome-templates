from typing import Any, cast

import pytest
from pydantic import BaseModel

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src._core.domain.validation import (
    ValidationErrorDetail,
    ValidationFailed,
    collect_conditionally_required_errors,
    collect_duplicate_field_errors,
    collect_unique_field_errors,
    ensure_conditionally_required,
)


class SampleRequest(BaseModel):
    email: str | None = None
    name: str | None = None


class FakeRepository:
    def __init__(self, existing: dict[str, set[str]] | None = None) -> None:
        self.existing = existing or {}

    async def exists_by_fields(
        self,
        filters,
        *,
        exclude_id=None,
    ) -> bool:
        return any(
            value in self.existing.get(field, set()) for field, value in filters.items()
        )


def test_validation_failed_uses_stable_error_details_shape():
    exc = ValidationFailed(
        [
            ValidationErrorDetail(
                field="email",
                message="email already exists",
                type="unique",
            )
        ],
        status_code=409,
        error_code="USER_ALREADY_EXISTS",
    )

    assert exc.status_code == 409
    assert exc.error_code == "USER_ALREADY_EXISTS"
    assert exc.details == {
        "errors": [
            {
                "field": "email",
                "message": "email already exists",
                "type": "unique",
            }
        ]
    }


def test_collect_duplicate_field_errors_reports_each_duplicated_field_once():
    entities = [
        SampleRequest(email="a@example.com", name="one"),
        SampleRequest(email="a@example.com", name="two"),
        SampleRequest(email="b@example.com", name="two"),
    ]

    errors = collect_duplicate_field_errors(entities, ("email", "name"))

    assert [error.field for error in errors] == ["email", "name"]
    assert all(error.type == "duplicate" for error in errors)


def test_conditionally_required_helpers_return_field_errors():
    entity = SampleRequest(email=None, name="Name")

    errors = collect_conditionally_required_errors(
        entity,
        ("email",),
        condition=True,
    )

    assert errors == [
        ValidationErrorDetail(
            field="email",
            message="Field is required",
            type="conditional_required",
        )
    ]
    with pytest.raises(ValidationFailed) as exc_info:
        ensure_conditionally_required(entity, ("email",), condition=True)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_collect_unique_field_errors_uses_repository_primitives():
    repo = cast(
        BaseRepositoryProtocol[Any],
        FakeRepository(existing={"email": {"taken@example.com"}}),
    )

    errors = await collect_unique_field_errors(
        repo,
        SampleRequest(email="taken@example.com"),
        ("email",),
    )

    assert errors == [
        ValidationErrorDetail(
            field="email",
            message="email already exists",
            type="unique",
        )
    ]
