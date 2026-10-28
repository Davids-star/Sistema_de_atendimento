from datetime import datetime, time

from sqlalchemy import CheckConstraint, DateTime, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BusinessHours(Base):
    """Um intervalo de funcionamento. Pode haver mais de um por dia (ex.: pausa de almoço).
    Dia sem nenhuma linha = fechado. weekday: 0=segunda ... 6=domingo."""

    __tablename__ = "business_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_business_hours_weekday"),
        CheckConstraint("start_time < end_time", name="ck_business_hours_order"),
        UniqueConstraint("weekday", "start_time", name="uq_business_hours_day_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int]
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class BlockedTime(Base):
    __tablename__ = "blocked_times"
    __table_args__ = (CheckConstraint("starts_at < ends_at", name="ck_blocked_times_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
