from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_optional_admin
from app.db.session import get_db
from app.models import AdminUser, Appointment, Service
from app.schemas.service import ServiceCreate, ServiceOut, ServiceUpdate
from app.services import audit

router = APIRouter(prefix="/services", tags=["services"])


def _get_or_404(db: Session, service_id: int, admin: AdminUser | None) -> Service:
    service = db.get(Service, service_id)
    # Público só enxerga serviços ativos; inativos aparecem como inexistentes.
    if service is None or (not service.is_active and admin is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Serviço não encontrado")
    return service


@router.get("", response_model=list[ServiceOut])
def list_services(include_inactive: bool = False, db: Session = Depends(get_db),
                  admin: AdminUser | None = Depends(get_optional_admin)):
    if include_inactive and admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária")
    query = select(Service).order_by(Service.name)
    if not include_inactive:
        query = query.where(Service.is_active)
    return db.scalars(query).all()


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(service_id: int, db: Session = Depends(get_db),
                admin: AdminUser | None = Depends(get_optional_admin)):
    return _get_or_404(db, service_id, admin)


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(data: ServiceCreate, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(get_current_admin)):
    service = Service(**data.model_dump())
    db.add(service)
    db.flush()
    audit.record(db, admin, "create", "service", service.id, data.model_dump())
    db.commit()
    db.refresh(service)
    return service


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, data: ServiceUpdate, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(get_current_admin)):
    service = _get_or_404(db, service_id, admin)
    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "price_cents", "duration_minutes", "is_active"):
        if field in changes and changes[field] is None:
            raise HTTPException(422, f"{field} não pode ser nulo")
    before = {k: getattr(service, k) for k in changes}
    for k, v in changes.items():
        setattr(service, k, v)
    audit.record(db, admin, "update", "service", service.id, {"before": before, "after": changes})
    db.commit()
    db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(get_current_admin)):
    """Exclui de vez se nunca foi usado; senão apenas desativa (preserva o histórico)."""
    service = _get_or_404(db, service_id, admin)
    used = db.scalar(select(exists().where(Appointment.service_id == service.id)))
    if used:
        service.is_active = False
        audit.record(db, admin, "deactivate", "service", service.id)
    else:
        db.delete(service)
        audit.record(db, admin, "delete", "service", service.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
