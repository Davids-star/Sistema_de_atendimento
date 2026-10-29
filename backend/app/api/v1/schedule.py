"""Funcionamento do negócio: horários, bloqueios, configurações e disponibilidade."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, BlockedTime, BusinessHours, Service
from app.schemas.schedule import (
    AvailabilityOut, BlockedTimeCreate, BlockedTimeOut, BusinessHoursItem,
    BusinessHoursUpdate, SettingsOut, SettingsUpdate,
)
from app.services import audit
from app.services.availability import slots_for_day
from app.services.shop_settings import get_settings

router = APIRouter(tags=["schedule"])


# ---------- Configurações ----------
@router.get("/settings", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin)):
    return get_settings(db)


@router.put("/settings", response_model=SettingsOut)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db),
                    admin: AdminUser = Depends(get_current_admin)):
    s = get_settings(db)
    before = s.slot_interval_minutes
    s.slot_interval_minutes = data.slot_interval_minutes
    audit.record(db, admin, "update", "settings", 1,
                 {"before": {"slot_interval_minutes": before}, "after": data.model_dump()})
    db.commit()
    return s


# ---------- Horário de funcionamento ----------
@router.get("/business-hours", response_model=list[BusinessHoursItem])
def read_business_hours(db: Session = Depends(get_db)):
    return db.scalars(select(BusinessHours).order_by(BusinessHours.weekday, BusinessHours.start_time)).all()


@router.put("/business-hours", response_model=list[BusinessHoursItem])
def replace_business_hours(data: BusinessHoursUpdate, db: Session = Depends(get_db),
                           admin: AdminUser = Depends(get_current_admin)):
    db.execute(delete(BusinessHours))
    db.add_all(BusinessHours(**i.model_dump()) for i in data.items)
    audit.record(db, admin, "replace", "business_hours", None,
                 {"items": [i.model_dump(mode="json") for i in data.items]})
    db.commit()
    return db.scalars(select(BusinessHours).order_by(BusinessHours.weekday, BusinessHours.start_time)).all()


# ---------- Bloqueios ----------
@router.get("/blocked-times", response_model=list[BlockedTimeOut])
def list_blocked(from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                 db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin)):
    query = select(BlockedTime).order_by(BlockedTime.starts_at)
    if from_:
        query = query.where(BlockedTime.ends_at > from_)
    if to:
        query = query.where(BlockedTime.starts_at < to)
    return db.scalars(query).all()


@router.post("/blocked-times", response_model=BlockedTimeOut, status_code=status.HTTP_201_CREATED)
def create_blocked(data: BlockedTimeCreate, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(get_current_admin)):
    block = BlockedTime(**data.model_dump())
    db.add(block)
    db.flush()
    audit.record(db, admin, "create", "blocked_time", block.id, data.model_dump(mode="json"))
    db.commit()
    db.refresh(block)
    return block


@router.delete("/blocked-times/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blocked(block_id: int, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(get_current_admin)):
    block = db.get(BlockedTime, block_id)
    if block is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloqueio não encontrado")
    db.delete(block)
    audit.record(db, admin, "delete", "blocked_time", block_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Disponibilidade (pública: o cliente do WhatsApp também consulta) ----------
@router.get("/availability", response_model=AvailabilityOut)
def availability(date_: date = Query(alias="date"), service_id: int = Query(), db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if service is None or not service.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Serviço não encontrado")

    slots = slots_for_day(db, date_, service)
    return AvailabilityOut(date=date_.isoformat(), service_id=service.id,
                           duration_minutes=service.duration_minutes, slots=slots)
