import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=100)


class UserCreate(UserBase):
    password: str = Field(
        ..., min_length=8, max_length=128,
        description="Password must be at least 8 characters and at most 72 UTF-8 bytes",
    )

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=100)
    current_password: Optional[str] = Field(default=None, max_length=128, repr=False)

    @field_validator("username", "email", "full_name", mode="before")
    @classmethod
    def trim_profile_fields(cls, value, info):
        if isinstance(value, str):
            value = value.strip()
        if info.field_name == "full_name":
            return None if value == "" else value
        if value is None:
            raise ValueError("Username and email cannot be null")
        return value

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, value):
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value

    @model_validator(mode="after")
    def require_profile_field(self):
        if not self.model_fields_set.intersection({"username", "email", "full_name"}):
            raise ValueError("Provide at least one profile field")
        return self


class UserDeletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128, repr=False)
    confirmation: Literal["DELETE"]

    @field_validator("current_password")
    @classmethod
    def validate_password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserResponse(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
