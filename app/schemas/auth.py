from datetime import datetime
from uuid import UUID

import re

from pydantic import Field, field_validator

from app.schemas.interpretation import ApiModel


class RegisterRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, alias="displayName", max_length=80)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("请输入有效的邮箱地址")
        return normalized


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return RegisterRequest.normalize_email(value)


class RefreshRequest(ApiModel):
    refresh_token: str = Field(alias="refreshToken", min_length=32, max_length=512)


class LogoutRequest(RefreshRequest):
    pass


class UserResponse(ApiModel):
    id: UUID
    email: str
    display_name: str | None = Field(alias="displayName")
    avatar_url: str | None = Field(alias="avatarUrl")
    email_verified: bool = Field(alias="emailVerified")
    is_anonymous: bool = Field(alias="isAnonymous")


class UpdateProfileRequest(ApiModel):
    display_name: str | None = Field(default=None, alias="displayName", max_length=80)
    avatar_url: str | None = Field(default=None, alias="avatarUrl", max_length=500)

    @field_validator("display_name", "avatar_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ChangePasswordRequest(ApiModel):
    current_password: str = Field(alias="currentPassword", min_length=8, max_length=128)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=128)


class DeleteAccountRequest(ApiModel):
    password: str = Field(min_length=8, max_length=128)
    confirmation: str

    @field_validator("confirmation")
    @classmethod
    def require_delete_confirmation(cls, value: str) -> str:
        if value != "DELETE":
            raise ValueError("账号注销确认无效")
        return value


class EmailTokenRequest(ApiModel):
    token: str = Field(min_length=32, max_length=512)


class ForgotPasswordRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return RegisterRequest.normalize_email(value)


class ResetPasswordRequest(EmailTokenRequest):
    new_password: str = Field(alias="newPassword", min_length=8, max_length=128)


class EmailActionResponse(ApiModel):
    message: str
    development_token: str | None = Field(default=None, alias="developmentToken")


class TokenResponse(ApiModel):
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    access_expires_at: datetime = Field(alias="accessExpiresAt")
    user: UserResponse
