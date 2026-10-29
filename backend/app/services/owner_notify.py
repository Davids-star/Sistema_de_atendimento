"""Avisa o dono sobre um cadastro novo (e-mail + Telegram), com nome, celular e localização."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AdminUser
from app.services import geoip, mailer, telegram
from app.services.users import UserActionError  # noqa: F401  (reexport para quem importa daqui)

logger = logging.getLogger("app.notify")


def _format_phone(phone: str | None) -> str:
    if not phone:
        return "ainda não informado"
    import re
    m = re.match(r"^55(\d{2})(\d{4,5})(\d{4})$", phone)
    return f"({m.group(1)}) {m.group(2)}-{m.group(3)}" if m else phone


def build_message(user: AdminUser, location: str, via: str) -> str:
    when = (user.created_at or datetime.now(timezone.utc)).astimezone().strftime("%d/%m/%Y %H:%M")
    return (
        "Novo cadastro aguardando a sua liberação\n\n"
        f"Nome: {user.name}\n"
        f"Celular: {_format_phone(user.phone)}\n"
        f"E-mail: {user.email} (confirmado)\n"
        f"Entrou por: {via}\n"
        f"Localização: {location}\n"
        f"IP: {user.signup_ip or 'desconhecido'}\n"
        f"Quando: {when}\n\n"
        "Se não reconhece essa pessoa, não libere."
    )


def notify_owner_new_user(user_id: int) -> None:
    """Roda em segundo plano (com sessão própria). Envia uma vez só por usuário e nunca levanta erro."""
    try:
        with SessionLocal() as db:
            user = db.get(AdminUser, user_id)
            if user is None or user.approved or user.owner_notified_at is not None:
                return
            owners = db.scalars(select(AdminUser).where(AdminUser.is_owner, AdminUser.is_active)).all()
            location = geoip.describe_location(user.signup_ip)
            via = "Google" if user.google_sub else "e-mail e senha"
            text = build_message(user, location, via)

            sent = False
            for owner in owners:
                mailer.send_mail(owner.email, f"Novo cadastro: {user.name}", text +
                                 f"\n\nLibere ou recuse em: {settings.frontend_url.rstrip('/')}/usuarios")
                sent = True
            if telegram.enabled():
                sent = bool(telegram.send_message(settings.telegram_chat_id, text, telegram.approval_buttons(user.id))) or sent
            if sent:
                user.owner_notified_at = datetime.now(timezone.utc)
                db.commit()
    except Exception:
        logger.exception("falha ao avisar o dono sobre novo cadastro")
