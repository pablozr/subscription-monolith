from pydantic import BaseModel


class LoginRequestModel(BaseModel):
    email: str
    password: str


class LoginGoogleRequestModel(BaseModel):
    token: str


class ForgetPasswordRequestModel(BaseModel):
    email: str


class ValidateCodeRequest(BaseModel):
    code: str


class UpdatePasswordRequest(BaseModel):
    password: str
