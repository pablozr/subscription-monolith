from pydantic import BaseModel


class LoginRequestModel(BaseModel):
    email: str
    password: str


class LoginGoogleRequestModel(BaseModel):
    token: str
