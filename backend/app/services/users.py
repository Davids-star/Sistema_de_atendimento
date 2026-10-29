"""Regras de liberar, recusar e reativar usuários. Usadas pelo painel (HTTP) e pelo Telegram."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AdminUser
from app.services import audit


class UserActionError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message, self.status_code = message, status_code


def approve(db: Session, owner: AdminUser, user: AdminUser, via: str = "painel") -> bool:
    """Libera o acesso. Devolve False se já estava liberado (nada mudou)."""
    if not user.is_active:
        raise UserActionError("Este usuário está desativado. Reative-o primeiro.")
    if not user.email_verified:
        raise UserActionError("O e-mail deste usuário ainda não foi confirmado")
    if user.approved:
        return False
    user.approved_at = datetime.now(timezone.utc)
    audit.record(db, owner, "user_approve", "admin_user", user.id, {"via": via})
    db.commit()
    return True


def deactivate(db: Session, owner: AdminUser, user: AdminUser, via: str = "painel") -> bool:
    """Desativa (ou recusa) e encerra as sessões abertas. Devolve False se já estava desativado."""
    if user.id == owner.id:
        raise UserActionError("Você não pode desativar a si mesmo")
    if user.is_owner:
        raise UserActionError("O dono não pode ser alterado por aqui")
    if not user.is_active:
        return False
    user.is_active = False
    user.password_changed_at = datetime.now(timezone.utc)   # invalida os tokens já emitidos
    audit.record(db, owner, "user_deactivate", "admin_user", user.id, {"via": via})
    db.commit()
    return True


def reactivate(db: Session, owner: AdminUser, user: AdminUser) -> bool:
    if user.is_active:
        return False
    user.is_active = True
    audit.record(db, owner, "user_reactivate", "admin_user", user.id)
    db.commit()
    return True
