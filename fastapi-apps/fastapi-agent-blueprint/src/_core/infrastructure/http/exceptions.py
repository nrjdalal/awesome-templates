from src._core.exceptions.base_exception import BaseCustomException


class ExternalServiceException(BaseCustomException):
    def __init__(self, message: str = "External service error") -> None:
        super().__init__(
            status_code=502,
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
        )


class ExternalServiceTimeoutException(BaseCustomException):
    def __init__(self, message: str = "External service timeout") -> None:
        super().__init__(
            status_code=504,
            message=message,
            error_code="EXTERNAL_SERVICE_TIMEOUT",
        )
