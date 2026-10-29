"""Confirmação de e-mail: prova que a pessoa tem acesso à caixa de entrada que informou."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_reset_token, new_reset_token
from app.models import AdminUser, EmailVerificationToken


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_token(db: Session, user: AdminUser) -> str:
    """Gera um link novo e invalida os anteriores ainda abertos. Devolve o token em texto (para o e-mail)."""
    db.execute(update(EmailVerificationToken)
               .where(EmailVerificationToken.admin_user_id == user.id, EmailVerificationToken.used_at.is_(None))
               .values(used_at=_now()))
    raw, token_hash = new_reset_token()
    db.add(EmailVerificationToken(admin_user_id=user.id, token_hash=token_hash,
                                  expires_at=_now() + timedelta(hours=settings.verify_token_hours)))
    db.commit()
    return raw


def consume(db: Session, raw: str) -> AdminUser | None:
    """Valida o link, marca o e-mail como confirmado e gasta o token. None se inválido, usado ou expirado."""
    row = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_reset_token(raw)))
    if row is None or row.used_at is not None or row.expires_at <= _now():
        return None
    user = db.get(AdminUser, row.admin_user_id)
    if user is None or not user.is_active:
        return None
    row.used_at = _now()
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    return user
