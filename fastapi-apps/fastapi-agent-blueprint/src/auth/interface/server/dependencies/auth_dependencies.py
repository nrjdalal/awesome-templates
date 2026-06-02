import structlog
from dependency_injector.wiring import Provide, inject
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.application.use_cases.auth_use_case import AuthUseCase
from src.auth.domain.exceptions.auth_exceptions import UnauthorizedException
from src.auth.infrastructure.di.auth_container import AuthContainer
from src.user.domain.dtos.user_dto import UserDTO

bearer_scheme = HTTPBearer(auto_error=False)


@inject
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_use_case: AuthUseCase = Depends(Provide[AuthContainer.auth_use_case]),
) -> UserDTO:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException()
    user = await auth_use_case.get_current_user(credentials.credentials)
    # Bind user_id to structlog contextvars so every record emitted during this
    # request (notably guardrail_triggered telemetry, #197 Phase 5) carries it.
    # RequestLogMiddleware unbinds it in its per-request cleanup.
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


# require_admin moved to the admin_identity realm (#218 / ADR 049):
# src/admin_identity/interface/server/dependencies/admin_auth_dependencies.py.
# It verifies admin-realm tokens, not customer tokens.
