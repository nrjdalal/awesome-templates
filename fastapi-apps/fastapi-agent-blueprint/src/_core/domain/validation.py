from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src._core.exceptions.base_exception import BaseCustomException

BUSINESS_VALIDATION_ERROR = "BUSINESS_VALIDATION_ERROR"
BUSINESS_CONFLICT = "BUSINESS_CONFLICT"


class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    type: str


class ValidationFailed(BaseCustomException):
    def __init__(
        self,
        errors: Sequence[ValidationErrorDetail | Mapping[str, Any]],
        *,
        status_code: int = 422,
        message: str = "Validation failed",
        error_code: str | None = None,
    ) -> None:
        normalized_errors = [_coerce_error(error) for error in errors]
        resolved_error_code = error_code or (
            BUSINESS_CONFLICT if status_code == 409 else BUSINESS_VALIDATION_ERROR
        )
        super().__init__(
            status_code=status_code,
            message=message,
            error_code=resolved_error_code,
            details={"errors": [error.model_dump() for error in normalized_errors]},
        )
        self.errors = tuple(normalized_errors)


def validation_error(
    field: str,
    message: str,
    error_type: str,
) -> ValidationErrorDetail:
    return ValidationErrorDetail(field=field, message=message, type=error_type)


def raise_if_errors(
    errors: Sequence[ValidationErrorDetail],
    *,
    status_code: int = 422,
    message: str = "Validation failed",
    error_code: str | None = None,
) -> None:
    if errors:
        raise ValidationFailed(
            errors,
            status_code=status_code,
            message=message,
            error_code=error_code,
        )


def collect_conditionally_required_errors(
    entity: BaseModel,
    fields: Sequence[str],
    *,
    condition: bool,
    message: str = "Field is required",
) -> list[ValidationErrorDetail]:
    if not condition:
        return []
    data = entity.model_dump()
    return [
        validation_error(field, message, "conditional_required")
        for field in fields
        if data.get(field) is None
    ]


def ensure_conditionally_required(
    entity: BaseModel,
    fields: Sequence[str],
    *,
    condition: bool,
    message: str = "Field is required",
) -> None:
    raise_if_errors(
        collect_conditionally_required_errors(
            entity,
            fields,
            condition=condition,
            message=message,
        )
    )


def collect_duplicate_field_errors(
    entities: Sequence[BaseModel],
    fields: Sequence[str],
) -> list[ValidationErrorDetail]:
    errors: list[ValidationErrorDetail] = []
    for field in fields:
        seen: set[Any] = set()
        duplicate_found = False
        for entity in entities:
            value = entity.model_dump().get(field)
            if value is None:
                continue
            if value in seen:
                duplicate_found = True
                break
            seen.add(value)
        if duplicate_found:
            errors.append(
                validation_error(
                    field,
                    f"Duplicate {field} in request payload",
                    "duplicate",
                )
            )
    return errors


def ensure_no_duplicate_field_values(
    entities: Sequence[BaseModel],
    fields: Sequence[str],
) -> None:
    raise_if_errors(collect_duplicate_field_errors(entities, fields))


async def collect_unique_field_errors(
    repository: BaseRepositoryProtocol[Any],
    entity: BaseModel,
    fields: Sequence[str],
    *,
    exclude_id: int | None = None,
    message_template: str = "{field} already exists",
) -> list[ValidationErrorDetail]:
    errors: list[ValidationErrorDetail] = []
    data = entity.model_dump()
    for field in fields:
        value = data.get(field)
        if value is None:
            continue
        if await repository.exists_by_fields({field: value}, exclude_id=exclude_id):
            errors.append(
                validation_error(
                    field,
                    message_template.format(field=field),
                    "unique",
                )
            )
    return errors


async def ensure_unique_field_values(
    repository: BaseRepositoryProtocol[Any],
    entity: BaseModel,
    fields: Sequence[str],
    *,
    exclude_id: int | None = None,
    message: str = "Validation failed",
    error_code: str | None = None,
) -> None:
    errors = await collect_unique_field_errors(
        repository,
        entity,
        fields,
        exclude_id=exclude_id,
    )
    raise_if_errors(
        errors,
        status_code=409,
        message=message,
        error_code=error_code,
    )


async def collect_existing_unique_field_errors(
    repository: BaseRepositoryProtocol[Any],
    entities: Sequence[BaseModel],
    fields: Sequence[str],
    *,
    exclude_id: int | None = None,
    message_template: str = "{field} already exists",
) -> list[ValidationErrorDetail]:
    errors: list[ValidationErrorDetail] = []
    for field in fields:
        values = [
            entity.model_dump().get(field)
            for entity in entities
            if entity.model_dump().get(field) is not None
        ]
        existing_values = await repository.existing_values_by_field(
            field,
            values,
            exclude_id=exclude_id,
        )
        if existing_values:
            errors.append(
                validation_error(
                    field,
                    message_template.format(field=field),
                    "unique",
                )
            )
    return errors


async def ensure_unique_field_values_for_batch(
    repository: BaseRepositoryProtocol[Any],
    entities: Sequence[BaseModel],
    fields: Sequence[str],
    *,
    message: str = "Validation failed",
    error_code: str | None = None,
) -> None:
    errors = await collect_existing_unique_field_errors(repository, entities, fields)
    raise_if_errors(
        errors,
        status_code=409,
        message=message,
        error_code=error_code,
    )


async def collect_existing_reference_errors(
    repository: BaseRepositoryProtocol[Any],
    field: str,
    values: Sequence[int],
    *,
    message: str = "Referenced resource does not exist",
) -> list[ValidationErrorDetail]:
    missing = False
    for value in set(values):
        if not await repository.exists_by_id(value):
            missing = True
            break
    if not missing:
        return []
    return [validation_error(field, message, "exists")]


async def ensure_existing_references(
    repository: BaseRepositoryProtocol[Any],
    field: str,
    values: Sequence[int],
    *,
    message: str = "Referenced resource does not exist",
) -> None:
    raise_if_errors(
        await collect_existing_reference_errors(
            repository,
            field,
            values,
            message=message,
        )
    )


def _coerce_error(
    error: ValidationErrorDetail | Mapping[str, Any],
) -> ValidationErrorDetail:
    if isinstance(error, ValidationErrorDetail):
        return error
    return ValidationErrorDetail.model_validate(error)
