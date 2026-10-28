from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    name: str
    has_password: bool


class GoogleLoginRequest(BaseModel):
    credential: str  # ID token entregue pelo Google ao navegador


class AuthConfig(BaseModel):
    google_client_id: str | None  # nulo = login com Google desligado


# Mesma regra do create_admin.py: mínimo de 10 caracteres.
NewPassword = Field(min_length=10, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = NewPassword


class ChangePasswordRequest(BaseModel):
    current_password: str | None = Field(default=None, max_length=128)  # dispensado só se o admin ainda não tem senha
    new_password: str = NewPassword
