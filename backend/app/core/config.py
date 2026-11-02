"""Configurações lidas de variáveis de ambiente (.env na raiz do projeto)."""
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str
    database_url_unpooled: str = ""
    secret_key: str

    @field_validator("database_url", "database_url_unpooled", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str) and v:
            # Render / Neon costumam fornecer postgres:// ou postgresql://.
            # O SQLAlchemy 2 com Psycopg 3 exige o driver postgresql+psycopg://
            if v.startswith("postgres://"):
                return "postgresql+psycopg://" + v[len("postgres://"):]
            if v.startswith("postgresql://") and not v.startswith("postgresql+"):
                return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v
    access_token_expire_minutes: int = 60
    log_level: str = "INFO"
    business_name: str = "Agenda"   # nome do negócio nos e-mails e mensagens (BUSINESS_NAME no .env)
    google_client_id: str = ""   # vazio = login com Google desligado
    # Redefinição de senha por e-mail
    frontend_url: str = "http://localhost:5173"   # usado para montar o link enviado por e-mail
    reset_token_minutes: int = 30
    # Aviso de novos cadastros ao dono, com Telegram. Token do @BotFather; chat id do dono (veja docs/telegram.md).
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Localização aproximada por IP. {ip} é substituído. Se falhar, a mensagem diz "indisponível".
    geoip_url: str = "https://ipapi.co/{ip}/json/"
    # Bot do CLIENTE (separado do bot de avisos do dono): token do @BotFather.
    customer_bot_token: str = ""
    # SÓ PARA TESTES: aceita o telefone digitado no Telegram (sem confirmação). No WhatsApp o número já vem confirmado.
    bot_allow_typed_phone: bool = False
    # Lembrete ao cliente antes do atendimento confirmado
    reminder_hours_before: int = 4          # quantas horas antes
    arrive_early_minutes: int = 20          # "chegue X minutos antes" (aparece no lembrete)
    reminder_quiet_start_hour: int = 21     # não manda lembrete entre 21h e 7h (horário local)
    reminder_quiet_end_hour: int = 7
    reminder_max_attempts: int = 10         # tentativas (1 por minuto) se o envio falhar
    bot_booking_days: int = 14        # quantos dias à frente o bot oferece
    bot_session_minutes: int = 30     # conversa parada por mais tempo volta ao menu
    # Push no app Android (FCM). Caminho do JSON da conta de serviço do Firebase (nunca no Git). Vazio = push desligado.
    fcm_service_account_file: str = ""
    push_max_age_minutes: int = 10   # não envia push de aviso mais velho que isso (ex.: ao ligar o push depois)
    verify_token_hours: int = 24   # validade do link de confirmação de e-mail
    mail_mode: str = "off"        # off = não envia | console = imprime no terminal (só para testes) | smtp = envia de verdade
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
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
    whatsapp_phone_number_id: str = ""
    # Chave de API de integração segura para o WhatsApp AI Agent
    whatsapp_agent_api_key: str = ""


settings = Settings()
