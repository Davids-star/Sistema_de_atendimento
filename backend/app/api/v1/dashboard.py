"""Indicadores do painel. Datas são interpretadas no fuso do negócio."""
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import Appointment, Client, Service
from app.models.appointment import STATUSES
from app.schemas.dashboard import DayCount, RevenueOut, RevenuePoint, SummaryOut
from app.services.availability import TZ, day_bounds

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_admin)])

MAX_DAYS = 366


def _month_end(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


class Period:
    """Período `date_from..date_to` (inclusive). Padrão: o mês atual inteiro."""

    def __init__(self, date_from: date | None = Query(None), date_to: date | None = Query(None)):
        self.date_from = date_from or datetime.now(TZ).date().replace(day=1)
        self.date_to = date_to or _month_end(self.date_from)
        if self.date_to < self.date_from:
            raise HTTPException(422, "date_to deve ser igual ou posterior a date_from")
        if (self.date_to - self.date_from).days >= MAX_DAYS:
            raise HTTPException(422, f"Período máximo de {MAX_DAYS} dias")
        self.start = day_bounds(self.date_from)[0]
        self.end = day_bounds(self.date_to)[1]

    def where(self):
        return (Appointment.starts_at >= self.start, Appointment.starts_at < self.end)


def _local_day(col=Appointment.starts_at):
    return cast(func.timezone(TZ.key, col), Date)


@router.get("/summary", response_model=SummaryOut)
def summary(p: Period = Depends(), db: Session = Depends(get_db)):
    counts = dict.fromkeys(STATUSES, 0)
    counts.update(dict(db.execute(select(Appointment.status, func.count()).where(*p.where())
                                  .group_by(Appointment.status)).all()))
    money = lambda *sts: db.scalar(select(func.coalesce(func.sum(Appointment.price_cents), 0))
                                   .where(*p.where(), Appointment.status.in_(sts)))
    base = counts["completed"] + counts["no_show"]
    top = db.execute(
        select(Service.id, Service.name, func.count(), func.sum(Appointment.price_cents))
        .join(Service, Service.id == Appointment.service_id)
        .where(*p.where(), Appointment.status == "completed")
        .group_by(Service.id, Service.name).order_by(func.count().desc(), Service.name).limit(5)).all()
    return SummaryOut(
        date_from=p.date_from, date_to=p.date_to, total_appointments=sum(counts.values()),
        scheduled_appointments=sum(n for k, n in counts.items() if k != "cancelled"), by_status=counts,
        revenue_cents=money("completed"), expected_revenue_cents=money("pending", "confirmed"),
        no_show_rate=round(counts["no_show"] / base, 4) if base else None,
        # "Atendidos" = quem teve ao menos um atendimento CONCLUÍDO (cancelado, ausente e pendente não contam).
        unique_clients=db.scalar(select(func.count(func.distinct(Appointment.client_id))).where(*p.where(), Appointment.status == "completed")),
        new_clients=db.scalar(select(func.count()).select_from(Client).where(
            Client.created_at >= p.start, Client.created_at < p.end)),
        top_services=[{"service_id": i, "name": n, "count": c, "revenue_cents": int(r)} for i, n, c, r in top])


@router.get("/appointments-by-day", response_model=list[DayCount])
def appointments_by_day(p: Period = Depends(), db: Session = Depends(get_db)):
    day = _local_day().label("day")  # um único objeto, para o GROUP BY casar com o SELECT
    rows = db.execute(select(day, Appointment.status, func.count()).where(*p.where())
                      .group_by(day, Appointment.status)).all()
    days: dict[date, dict[str, int]] = {}
    for d, status, n in rows:
        days.setdefault(d, dict.fromkeys(STATUSES, 0))[status] = n
    out = []
    for i in range((p.date_to - p.date_from).days + 1):  # inclui dias sem agendamentos (facilita gráficos)
        d = p.date_from + timedelta(days=i)
        by = days.get(d, dict.fromkeys(STATUSES, 0))
        out.append(DayCount(date=d, total=sum(by.values()), by_status=by))
    return out


@router.get("/revenue", response_model=RevenueOut)
def revenue(p: Period = Depends(), group_by: Literal["day", "month"] = "day", db: Session = Depends(get_db)):
    """Faturamento registrado = soma do preço dos agendamentos CONCLUÍDOS, no dia do atendimento."""
    bucket = _local_day() if group_by == "day" else cast(func.date_trunc("month", func.timezone(TZ.key, Appointment.starts_at)), Date)
    rows = db.execute(select(bucket, func.sum(Appointment.price_cents), func.count())
                      .where(*p.where(), Appointment.status == "completed").group_by(bucket).order_by(bucket)).all()
    fmt = "%Y-%m-%d" if group_by == "day" else "%Y-%m"
    points = [RevenuePoint(period=d.strftime(fmt), revenue_cents=int(total), completed_count=n) for d, total, n in rows]
    return RevenueOut(date_from=p.date_from, date_to=p.date_to, group_by=group_by,
                      total_cents=sum(x.revenue_cents for x in points), points=points)
