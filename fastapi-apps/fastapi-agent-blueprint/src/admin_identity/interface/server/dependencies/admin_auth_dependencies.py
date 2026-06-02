from dependency_injector.wiring import Provide, inject
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.admin_identity.application.use_cases.admin_auth_use_case import (
    AdminAuthUseCase,
)
from src.admin_identity.domain.dtos.admin_identity_dto import AdminIdentityDTO
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminForbiddenException,
    AdminUnauthorizedException,
)
from src.admin_identity.infrastructure.di.admin_identity_container import (
    AdminIdentityContainer,
)

admin_bearer_scheme = HTTPBearer(auto_error=False)


@inject
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer_scheme),
    admin_auth_use_case: AdminAuthUseCase = Depends(
        Provide[AdminIdentityContainer.admin_auth_use_case]
    ),
) -> AdminIdentityDTO:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AdminUnauthorizedException()
    return await admin_auth_use_case.get_current_admin(credentials.credentials)


async def require_admin(
    current_admin: AdminIdentityDTO = Depends(get_current_admin),
) -> AdminIdentityDTO:
    """Admin-only API gate.

    Verifies an admin-realm token against the admin identity store. A
    customer-realm token is rejected upstream at the signature/audience layer
    (different secret + audience). Bootstrap admins are setup-only and rejected.
    """
    if current_admin.is_bootstrap_admin:
        raise AdminForbiddenException()
    return current_admin
