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
    return await auth_use_case.get_current_user(credentials.credentials)
