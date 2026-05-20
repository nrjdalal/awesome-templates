from src.auth.domain.dtos.auth_dto import AdminSessionDTO, AuthTokenConfig
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException
from src.auth.domain.services.auth_service import AuthService
from src.auth.interface.server.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairData,
)
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN, UserDTO
from src.user.domain.protocols.user_service_protocol import UserServiceProtocol
from src.user.interface.server.schemas.user_schema import CreateUserRequest


class AuthUseCase:
    def __init__(
        self,
        auth_service: AuthService,
        user_service: UserServiceProtocol,
        token_config: AuthTokenConfig,
    ) -> None:
        self._auth_service = auth_service
        self._user_service = user_service
        self._token_config = token_config

    async def register(self, request: RegisterRequest) -> TokenPairData:
        user = await self._user_service.create_data(
            CreateUserRequest(**request.model_dump())
        )
        return await self._token_pair_for_user(user)

    async def login(self, request: LoginRequest) -> TokenPairData:
        user = await self._auth_service.verify_credentials(
            request.username,
            request.password,
        )
        return await self._token_pair_for_user(user)

    async def admin_login(self, request: LoginRequest) -> AdminSessionDTO:
        user = await self._auth_service.verify_credentials(
            request.username,
            request.password,
        )
        return self._admin_session_for_user(user)

    async def get_admin_session(self, user_id: int) -> AdminSessionDTO:
        user = await self._auth_service.get_user_by_id(user_id)
        return self._admin_session_for_user(user)

    async def refresh(self, request: RefreshTokenRequest) -> TokenPairData:
        access_token, refresh_token = await self._auth_service.rotate_refresh_token(
            request.refresh_token
        )
        user = await self._auth_service.get_user_from_access_token(access_token)
        return self._token_pair(access_token, refresh_token, user)

    async def logout(self, request: LogoutRequest) -> bool:
        return await self._auth_service.revoke_refresh_token(request.refresh_token)

    async def get_current_user(self, token: str) -> UserDTO:
        return await self._auth_service.get_user_from_access_token(token)

    async def _token_pair_for_user(self, user: UserDTO) -> TokenPairData:
        access_token, refresh_token = await self._auth_service.issue_token_pair(user)
        return self._token_pair(access_token, refresh_token, user)

    def _token_pair(
        self,
        access_token: str,
        refresh_token: str,
        user: UserDTO,
    ) -> TokenPairData:
        return TokenPairData(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",  # noqa: S106
            expires_in=60 * self._token_config.access_token_minutes,
            user=user,
        )

    def _admin_session_for_user(self, user: UserDTO) -> AdminSessionDTO:
        if user.role != USER_ROLE_ADMIN:
            raise InvalidCredentialsException()
        return AdminSessionDTO(user_id=user.id, username=user.username, role=user.role)
