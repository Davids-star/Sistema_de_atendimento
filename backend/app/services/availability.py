"""Cálculo de horários livres. Função pura (sem banco) para ser fácil de testar."""
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models import Appointment, BlockedTime, BusinessHours, Service
from app.models.appointment import ACTIVE_STATUSES
from app.services.shop_settings import get_settings

TZ = ZoneInfo(app_settings.shop_timezone)
Interval = tuple[datetime, datetime]


def compute_slots(
    day: date,
    duration_minutes: int,
    hours: list[tuple[time, time]],
    interval_minutes: int,
    busy: list[Interval],
    tz: tzinfo,
    now: datetime,
) -> list[datetime]:
    """Horários de início livres em `day`.

    - Os inícios andam de `interval_minutes` em `interval_minutes`, a partir da abertura de cada expediente.
    - O serviço precisa terminar até o fim do expediente.
    - `busy` junta bloqueios e agendamentos ativos; encostar (terminar quando o outro começa) é permitido.
    - Horários que já passaram não são oferecidos.
    """
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=interval_minutes)
    slots: list[datetime] = []
    for start_t, end_t in sorted(hours):
        cursor = datetime.combine(day, start_t, tzinfo=tz)
        close = datetime.combine(day, end_t, tzinfo=tz)
        while cursor + duration <= close:
            end = cursor + duration
            if cursor > now and not any(cursor < b_end and end > b_start for b_start, b_end in busy):
                slots.append(cursor)
            cursor += step
    return slots


def day_bounds(day: date) -> Interval:
    start = datetime.combine(day, time.min, tzinfo=TZ)
    return start, start + timedelta(days=1)


def slots_for_day(db: Session, day: date, service: Service, now: datetime | None = None) -> list[datetime]:
    """Consulta o banco e devolve os horários livres de `day` para `service`."""
    hours = [(h.start_time, h.end_time) for h in
             db.scalars(select(BusinessHours).where(BusinessHours.weekday == day.weekday()))]
    day_start, day_end = day_bounds(day)
    blocks = db.execute(select(BlockedTime.starts_at, BlockedTime.ends_at)
                        .where(BlockedTime.starts_at < day_end, BlockedTime.ends_at > day_start)).all()
    appts = db.execute(select(Appointment.starts_at, Appointment.ends_at)
                       .where(Appointment.status.in_(ACTIVE_STATUSES),
                              Appointment.starts_at < day_end, Appointment.ends_at > day_start)).all()
    return compute_slots(day, service.duration_minutes, hours, get_settings(db).slot_interval_minutes,
                         [(s, e) for s, e in [*blocks, *appts]], TZ, now or datetime.now(timezone.utc))
