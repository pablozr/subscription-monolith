from typing import TypedDict

from pydantic import BaseModel, EmailStr, Field


class UserGetDataResponse(TypedDict):
    user_id: int
    email: str


class UserGetResponse(TypedDict):
    status: bool
    message: str
    data: dict[str, UserGetDataResponse]


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    fullname: str = Field(min_length=8)
