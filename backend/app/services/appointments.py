"""Regras de agendamento.

A garantia final contra horários duplicados é a restrição de exclusão do PostgreSQL
(`ex_appointments_no_overlap`): mesmo com requisições simultâneas, só uma passa.
Aqui apenas traduzimos esse erro do banco em uma resposta amigável (409).
"""
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AdminUser, Appointment, BlockedTime, BusinessHours, Client, Service
from app.services import audit
from app.services.availability import TZ, slots_for_day
from app.services.clients import get_or_create_by_phone, normalize_phone

OVERLAP_CONSTRAINT = "ex_appointments_no_overlap"

# ação -> (status de origem permitidos, status final)
TRANSITIONS = {
    "confirm": ({"pending"}, "confirmed"),
    "cancel": ({"pending", "confirmed"}, "cancelled"),
    "complete": ({"pending", "confirmed"}, "completed"),
    "no_show": ({"pending", "confirmed"}, "no_show"),
}
ONLY_AFTER_START = {"complete", "no_show"}


class AppointmentError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message, self.status_code = message, status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _flush_or_conflict(db: Session, apply: Callable[[], None]) -> None:
    """Executa `apply` (que adiciona/altera o agendamento) e grava dentro de um savepoint.

    As alterações precisam acontecer DENTRO do savepoint: assim, em caso de conflito, o banco
    desfaz só elas e a transação da requisição continua válida."""
    try:
        with db.begin_nested():
            apply()
            db.flush()
    except IntegrityError as e:
        if OVERLAP_CONSTRAINT in str(e.orig):
            raise AppointmentError("Esse horário já está ocupado por outro agendamento") from e
        raise


def _warnings(db: Session, starts: datetime, ends: datetime) -> list[str]:
    """Avisos para o admin, que pode agendar mesmo assim."""
    out = []
    local_s, local_e = starts.astimezone(TZ), ends.astimezone(TZ)
    hours = db.scalars(select(BusinessHours).where(BusinessHours.weekday == local_s.weekday())).all()
    inside = local_s.date() == local_e.date() and any(
        h.start_time <= local_s.time() and local_e.time() <= h.end_time for h in hours)
    if not inside:
        out.append("Fora do horário de funcionamento")
    if db.scalar(select(BlockedTime.id).where(BlockedTime.starts_at < ends, BlockedTime.ends_at > starts).limit(1)):
        out.append("Coincide com um horário bloqueado")
    return out


def _reject_past(starts: datetime) -> None:
    if starts < _now():
        raise AppointmentError("Não é possível agendar em um horário que já passou", 422)


def _active_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if service is None or not service.is_active:
        raise AppointmentError("Serviço não encontrado ou inativo", 422)
    return service


def _check_strict(db: Session, starts: datetime, service: Service) -> None:
    if starts not in slots_for_day(db, starts.astimezone(TZ).date(), service):
        raise AppointmentError("Horário indisponível")


def get_locked(db: Session, appointment_id: int) -> Appointment:
    """Busca com trava de linha: duas ações simultâneas no mesmo agendamento ficam em fila."""
    appt = db.scalar(select(Appointment).where(Appointment.id == appointment_id).with_for_update())
    if appt is None:
        raise AppointmentError("Agendamento não encontrado", 404)
    return appt


def create_appointment(db: Session, *, admin: AdminUser | None, client_id: int | None, client_phone: str | None,
                       client_name: str | None, service_id: int, starts_at: datetime, notes: str | None,
                       status: str, source: str, strict: bool,
                       conversation_id: int | None = None) -> tuple[Appointment, list[str]]:
    """Nunca agenda no passado. Se o cliente faltou, marque `no_show`: isso libera o horário.
    strict=True (WhatsApp): só aceita horários realmente livres e dentro do expediente.
    strict=False (admin): aceita fora do expediente/sobre bloqueios (com avisos), mas nunca sobre outro agendamento."""
    _reject_past(starts_at)
    service = _active_service(db, service_id)
    if client_id is not None:
        client = db.get(Client, client_id)
        if client is None:
            raise AppointmentError("Cliente não encontrado", 404)
    else:
        try:
            phone = normalize_phone(client_phone)
        except ValueError as e:
            raise AppointmentError(str(e), 422)
        client = db.scalar(select(Client).where(Client.phone == phone))
        if client is None:
            if not client_name:
                raise AppointmentError("Cliente novo: informe client_name", 422)
            client, _ = get_or_create_by_phone(db, phone, client_name)

    if strict:
        _check_strict(db, starts_at, service)
    ends_at = starts_at + timedelta(minutes=service.duration_minutes)
    appt = Appointment(client_id=client.id, service_id=service.id, starts_at=starts_at, ends_at=ends_at,
                       status=status, price_cents=service.price_cents, source=source, notes=notes,
                       conversation_id=conversation_id)
    _flush_or_conflict(db, lambda: db.add(appt))
    warnings = [] if strict else _warnings(db, starts_at, ends_at)
    audit.record(db, admin, "create", "appointment", appt.id,
                 {"client_id": client.id, "service_id": service.id, "starts_at": starts_at.isoformat(),
                  "status": status, "source": source, "warnings": warnings})
    return appt, warnings


def update_appointment(db: Session, admin: AdminUser, appointment_id: int, changes: dict) -> tuple[Appointment, list[str]]:
    appt = get_locked(db, appointment_id)
    if appt.status not in ("pending", "confirmed"):
        raise AppointmentError("Só é possível alterar agendamentos pendentes ou confirmados")
    before = {k: getattr(appt, k) for k in changes}
    new_service_id = changes.get("service_id")
    if new_service_id is not None and new_service_id != appt.service_id:
        service = _active_service(db, new_service_id)
        new_price = service.price_cents  # novo serviço = novo preço
    else:
        service, new_price = db.get(Service, appt.service_id), appt.price_cents
    new_start = changes.get("starts_at") or appt.starts_at
    if new_start != appt.starts_at:
        _reject_past(new_start)  # remarcar para o passado também não vale
    def apply():
        if "notes" in changes:
            appt.notes = changes["notes"]
        appt.service_id, appt.price_cents = service.id, new_price
        if new_start != appt.starts_at:
            appt.reminder_sent_at, appt.reminder_attempts = None, 0   # novo horário: o lembrete deve ser enviado de novo
        appt.starts_at = new_start
        appt.ends_at = new_start + timedelta(minutes=service.duration_minutes)

    _flush_or_conflict(db, apply)
    warnings = _warnings(db, appt.starts_at, appt.ends_at) if {"starts_at", "service_id"} & changes.keys() else []
    audit.record(db, admin, "update", "appointment", appt.id,
                 {"before": {k: str(v) for k, v in before.items()},
                  "after": {k: str(v) for k, v in changes.items()}, "warnings": warnings})
    return appt, warnings


def change_status(db: Session, admin: AdminUser | None, appointment_id: int, action: str) -> Appointment:
    allowed_from, target = TRANSITIONS[action]
    appt = get_locked(db, appointment_id)
    if appt.status not in allowed_from:
        raise AppointmentError(f"Não é possível executar '{action}' em um agendamento {appt.status}")
    if action in ONLY_AFTER_START and appt.starts_at > _now():
        raise AppointmentError("Só é possível registrar conclusão/ausência depois do início do horário")
    old, appt.status = appt.status, target
    audit.record(db, admin, action, "appointment", appt.id, {"from": old, "to": target})
    return appt
