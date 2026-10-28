from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_services_price_nonneg"),
        CheckConstraint("duration_minutes > 0", name="ck_services_duration_pos"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int]  # dinheiro em centavos, evita erro de ponto flutuante
    duration_minutes: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
