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
    interval_minutes: int | None,
    busy: list[Interval],
    tz: tzinfo,
    now: datetime,
) -> list[datetime]:
    """Horários de início livres em `day`.

    - Divide o expediente em janelas livres, descontando bloqueios e agendamentos ocupados.
    - O primeiro horário livre de cada janela começa no início dela (ex.: logo após o término do agendamento anterior).
    - Os próximos horários dentro da mesma janela avançam pela duração do serviço (ou intervalo configurado).
    - O serviço precisa terminar antes de fechar a janela / expediente.
    - Horários que já passaram não são oferecidos.
    """
    duration = timedelta(minutes=duration_minutes)
    step_minutes = interval_minutes or duration_minutes
    step = timedelta(minutes=step_minutes)
    slots: list[datetime] = []

    for start_t, end_t in sorted(hours):
        open_dt = datetime.combine(day, start_t, tzinfo=tz)
        close_dt = datetime.combine(day, end_t, tzinfo=tz)

        # Clampa e filtra ocupações deste expediente
        relevant_busy: list[Interval] = []
        for b_start, b_end in busy:
            s = max(b_start, open_dt)
            e = min(b_end, close_dt)
            if s < e:
                relevant_busy.append((s, e))

        # Mescla intervalos ocupados que se sobrepõem ou encostam
        relevant_busy.sort(key=lambda x: x[0])
        merged_busy: list[Interval] = []
        for s, e in relevant_busy:
            if not merged_busy:
                merged_busy.append((s, e))
            else:
                last_s, last_e = merged_busy[-1]
                if s <= last_e:
                    merged_busy[-1] = (last_s, max(last_e, e))
                else:
                    merged_busy.append((s, e))

        # Identifica as janelas livres dentro do expediente
        free_windows: list[Interval] = []
        curr = open_dt
        for b_start, b_end in merged_busy:
            if curr < b_start:
                free_windows.append((curr, b_start))
            curr = max(curr, b_end)
        if curr < close_dt:
            free_windows.append((curr, close_dt))

        # Em cada janela livre, os slots iniciam no começo da janela e avançam pelo passo
        for w_start, w_end in free_windows:
            cursor = w_start
            while cursor + duration <= w_end:
                if cursor > now:
                    slots.append(cursor)
                cursor += step

    return sorted(slots)


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
    settings = get_settings(db)
    # Se slot_interval_minutes configurado for estritamente maior que a duração, respeita a folga do admin;
    # caso contrário, o passo é determinado pela própria duração do serviço para encadeamento perfeito.
    interval = settings.slot_interval_minutes if (settings.slot_interval_minutes and settings.slot_interval_minutes > service.duration_minutes) else service.duration_minutes
    return compute_slots(day, service.duration_minutes, hours, interval,
                         [(s, e) for s, e in [*blocks, *appts]], TZ, now or datetime.now(timezone.utc))
