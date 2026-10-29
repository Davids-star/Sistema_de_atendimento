"""Avisos do sistema para a CLIENTE, pelo canal em que ela conversa com o bot (hoje, o Telegram).

Só avisa quem já conversou com o bot: o sistema não tem como achar o Telegram de alguém só pelo telefone.
Mudanças feitas pela própria cliente no bot não geram aviso (ela já sabe).
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bot import texts
from app.bot.channels import telegram
from app.bot.types import Button, Reply
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Appointment, Conversation
from app.models.appointment import ACTIVE_STATUSES

logger = logging.getLogger("app.client_notify")


def targets(db: Session, client_id: int) -> list[Conversation]:
    """Conversas onde a cliente pode ser avisada. Exige número confirmado pelo canal (no modo de teste, vale também o digitado)."""
    rows = db.scalars(select(Conversation).where(
        Conversation.client_id == client_id, Conversation.channel == "telegram", Conversation.external_id.is_not(None))).all()
    return [c for c in rows if c.phone_verified or settings.bot_allow_typed_phone]


def send(db: Session, client_id: int, text: str, buttons: list[list[Button]] | None = None) -> int:
    """Devolve em quantas conversas a mensagem foi entregue."""
    delivered = 0
    for conv in targets(db, client_id):
        if telegram.send_reply(conv.external_id, Reply(text, buttons or [])):
            delivered += 1
    return delivered


def _rescheduled(db: Session, appointment_id: int, old_start: datetime) -> int:
    appt = db.get(Appointment, appointment_id)
    if appt is None or appt.status not in ACTIVE_STATUSES or appt.starts_at == old_start:
        return 0
    return send(db, appt.client_id, texts.rescheduled(appt.service.name, old_start, appt.starts_at))


def _cancelled(db: Session, appointment_id: int) -> int:
    appt = db.get(Appointment, appointment_id)
    if appt is None or appt.status != "cancelled":
        return 0
    return send(db, appt.client_id, texts.cancelled_by_studio(appt.service.name, appt.starts_at),
                [[Button(texts.BTN_BOOK, "book")]])


# Funções chamadas em segundo plano pelas rotas do painel (abrem a própria sessão; falhas nunca chegam a quem usa o painel).
def notify_rescheduled(appointment_id: int, old_start_iso: str) -> None:
    try:
        with SessionLocal() as db:
            _rescheduled(db, appointment_id, datetime.fromisoformat(old_start_iso))
    except Exception:
        logger.exception("falha ao avisar a cliente da remarcacao")


def notify_cancelled(appointment_id: int) -> None:
    try:
        with SessionLocal() as db:
            _cancelled(db, appointment_id)
    except Exception:
        logger.exception("falha ao avisar a cliente do cancelamento")
