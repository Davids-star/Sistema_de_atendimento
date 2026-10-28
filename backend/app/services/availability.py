"""Cálculo de horários livres. Função pura (sem banco) para ser fácil de testar."""
from datetime import date, datetime, time, timedelta, tzinfo

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
