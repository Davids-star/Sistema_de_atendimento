from pydantic import BaseModel, ConfigDict, EmailStr


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


class GoogleLoginRequest(BaseModel):
    credential: str  # ID token entregue pelo Google ao navegador


class AuthConfig(BaseModel):
    google_client_id: str | None  # nulo = login com Google desligado
