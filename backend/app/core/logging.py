"""Logs da aplicação: console + arquivo rotativo (logs/app.log), cada linha com o id da requisição.

Regra: nunca logar senhas, tokens, corpo de requisições nem query strings.
"""
import logging
import logging.config
from contextvars import ContextVar

from app.core.config import ROOT, settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


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
        "formatters": {"std": {"format": fmt}},
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
        },
    })
