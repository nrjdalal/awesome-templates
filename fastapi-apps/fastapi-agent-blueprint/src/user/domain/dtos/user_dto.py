from datetime import datetime

from pydantic import BaseModel, Field


class UserDTO(BaseModel):
    id: int = Field(..., description="User unique identifier")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")
