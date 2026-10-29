from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.client import Client  # noqa: F401  (usado nos relacionamentos)
from app.models.service import Service  # noqa: F401

STATUSES = ("pending", "confirmed", "cancelled", "completed", "no_show")
ACTIVE_STATUSES = ("pending", "confirmed")  # ocupam o horário


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="ck_appointments_order"),
        CheckConstraint(
            "status IN ('pending','confirmed','cancelled','completed','no_show')",
            name="ck_appointments_status",
        ),
        CheckConstraint("source IN ('admin','whatsapp','telegram')", name="ck_appointments_source"),
        # Garantia final contra sobreposição, mesmo com requisições simultâneas:
        # o próprio PostgreSQL rejeita dois agendamentos ativos que se cruzem.
        ExcludeConstraint(
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            where=text("status IN ('pending','confirmed')"),
            using="gist",
            name="ex_appointments_no_overlap",
        ),
        Index("ix_appointments_starts_at", "starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    price_cents: Mapped[int]  # preço no momento do agendamento (histórico não muda se o serviço mudar)
    source: Mapped[str] = mapped_column(String(20), default="admin", server_default="admin")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Carregados junto com o agendamento (JOIN) para a API devolver nomes sem consultas extras.
    client: Mapped["Client"] = relationship(lazy="joined", innerjoin=True)
    service: Mapped["Service"] = relationship(lazy="joined", innerjoin=True)

    @property
    def client_name(self) -> str:
        return self.client.name

    @property
    def client_phone(self) -> str:
        return self.client.phone

    @property
    def service_name(self) -> str:
        return self.service.name
