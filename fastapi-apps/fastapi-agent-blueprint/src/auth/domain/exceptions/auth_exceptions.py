from src._core.exceptions.base_exception import BaseCustomException


class UnauthorizedException(BaseCustomException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="Authentication required",
            error_code="UNAUTHORIZED",
        )


class InvalidCredentialsException(BaseCustomException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="Invalid credentials",
            error_code="INVALID_CREDENTIALS",
        )


class TokenExpiredException(BaseCustomException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="Token has expired",
            error_code="TOKEN_EXPIRED",
        )


class InvalidTokenException(BaseCustomException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="Invalid token",
            error_code="INVALID_TOKEN",
        )


class RefreshTokenRevokedException(BaseCustomException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="Refresh token has been revoked",
            error_code="REFRESH_TOKEN_REVOKED",
        )
