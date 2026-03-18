from typing import TypedDict


class UserGetDataResponse(TypedDict):
    user_id: int
    email: str


class UserGetResponse(TypedDict):
    status: bool
    message: str
    data: dict[str, UserGetDataResponse]
