from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None = None
    profile_picture_url: str | None = None
    auth_provider: str
    created_at: datetime
    username: str | None = None
    bio: str = ""
    avatar_url: str | None = None
    profile_visibility: str = "public"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
