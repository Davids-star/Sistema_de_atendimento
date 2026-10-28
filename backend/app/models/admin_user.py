from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    # Nulo = administrador que só entra com Google (não tem senha).
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # Identificador estável da conta Google (campo "sub"), gravado no primeiro login com Google.
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Quando a senha foi trocada pela última vez. Sessões (tokens) emitidas antes disso deixam de valer.
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None
