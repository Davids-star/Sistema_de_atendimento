"""Logs da aplicação: console + arquivo rotativo (logs/app.log), cada linha com o id da requisição.

Regra: nunca logar senhas, tokens, corpo de requisições nem query strings.
"""
import logging
import logging.config
import re
from contextvars import ContextVar

from app.core.config import ROOT, settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Token de bot do Telegram aparece em URLs (/bot123456:ABC.../getUpdates). Bibliotecas de rede como a urllib3 registram
# essas URLs sozinhas (ao tentar de novo, ou em DEBUG), então escondemos o token em TUDO que sai nos logs.
_BOT_TOKEN = re.compile(r"bot\d{6,12}:[A-Za-z0-9_-]{20,}|\b\d{6,12}:[A-Za-z0-9_-]{30,}(?![A-Za-z0-9_-])")


def redact(text: str) -> str:
    return _BOT_TOKEN.sub("<token oculto>", text)


class RedactingFormatter(logging.Formatter):
    """Aplica o redact no texto FINAL (mensagem + erro detalhado), por isso nada escapa."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    fmt = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"rid": {"()": RequestIdFilter}},
        "formatters": {"std": {"()": RedactingFormatter, "format": fmt}},
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "std", "filters": ["rid"]},
            "file": {
                "class": "logging.handlers.RotatingFileHandler", "formatter": "std", "filters": ["rid"],
                "filename": str(log_dir / "app.log"), "maxBytes": 5_000_000,
                "backupCount": 5, "encoding": "utf-8",
            },
        },
        "root": {"level": settings.log_level.upper(), "handlers": ["console", "file"]},
        "loggers": {
            # O acesso HTTP já é registrado pelo middleware (com id e tempo); evita duplicar.
            "uvicorn.access": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},   # em DEBUG escreve cada URL (com token) a cada requisição
        },
    })
