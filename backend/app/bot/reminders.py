"""Lembrete ao cliente: X horas antes de um atendimento CONFIRMADO, pedindo para chegar alguns minutos antes.

Roda em um laço (uma verificação por minuto) dentro do programa do bot (customer_bot.py).
- Não manda de madrugada (padrão: entre 21h e 7h); atendimentos cedo recebem o lembrete às 7h.
- Cada lembrete sai uma vez só: o envio é "reservado" no banco antes (vale mesmo com dois programas rodando).
- Se o envio falhar, tenta de novo no minuto seguinte, até um limite de tentativas.
- Remarcar o horário zera o controle, e a cliente recebe um lembrete novo.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.bot import texts
from app.bot.types import Button
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Appointment
from app.services import client_notify
from app.services.availability import TZ

logger = logging.getLogger("app.reminders")


def in_quiet_hours(now: datetime) -> bool:
    hour = now.astimezone(TZ).hour
    start, end = settings.reminder_quiet_start_hour, settings.reminder_quiet_end_hour
    return hour >= start or hour < end if start > end else start <= hour < end


def due_appointments(db: Session, now: datetime) -> list[Appointment]:
    horizon = now + timedelta(hours=settings.reminder_hours_before)
    return list(db.scalars(select(Appointment).where(
        Appointment.status == "confirmed", Appointment.reminder_sent_at.is_(None),
        Appointment.reminder_attempts < settings.reminder_max_attempts,
        Appointment.starts_at > now, Appointment.starts_at <= horizon).order_by(Appointment.starts_at)))


def send_due(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    result = {"sent": 0, "failed": 0, "quiet": False, "disabled": False}
    if not settings.customer_bot_token:
        result["disabled"] = True
        return result
    if in_quiet_hours(now):
        result["quiet"] = True
        return result
    for appt in due_appointments(db, now):
        if not client_notify.targets(db, appt.client_id):
            continue   # cliente que nunca falou com o bot (ex.: agendada pelo painel): não há para onde enviar
        # Reserva atômica: só um processo consegue enviar este lembrete.
        claimed = db.execute(update(Appointment).where(
            Appointment.id == appt.id, Appointment.reminder_sent_at.is_(None),
            Appointment.reminder_attempts == appt.reminder_attempts)
            .values(reminder_attempts=Appointment.reminder_attempts + 1)).rowcount
        db.commit()
        if not claimed:
            continue
        delivered = client_notify.send(db, appt.client_id, texts.reminder(appt.service.name, appt.starts_at),
                                       [[Button(texts.BTN_MINE, "mine")]])
        if delivered:
            appt.reminder_sent_at = now
            db.commit()
            result["sent"] += 1
        else:
            result["failed"] += 1
    return result


def run_loop(interval: int = 60, stop=None) -> None:
    """Verifica a cada `interval` segundos. Erros são registrados e o laço continua."""
    while not (stop is not None and stop.is_set()):
        try:
            with SessionLocal() as db:
                result = send_due(db)
            if result["sent"] or result["failed"]:
                logger.info("lembretes: %d enviado(s), %d com falha", result["sent"], result["failed"])
        except Exception:
            logger.exception("falha no ciclo de lembretes")
        if stop is not None:
            stop.wait(interval)
        else:
            time.sleep(interval)
