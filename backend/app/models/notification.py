from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Notification(Base):
    """Aviso dentro do sistema para UM usuário do painel (sino). Uma linha por destinatário."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "ref", name="uq_notifications_user_ref"),   # o mesmo evento não avisa a mesma pessoa duas vezes
        Index("ix_notifications_user_read", "user_id", "read_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))            # appointment_cancelled | appointment_booked | user_signup
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(400))
    link: Mapped[str | None] = mapped_column(String(120))    # tela do painel que o aviso abre (ex.: /agendamentos)
    ref: Mapped[str | None] = mapped_column(String(60))      # identifica o evento (ex.: "cancel:12") para não duplicar
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
