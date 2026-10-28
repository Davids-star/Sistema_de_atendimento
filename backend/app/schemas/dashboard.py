from datetime import date

from pydantic import BaseModel


class SummaryOut(BaseModel):
    date_from: date
    date_to: date
    total_appointments: int
    by_status: dict[str, int]
    revenue_cents: int            # faturamento registrado: só agendamentos CONCLUÍDOS
    expected_revenue_cents: int   # pendentes + confirmados (ainda não concluídos)
    no_show_rate: float | None    # ausências / (concluídos + ausências); None se não houver base
    unique_clients: int
    new_clients: int              # clientes cadastrados no período
    top_services: list[dict]      # [{service_id, name, count, revenue_cents}] só concluídos


class DayCount(BaseModel):
    date: date
    total: int
    by_status: dict[str, int]


class RevenuePoint(BaseModel):
    period: str   # "2030-01-07" (day) ou "2030-01" (month)
    revenue_cents: int
    completed_count: int


class RevenueOut(BaseModel):
    date_from: date
    date_to: date
    group_by: str
    total_cents: int
    points: list[RevenuePoint]
