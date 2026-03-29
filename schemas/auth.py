from pydantic import BaseModel, EmailStr, Field


class AuthBaseModel(BaseModel):
    model_config = {"extra": "forbid"}


class LoginRequestModel(AuthBaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginGoogleRequestModel(AuthBaseModel):
    token: str = Field(min_length=10, max_length=4096)


class ForgetPasswordRequestModel(AuthBaseModel):
    email: EmailStr


class ValidateCodeRequest(AuthBaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class UpdatePasswordRequest(AuthBaseModel):
    password: str = Field(min_length=8, max_length=128)
