from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdminUser(Base):
    """Pessoa com conta no painel. Cadastrar-se não dá acesso: é preciso confirmar o e-mail
    (`email_verified_at`) e o dono precisa liberar (`approved_at`). Só o dono (`is_owner`) libera os demais."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))   # formato 5511999998888; ainda sem validação por código
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))   # nulo = acesso ainda não liberado
    # De onde veio o cadastro (para o dono decidir se libera). Dado pessoal: avisado no formulário de cadastro.
    signup_ip: Mapped[str | None] = mapped_column(String(45))
    owner_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))   # evita avisar o dono duas vezes
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
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

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def approved(self) -> bool:
        return self.approved_at is not None

    @property
    def status(self) -> str:
        if not self.is_active:
            return "disabled"
        if not self.email_verified:
            return "pending_email"
        return "active" if self.approved else "pending_approval"
