from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# Membership in the admin_identity store IS the admin role — there is no
# `role` column (contrast with the customer `user` table). This constant is
# only the session marker the NiceGUI dashboard stores (IC-155-1).
ADMIN_SESSION_ROLE = "admin"


class AdminIdentityDTO(BaseModel):
    id: int = Field(..., description="Admin identity unique identifier")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password hash")
    permissions: list[str] = Field(
        default_factory=list, description="Admin page permission keys"
    )

    @field_validator("permissions", mode="before")
    @classmethod
    def _coerce_null_permissions(cls, v: object) -> object:
        return [] if v is None else v

    password_temporary: bool = Field(
        default=False, description="Must change password on next login"
    )
    is_bootstrap_admin: bool = Field(
        default=False, description="Seeded bootstrap account marker"
    )
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class AdminTokenConfig(BaseModel):
    secret_key: str
    algorithm: str
    access_token_minutes: int
    refresh_token_days: int
    issuer: str
    audience: str
    leeway_seconds: int


class AdminRefreshTokenDTO(BaseModel):
    id: int = Field(..., description="Refresh token row identifier")
    admin_id: int = Field(..., description="Admin identity identifier")
    token_hash: str = Field(..., description="Stored refresh token hash")
    jti: str = Field(..., description="JWT identifier")
    expires_at: datetime = Field(..., description="Refresh token expiration time")
    revoked_at: datetime | None = Field(default=None, description="Revocation time")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class AdminRefreshTokenCreateDTO(BaseModel):
    admin_id: int
    token_hash: str
    jti: str
    expires_at: datetime
    revoked_at: datetime | None = None


class AdminSessionDTO(BaseModel):
    user_id: int
    username: str
    role: str = ADMIN_SESSION_ROLE
    password_temporary: bool = False
    permissions: list[str] = Field(default_factory=list)


class BootstrapAdminDTO(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=255)


class CreateAdminAccountDTO(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    permissions: list[str] = Field(default_factory=list)


class UpdateAdminPermissionsDTO(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class ChangePasswordDTO(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)
    confirm_password: str = Field(min_length=8, max_length=255)
