from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterPayload(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=160)


class LoginPayload(BaseModel):
    email: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    display_name: str | None = None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
