"""Configurações lidas de variáveis de ambiente (.env na raiz do projeto)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 60
    log_level: str = "INFO"
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_app_secret: str = ""


settings = Settings()
