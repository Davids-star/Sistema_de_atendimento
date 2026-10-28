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
    shop_timezone: str = "America/Sao_Paulo"
    # Origens do frontend autorizadas a chamar a API (separadas por vírgula). Vite usa a 5173.
    cors_origins: str = "http://localhost:5173"
    rate_limit_per_minute: int = 120   # por IP; 0 desliga
    login_max_failures: int = 5        # falhas seguidas (por e-mail e por IP) antes de bloquear
    login_lockout_minutes: int = 15
    test_database_url: str = ""        # se definido, os testes usam este banco em vez do principal
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_app_secret: str = ""


settings = Settings()
