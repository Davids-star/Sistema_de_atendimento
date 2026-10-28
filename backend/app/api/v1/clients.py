from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, Appointment, Client
from app.schemas.appointment import AppointmentOut
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.services import audit
from app.services.clients import normalize_phone

# Todas as rotas de clientes são administrativas.
router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_admin)])


def _phone_or_422(raw: str) -> str:
    try:
        return normalize_phone(raw)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _get_or_404(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado")
    return client


@router.get("", response_model=list[ClientOut])
def list_clients(q: str | None = Query(None, max_length=60, description="busca por nome ou telefone"),
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db)):
    query = select(Client).order_by(Client.name, Client.id).limit(limit).offset(offset)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Client.name.ilike(like), Client.phone.like(like)))
    return db.scalars(query).all()


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreate, db: Session = Depends(get_db),
                  admin: AdminUser = Depends(get_current_admin)):
    phone = _phone_or_422(data.phone)
    if db.scalar(select(Client.id).where(Client.phone == phone)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um cliente com este telefone")
    client = Client(name=data.name, phone=phone)
    db.add(client)
    db.flush()
    audit.record(db, admin, "create", "client", client.id, {"name": data.name})
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, client_id)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, data: ClientUpdate, db: Session = Depends(get_db),
                  admin: AdminUser = Depends(get_current_admin)):
    client = _get_or_404(db, client_id)
    changes = data.model_dump(exclude_unset=True)
    if any(v is None for v in changes.values()):
        raise HTTPException(422, "Campos não podem ser nulos")
    if "phone" in changes:
        changes["phone"] = _phone_or_422(changes["phone"])
        other = db.scalar(select(Client.id).where(Client.phone == changes["phone"], Client.id != client_id))
        if other:
            raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um cliente com este telefone")
    before = {k: getattr(client, k) for k in changes}
    for k, v in changes.items():
        setattr(client, k, v)
    audit.record(db, admin, "update", "client", client.id, {"before": before, "after": changes})
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}/appointments", response_model=list[AppointmentOut])
def client_appointments(client_id: int, db: Session = Depends(get_db)):
    _get_or_404(db, client_id)
    return db.scalars(select(Appointment).where(Appointment.client_id == client_id)
                      .order_by(Appointment.starts_at.desc())).all()
