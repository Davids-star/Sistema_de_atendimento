from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


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
    phone: str | None
    has_password: bool
    email_verified: bool
    approved: bool          # acesso ao painel liberado pelo dono
    is_owner: bool
    status: str             # pending_email | pending_approval | active | disabled


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


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=25)
    email: EmailStr
    password: str = NewPassword
    password_confirm: str = Field(max_length=128)

    @model_validator(mode="after")
    def _same_password(self):
        if self.password != self.password_confirm:
            raise ValueError("A confirmação da senha não confere")
        return self


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ProfileUpdate(BaseModel):
    """Campos opcionais: só o que for enviado é alterado."""
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=8, max_length=25)
