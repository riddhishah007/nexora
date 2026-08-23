import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import ROLE_ADMIN, ROLE_USER


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain an uppercase letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain a digit")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    email: EmailStr
    name: str | None
    role: str
    is_active: bool
    created_at: datetime


def validate_role(role: str) -> str:
    if role not in (ROLE_USER, ROLE_ADMIN):
        raise ValueError(f"Unknown role: {role}")
    return role
