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


class ForbiddenException(BaseCustomException):
    """Authenticated caller lacks the required role for an API route."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            message="Forbidden",
            error_code="FORBIDDEN",
        )


class AdminSetupRequiredException(BaseCustomException):
    """Bootstrap credential used when no real admin exists — route to setup wizard."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            message="Initial admin setup required",
            error_code="ADMIN_SETUP_REQUIRED",
        )


class AdminCredentialDisabledException(BaseCustomException):
    """Bootstrap credential used after a real admin already exists — generic block."""

    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="Invalid credentials",
            error_code="INVALID_CREDENTIALS",
        )


class AdminSetupForbiddenException(BaseCustomException):
    """Direct access to /admin/setup when a real admin already exists."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            message="Admin setup is not available",
            error_code="ADMIN_SETUP_FORBIDDEN",
        )


class AdminPermissionDeniedException(BaseCustomException):
    """Admin lacks the required page permission."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            message="Permission denied",
            error_code="ADMIN_PERMISSION_DENIED",
        )


class AdminLastAccountsGuardException(BaseCustomException):
    """Blocked because action would remove the last accounts-permission holder."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            message="Cannot remove the last admin with accounts permission",
            error_code="ADMIN_LAST_ACCOUNTS_GUARD",
        )


class AdminSelfActionForbiddenException(BaseCustomException):
    """Admin attempted a self-delete or self-lockout action."""

    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            message="Cannot perform this action on your own account",
            error_code="ADMIN_SELF_ACTION_FORBIDDEN",
        )
