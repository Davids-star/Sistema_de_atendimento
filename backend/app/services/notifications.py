"""Central de notificações do painel (sino). Os avisos são gravados no banco, para cada pessoa que pode vê-los.

São criados DENTRO da transação do evento (ex.: ao cancelar): ou grava tudo junto ou nada, sem aviso "fantasma".
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.bot.texts import when
from app.models import AdminUser, Appointment, Notification

RETENTION_DAYS = 90


def panel_users(db: Session, *, owners_only: bool = False, exclude_user_id: int | None = None) -> list[AdminUser]:
    """Quem pode ver o painel (acesso liberado e ativo), opcionalmente só o dono e sem quem causou o evento."""
    query = select(AdminUser).where(AdminUser.is_active, AdminUser.approved_at.is_not(None))
    if owners_only:
        query = query.where(AdminUser.is_owner)
    if exclude_user_id is not None:
        query = query.where(AdminUser.id != exclude_user_id)
    return list(db.scalars(query))


def notify(db: Session, users: list[AdminUser], *, kind: str, title: str, body: str, link: str | None = None,
           ref: str | None = None, appointment_id: int | None = None) -> int:
    """Cria o aviso para cada usuário. `ref` impede duplicar o mesmo evento. Devolve quantos foram criados."""
    created = 0
    for user in users:
        stmt = insert(Notification).values(user_id=user.id, kind=kind, title=title[:120], body=body[:400], link=link,
                                           ref=ref, appointment_id=appointment_id)
        if ref:
            stmt = stmt.on_conflict_do_nothing(constraint="uq_notifications_user_ref")
        # RETURNING: só vem uma linha se de fato inseriu (o rowcount do PostgreSQL com ON CONFLICT não é confiável).
        if db.execute(stmt.returning(Notification.id)).first() is not None:
            created += 1
    # Faxina: avisos com mais de 90 dias saem (a lista nunca cresce sem limite).
    db.execute(delete(Notification).where(Notification.created_at < datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)))
    return created


def _label(appt: Appointment) -> str:
    return f"{appt.service.name}, {when(appt.starts_at)}"


def appointment_cancelled(db: Session, appt: Appointment, *, exclude_user_id: int | None) -> int:
    """Todos do painel são avisados, menos quem cancelou (ele já sabe)."""
    return notify(db, panel_users(db, exclude_user_id=exclude_user_id), kind="appointment_cancelled",
                  title="Agendamento cancelado",
                  body=f"{appt.client.name} · {_label(appt)}. Cancelado por {appt.cancelled_by or 'não informado'}.",
                  link="/agendamentos", ref=f"cancel:{appt.id}", appointment_id=appt.id)


def appointment_booked(db: Session, appt: Appointment) -> int:
    """Novo agendamento feito pela cliente no bot."""
    return notify(db, panel_users(db), kind="appointment_booked", title="Novo agendamento",
                  body=f"{appt.client.name} · {_label(appt)}.", link="/agendamentos", ref=f"booked:{appt.id}", appointment_id=appt.id)


def user_signup(db: Session, user: AdminUser) -> int:
    """Novo cadastro aguardando liberação: só o dono."""
    return notify(db, panel_users(db, owners_only=True), kind="user_signup", title="Novo cadastro aguardando liberação",
                  body=f"{user.name} ({user.email}) criou uma conta e espera a sua liberação.", link="/usuarios",
                  ref=f"signup:{user.id}")
