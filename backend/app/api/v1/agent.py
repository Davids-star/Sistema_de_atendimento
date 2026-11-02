"""Rotas dedicadas para integração segura com o WhatsApp AI Agent (M2M).

Todas as rotas exigem autenticação via chave de integração (header `X-Agent-API-Key`
ou `Authorization: Bearer <key>`) e retornam respostas no envelope padronizado:
{
  "success": true | false,
  "data": { ... } | null,
  "error": { "code": "...", "message": "..." } | null
}
"""
from datetime import date, datetime, timezone
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import verify_agent_key
from app.db.session import get_db
from app.models import Appointment, Client, Service
from app.models.appointment import ACTIVE_STATUSES
from app.schemas.agent import (
    AgentAppointmentCancel,
    AgentAppointmentCreate,
    AgentAppointmentItem,
    AgentAppointmentReschedule,
    AgentAvailabilityItem,
    AgentClientCreate,
    AgentClientItem,
    AgentResponse,
    AgentServiceItem,
)
from app.services import appointments as appt_svc
from app.services import client_notify, owner_notify
from app.services.appointments import AppointmentError
from app.services.availability import TZ, slots_for_day
from app.services.clients import get_or_create_by_phone, normalize_phone

logger = logging.getLogger("app.agent")

router = APIRouter(
    prefix="/agent",
    tags=["WhatsApp AI Agent"],
    dependencies=[Depends(verify_agent_key)],
)


def _format_price(price_cents: int) -> str:
    val = price_cents / 100.0
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _to_appointment_item(appt: Appointment) -> AgentAppointmentItem:
    return AgentAppointmentItem(
        appointment_id=appt.id,
        client_id=appt.client_id,
        client_name=appt.client.name if appt.client else "",
        client_phone=appt.client.phone if appt.client else "",
        service_id=appt.service_id,
        service_name=appt.service.name if appt.service else "",
        status=appt.status,
        starts_at=appt.starts_at,
        ends_at=appt.ends_at,
        price_cents=appt.price_cents,
        price_formatted=_format_price(appt.price_cents),
        notes=appt.notes,
        cancelled_by=appt.cancelled_by,
    )


def _err_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": {"code": code, "message": message}},
    )


# ----------------------------------------------------------------------
# 1. Consultar Serviços e Preços
# ----------------------------------------------------------------------
@router.get("/services", response_model=AgentResponse[list[AgentServiceItem]])
@router.get("/servicos", response_model=AgentResponse[list[AgentServiceItem]], include_in_schema=False)
def list_services(db: Session = Depends(get_db)):
    """Lista todos os serviços ativos com duração e preços formatados."""
    services = db.scalars(select(Service).where(Service.is_active).order_by(Service.name)).all()
    data = [
        AgentServiceItem(
            id=s.id,
            name=s.name,
            duration_minutes=s.duration_minutes,
            price_cents=s.price_cents,
            price_formatted=_format_price(s.price_cents),
        )
        for s in services
    ]
    return AgentResponse.ok(data)


# ----------------------------------------------------------------------
# 1.1 Consultar Dias e Horários de Funcionamento do Estabelecimento
# ----------------------------------------------------------------------
@router.get("/business-hours", response_model=AgentResponse[list[dict]])
@router.get("/horarios-funcionamento", response_model=AgentResponse[list[dict]], include_in_schema=False)
def get_business_hours(db: Session = Depends(get_db)):
    """Retorna os horários e dias de funcionamento oficiais do estabelecimento."""
    from app.models.schedule import BusinessHours
    days = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    b_hours = db.scalars(select(BusinessHours).order_by(BusinessHours.weekday, BusinessHours.start_time)).all()
    data = [
        {
            "weekday": b.weekday,
            "day_name": days[b.weekday],
            "start_time": b.start_time.strftime("%H:%M"),
            "end_time": b.end_time.strftime("%H:%M"),
        }
        for b in b_hours
    ]
    return AgentResponse.ok(data)


# ----------------------------------------------------------------------
# 2. Consultar Horários Disponíveis
# ----------------------------------------------------------------------
@router.get("/availability", response_model=AgentResponse[AgentAvailabilityItem])
@router.get("/horarios-disponiveis", response_model=AgentResponse[AgentAvailabilityItem], include_in_schema=False)
def get_availability(
    date_: date = Query(..., alias="date", description="Data da consulta (YYYY-MM-DD)"),
    service_id: int = Query(..., description="ID do serviço pretendido"),
    db: Session = Depends(get_db),
):
    """Consulta horários disponíveis no expediente para uma data e serviço específicos."""
    service = db.get(Service, service_id)
    if service is None or not service.is_active:
        return _err_response("SERVICO_INEXISTENTE", "Serviço não encontrado ou inativo", status.HTTP_404_NOT_FOUND)

    slots = slots_for_day(db, date_, service)
    data = AgentAvailabilityItem(
        date=date_.isoformat(),
        service_id=service.id,
        duration_minutes=service.duration_minutes,
        available_slots=[s.astimezone(TZ).strftime("%H:%M") for s in slots],
        available_slots_iso=[s.isoformat() for s in slots],
    )
    return AgentResponse.ok(data)


