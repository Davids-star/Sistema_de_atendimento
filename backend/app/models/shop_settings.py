from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ShopSettings(Base):
    """Configurações do negócio. Sempre uma única linha (id = 1)."""

    __tablename__ = "shop_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_shop_settings_singleton"),
        CheckConstraint("slot_interval_minutes BETWEEN 5 AND 240", name="ck_shop_settings_interval"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    # De quanto em quanto tempo começam os horários oferecidos (ex.: 30 -> 9:00, 9:30, 10:00...)
    slot_interval_minutes: Mapped[int] = mapped_column(default=30, server_default="30")
    # WhatsApp do dono para onde o bot encaminha a cliente que precisa falar com uma pessoa (formato 5511999998888).
    contact_phone: Mapped[str | None] = mapped_column(String(20))
