from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, Appointment
from app.models.appointment import ACTIVE_STATUSES
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentResult, AppointmentUpdate
from app.services import appointments as svc
from app.services import client_notify, owner_notify
from app.services.availability import day_bounds

# Todas as rotas de agendamento exigem o administrador (o WhatsApp usará o serviço direto, com strict=True).
router = APIRouter(prefix="/appointments", tags=["appointments"], dependencies=[Depends(get_current_admin)])

STATUSES = "^(pending|confirmed|cancelled|completed|no_show)$"


@router.get("", response_model=list[AppointmentOut])
def list_appointments(date_from: date | None = None, date_to: date | None = None,
                      status_: str | None = Query(None, alias="status", pattern=STATUSES),
                      client_id: int | None = None,
                      needs_outcome: bool = Query(False, description="só os que já terminaram e ainda estão pendentes/confirmados"),
                      upcoming: bool = Query(False, description="só os pendentes/confirmados que ainda não terminaram (de agora em diante)"),
                      limit: int = Query(100, ge=1, le=500),
                      offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = select(Appointment).order_by(Appointment.starts_at, Appointment.id).limit(limit).offset(offset)
    if date_from:
        query = query.where(Appointment.starts_at >= day_bounds(date_from)[0])
    if date_to:
        query = query.where(Appointment.starts_at < day_bounds(date_to)[1])
    if status_:
        query = query.where(Appointment.status == status_)
    if client_id:
        query = query.where(Appointment.client_id == client_id)
    if upcoming:
        query = query.where(Appointment.status.in_(ACTIVE_STATUSES), Appointment.ends_at > datetime.now(timezone.utc))
    if needs_outcome:
        query = query.where(Appointment.status.in_(ACTIVE_STATUSES), Appointment.ends_at < datetime.now(timezone.utc))
    return db.scalars(query).all()


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(Appointment, appointment_id)
    if appt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agendamento não encontrado")
    return appt


@router.post("", response_model=AppointmentResult, status_code=status.HTTP_201_CREATED)
def create_appointment(data: AppointmentCreate, db: Session = Depends(get_db),
                       admin: AdminUser = Depends(get_current_admin)):
    appt, warnings = svc.create_appointment(
        db, admin=admin, client_id=data.client_id, client_phone=data.client_phone, client_name=data.client_name,
        service_id=data.service_id, starts_at=data.starts_at, notes=data.notes, status=data.status,
        source="admin", strict=False)
    db.commit()
    db.refresh(appt)
    return AppointmentResult.model_validate(appt).model_copy(update={"warnings": warnings})


@router.patch("/{appointment_id}", response_model=AppointmentResult)
def update_appointment(appointment_id: int, data: AppointmentUpdate, background: BackgroundTasks, db: Session = Depends(get_db),
                       admin: AdminUser = Depends(get_current_admin)):
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "Nenhum campo para alterar")
    if any(k in changes and changes[k] is None for k in ("starts_at", "service_id")):
        raise HTTPException(422, "starts_at e service_id não podem ser nulos")
    existing = db.get(Appointment, appointment_id)
    old_start = existing.starts_at if existing else None   # guarda o horário antigo para avisar a cliente
    appt, warnings = svc.update_appointment(db, admin, appointment_id, changes)
    db.commit()
    db.refresh(appt)
    if old_start is not None and appt.starts_at != old_start:
        background.add_task(client_notify.notify_rescheduled, appt.id, old_start.isoformat())   # depois de responder
    return AppointmentResult.model_validate(appt).model_copy(update={"warnings": warnings})


def _action(action: str):
    def endpoint(appointment_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
                 admin: AdminUser = Depends(get_current_admin)):
        appt = svc.change_status(db, admin, appointment_id, action)
        db.commit()
        db.refresh(appt)
        if action == "cancel":   # cancelado PELO PAINEL: avisa a cliente (cancelamento feito por ela no bot não passa por aqui)
            background.add_task(client_notify.notify_cancelled, appt.id)
            if not admin.is_owner:   # o dono sabe o que ele mesmo cancelou; os demais usuários geram aviso para ele
                background.add_task(owner_notify.notify_owner_cancellation, appt.id)
        return appt
    endpoint.__name__ = f"{action}_appointment"
    return endpoint


for _name, _path in (("confirm", "confirm"), ("cancel", "cancel"), ("complete", "complete"), ("no_show", "no-show")):
    router.add_api_route(f"/{{appointment_id}}/{_path}", _action(_name), methods=["POST"],
                         response_model=AppointmentOut, name=f"{_name}_appointment")