# ----------------------------------------------------------------------
# 3. Localizar Cliente por Telefone
# ----------------------------------------------------------------------
@router.get("/clients/by-phone", response_model=AgentResponse[AgentClientItem])
@router.get("/clientes/por-telefone", response_model=AgentResponse[AgentClientItem], include_in_schema=False)
def get_client_by_phone(
    phone: str = Query(..., description="Número de WhatsApp com DDD"),
    db: Session = Depends(get_db),
):
    """Localiza um cliente pelo número de telefone normalizado."""
    try:
        norm_phone = normalize_phone(phone)
    except ValueError as e:
        return _err_response("DADOS_INVALIDOS", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)

    client = db.scalar(select(Client).where(Client.phone == norm_phone))
    if client is None:
        return _err_response("CLIENTE_NAO_ENCONTRADO", "Cliente não encontrado para este telefone", status.HTTP_404_NOT_FOUND)

    return AgentResponse.ok(AgentClientItem(id=client.id, name=client.name, phone=client.phone))


# ----------------------------------------------------------------------
# 4. Cadastrar Cliente
# ----------------------------------------------------------------------
@router.post("/clients", response_model=AgentResponse[AgentClientItem], status_code=status.HTTP_201_CREATED)
@router.post("/clientes", response_model=AgentResponse[AgentClientItem], status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_client(payload: AgentClientCreate, db: Session = Depends(get_db)):
    """Cadastra ou obtém um cliente pelo telefone com garantia de não duplicação."""
    try:
        norm_phone = normalize_phone(payload.phone)
    except ValueError as e:
        return _err_response("DADOS_INVALIDOS", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)

    client, created = get_or_create_by_phone(db, norm_phone, payload.name.strip())
    db.commit()
    db.refresh(client)
    return AgentResponse.ok(AgentClientItem(id=client.id, name=client.name, phone=client.phone, created=created))


# ----------------------------------------------------------------------
# 5. Criar Agendamento (Reserva com validação estrita em tempo real)
# ----------------------------------------------------------------------
@router.post("/appointments", response_model=AgentResponse[AgentAppointmentItem], status_code=status.HTTP_201_CREATED)
@router.post("/agendamentos", response_model=AgentResponse[AgentAppointmentItem], status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_appointment(
    payload: AgentAppointmentCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Cria um agendamento com validação estrita (strict=True) de disponibilidade em tempo real."""
    try:
        appt, _ = appt_svc.create_appointment(
            db=db,
            admin=None,
            client_id=None,
            client_phone=payload.client_phone,
            client_name=payload.client_name,
            service_id=payload.service_id,
            starts_at=payload.starts_at,
            notes=payload.notes,
            status="confirmed",
            source="whatsapp",
            strict=True,
        )
        db.commit()
        db.refresh(appt)
        # Notifica o dono/chefe imediatamente (ex.: via Telegram) sobre o novo agendamento feito pelo WhatsApp
        background.add_task(owner_notify.notify_owner_booking, appt.id, "WhatsApp")
    except AppointmentError as e:
        db.rollback()
        code = "HORARIO_INDISPONIVEL" if e.status_code == 409 else "DADOS_INVALIDOS"
        return _err_response(code, e.message, e.status_code)
    except ValueError as e:
        db.rollback()
        return _err_response("DADOS_INVALIDOS", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)
    except Exception as e:
        db.rollback()
        logger.exception("Erro inesperado ao criar agendamento pelo agente")
        return _err_response("ERRO_INTERNO", f"Falha ao registrar agendamento: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    return AgentResponse.ok(_to_appointment_item(appt))


# ----------------------------------------------------------------------
# 6. Consultar Agendamentos do Cliente
# ----------------------------------------------------------------------
@router.get("/appointments", response_model=AgentResponse[list[AgentAppointmentItem]])
@router.get("/agendamentos/cliente", response_model=AgentResponse[list[AgentAppointmentItem]], include_in_schema=False)
def list_client_appointments(
    phone: str = Query(..., description="Telefone do cliente para consulta"),
    upcoming: bool = Query(True, description="Filtrar apenas agendamentos futuros"),
    status_: str | None = Query(None, alias="status", description="Status específico (opcional)"),
    db: Session = Depends(get_db),
):
    """Retorna os agendamentos pertencentes exclusivamente ao número de telefone informado."""
    try:
        norm_phone = normalize_phone(phone)
    except ValueError as e:
        return _err_response("DADOS_INVALIDOS", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)

    client = db.scalar(select(Client).where(Client.phone == norm_phone))
    if client is None:
        return AgentResponse.ok([])

    query = select(Appointment).where(Appointment.client_id == client.id)
    if upcoming:
        query = query.where(
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.ends_at > datetime.now(timezone.utc),
        )
    if status_:
        query = query.where(Appointment.status == status_)

    query = query.order_by(Appointment.starts_at.asc())
    appointments = db.scalars(query).all()
    return AgentResponse.ok([_to_appointment_item(a) for a in appointments])


# ----------------------------------------------------------------------
# 7. Alterar / Remarcar Agendamento
# ----------------------------------------------------------------------
@router.patch("/appointments/{appointment_id}", response_model=AgentResponse[AgentAppointmentItem])
@router.patch("/agendamentos/{appointment_id}", response_model=AgentResponse[AgentAppointmentItem], include_in_schema=False)
def reschedule_appointment(
    appointment_id: int,
    payload: AgentAppointmentReschedule,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Altera a data/horário ou serviço de um agendamento com validação estrita de titularidade e disponibilidade."""
    try:
        norm_phone = normalize_phone(payload.phone)
    except ValueError as e:
        return _err_response("DADOS_INVALIDOS", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)

    existing = db.get(Appointment, appointment_id)
    if existing is None:
        return _err_response("AGENDAMENTO_NAO_ENCONTRADO", "Agendamento não encontrado", status.HTTP_404_NOT_FOUND)

    # Validação rigorosa de titularidade
    if existing.client.phone != norm_phone:
        return _err_response(
            "NAO_AUTORIZADO",
            "Este agendamento não pertence ao telefone informado",
            status.HTTP_403_FORBIDDEN,
        )

    changes: dict = {"starts_at": payload.starts_at}
    if payload.service_id is not None:
        changes["service_id"] = payload.service_id

    old_start = existing.starts_at
    try:
        appt, _ = appt_svc.update_appointment(
            db=db,
            admin=None,
            appointment_id=appointment_id,
            changes=changes,
            strict=True,
        )
        db.commit()
        db.refresh(appt)
    except AppointmentError as e:
        db.rollback()
        code = "HORARIO_INDISPONIVEL" if e.status_code == 409 else "DADOS_INVALIDOS"
        return _err_response(code, e.message, e.status_code)
    except Exception as e:
        db.rollback()
        logger.exception("Erro ao reagendar pelo agente")
        return _err_response("ERRO_INTERNO", f"Falha ao remarcar: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    if old_start is not None and appt.starts_at != old_start:
        background.add_task(client_notify.notify_rescheduled, appt.id, old_start.isoformat())

    return AgentResponse.ok(_to_appointment_item(appt))


# ----------------------------------------------------------------------
# 8. Cancelar Agendamento
# ----------------------------------------------------------------------
@router.post("/appointments/{appointment_id}/cancel", response_model=AgentResponse[AgentAppointmentItem])
@router.post("/agendamentos/{appointment_id}/cancelar", response_model=AgentResponse[AgentAppointmentItem], include_in_schema=False)
def cancel_appointment(
    appointment_id: int,
    payload: AgentAppointmentCancel,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Cancela um agendamento garantindo que o cliente só cancele suas próprias reservas."""
    try:
        norm_phone = normalize_phone(payload.phone)
    except ValueError as e:
        return _err_response("DADOS_INVALIDOS", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)

    existing = db.get(Appointment, appointment_id)
    if existing is None:
        return _err_response("AGENDAMENTO_NAO_ENCONTRADO", "Agendamento não encontrado", status.HTTP_404_NOT_FOUND)

    # Validação rigorosa de titularidade
    if existing.client.phone != norm_phone:
        return _err_response(
            "NAO_AUTORIZADO",
            "Este agendamento não pertence ao telefone informado",
            status.HTTP_403_FORBIDDEN,
        )

    try:
        cancel_actor = f"{existing.client.name} (WhatsApp Agent)"
        appt = appt_svc.change_status(db, admin=None, appointment_id=appointment_id, action="cancel", by=cancel_actor)
        if payload.reason:
            appt.notes = (appt.notes + f" | Cancelamento: {payload.reason}") if appt.notes else f"Cancelamento: {payload.reason}"
        db.commit()
        db.refresh(appt)
    except AppointmentError as e:
        db.rollback()
        return _err_response("OPERACAO_INVALIDA", e.message, e.status_code)
    except Exception as e:
        db.rollback()
        logger.exception("Erro ao cancelar agendamento pelo agente")
        return _err_response("ERRO_INTERNO", f"Falha ao cancelar: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    background.add_task(owner_notify.notify_owner_cancellation, appt.id)
    return AgentResponse.ok(_to_appointment_item(appt))
