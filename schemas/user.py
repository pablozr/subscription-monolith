from typing import TypedDict

from pydantic import BaseModel, EmailStr, Field


class UserGetDataResponse(TypedDict):
    id: int
    userId: int
    email: str
    fullname: str
    role: str


class UserGetResponse(TypedDict):
    status: bool
    message: str
    data: dict[str, UserGetDataResponse]


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    fullName: str = Field(min_length=8)


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    fullname: str | None = Field(default=None, min_length=8)
