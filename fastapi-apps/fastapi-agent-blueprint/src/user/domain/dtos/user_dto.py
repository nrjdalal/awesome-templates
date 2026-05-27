from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

UserRole = Literal["user", "admin"]
USER_ROLE_USER: UserRole = "user"
USER_ROLE_ADMIN: UserRole = "admin"


class UserDTO(BaseModel):
    id: int = Field(..., description="User unique identifier")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    role: UserRole = Field(default=USER_ROLE_USER, description="User role")
    password_temporary: bool = Field(
        default=False, description="Must change password on next login"
    )
    permissions: list[str] = Field(
        default_factory=list, description="Admin page permission keys"
    )

    @field_validator("permissions", mode="before")
    @classmethod
    def _coerce_null_permissions(cls, v: object) -> object:
        return [] if v is None else v

    is_bootstrap_admin: bool = Field(
        default=False, description="Seeded bootstrap account marker"
    )
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class BootstrapAdminUserDTO(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UpdateUserRoleDTO(BaseModel):
    role: UserRole


class UpdateAdminPermissionsDTO(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class ChangePasswordDTO(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)
    confirm_password: str = Field(min_length=8, max_length=255)


class CreateAdminAccountDTO(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    permissions: list[str] = Field(default_factory=list)
