"""Troca do e-mail do dono (é nele que chegam os avisos de cadastro e as redefinições de senha)."""
import re
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog
from app.services import audit, owner_notify


class OwnerError(Exception):
    def __init__(self, message: str, conflict: AdminUser | None = None):
        super().__init__(message)
        self.message, self.conflict = message, conflict


def get_owner(db: Session) -> AdminUser:
    owner = db.scalar(select(AdminUser).where(AdminUser.is_owner, AdminUser.is_active).order_by(AdminUser.id))
    if owner is None:
        raise OwnerError("Nenhum dono ativo encontrado.")
    return owner


def change_owner_email(db: Session, new_email: str, *, remove_conflict: bool = False) -> AdminUser:
    """Muda o e-mail do dono. Se existir um cadastro comum (sem acesso) com esse e-mail, só o remove com `remove_conflict`."""
    email = new_email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise OwnerError("E-mail inválido.")
    owner = get_owner(db)
    if owner.email == email:
        raise OwnerError("Este já é o e-mail do dono.")

    other = db.scalar(select(AdminUser).where(AdminUser.email == email, AdminUser.id != owner.id))
    if other is not None:
        if other.is_owner or other.approved:
            raise OwnerError("Este e-mail já pertence a um usuário com acesso ao painel.")
        if not remove_conflict:
            raise OwnerError("Já existe um cadastro (sem acesso) com este e-mail.", conflict=other)
        # Cadastro de teste sem acesso: sai da frente. O histórico de auditoria é mantido, sem o vínculo.
        db.execute(update(AuditLog).where(AuditLog.admin_user_id == other.id).values(admin_user_id=None))
        db.delete(other)
        db.flush()

    owner.email = email
    if owner.email_verified_at is None:
        owner.email_verified_at = datetime.now(timezone.utc)
    owner.google_sub = None   # o próximo login com Google desse e-mail volta a se ligar a esta conta
    audit.record(db, owner, "owner_email_change", "admin_user", owner.id)
    db.commit()
    return owner


def renotify_pending(db: Session) -> list[int]:
    """Reenvia ao dono o aviso dos cadastros que aguardam liberação (ex.: avisos que foram para o endereço errado)."""
    pending = [u for u in db.scalars(select(AdminUser).order_by(AdminUser.id)) if u.status == "pending_approval"]
    for user in pending:
        user.owner_notified_at = None
    db.commit()
    for user in pending:
        owner_notify.notify_owner_new_user(user.id)
    return [u.id for u in pending]
