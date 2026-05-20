from collections.abc import Sequence

from src._core.domain.validation import ValidationErrorDetail, ValidationFailed
from src._core.exceptions.base_exception import BaseCustomException


class UserNotFoundException(BaseCustomException):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            status_code=404,
            message=f"User with ID [ {user_id} ] not found",
            error_code="USER_NOT_FOUND",
        )


class UserAlreadyExistsException(ValidationFailed):
    def __init__(
        self,
        username: str | None = None,
        *,
        errors: Sequence[ValidationErrorDetail] | None = None,
    ) -> None:
        if errors is None:
            errors = (
                ValidationErrorDetail(
                    field="username",
                    message="username already exists",
                    type="unique",
                ),
            )
        message = (
            f"User with username [ {username} ] already exists"
            if username
            else "User already exists"
        )
        super().__init__(
            errors,
            status_code=409,
            message=message,
            error_code="USER_ALREADY_EXISTS",
        )
