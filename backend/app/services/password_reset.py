"""Regras de redefinição e troca de senha."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, hash_reset_token, new_reset_token
from app.models import AdminUser, PasswordResetToken


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_token(db: Session, admin: AdminUser) -> str:
    """Cria um link novo e invalida os anteriores ainda abertos. Devolve o token em texto (para o e-mail)."""
    db.execute(update(PasswordResetToken)
               .where(PasswordResetToken.admin_user_id == admin.id, PasswordResetToken.used_at.is_(None))
               .values(used_at=_now()))
    raw, token_hash = new_reset_token()
    db.add(PasswordResetToken(admin_user_id=admin.id, token_hash=token_hash,
                              expires_at=_now() + timedelta(minutes=settings.reset_token_minutes)))
    db.commit()
    return raw


def find_valid(db: Session, raw: str) -> tuple[PasswordResetToken, AdminUser] | None:
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(raw)))
    if row is None or row.used_at is not None or row.expires_at <= _now():
        return None
    admin = db.get(AdminUser, row.admin_user_id)
    if admin is None or not admin.is_active:
        return None
    return row, admin


def set_password(db: Session, admin: AdminUser, new_password: str) -> None:
    """Troca a senha e encerra todas as sessões antigas e links de redefinição abertos."""
    admin.password_hash = hash_password(new_password)
    admin.password_changed_at = _now()
    db.execute(update(PasswordResetToken)
               .where(PasswordResetToken.admin_user_id == admin.id, PasswordResetToken.used_at.is_(None))
               .values(used_at=_now()))
