from datetime import datetime

from pydantic import BaseModel, Field

from src.user.domain.dtos.user_dto import UserRole


class AuthTokenConfig(BaseModel):
    secret_key: str
    algorithm: str
    access_token_minutes: int
    refresh_token_days: int
    issuer: str
    audience: str
    leeway_seconds: int


class RefreshTokenDTO(BaseModel):
    id: int = Field(..., description="Refresh token row identifier")
    user_id: int = Field(..., description="User identifier")
    token_hash: str = Field(..., description="Stored refresh token hash")
    jti: str = Field(..., description="JWT identifier")
    expires_at: datetime = Field(..., description="Refresh token expiration time")
    revoked_at: datetime | None = Field(default=None, description="Revocation time")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class RefreshTokenCreateDTO(BaseModel):
    user_id: int
    token_hash: str
    jti: str
    expires_at: datetime
    revoked_at: datetime | None = None


class AdminSessionDTO(BaseModel):
    user_id: int
    username: str
    role: UserRole
