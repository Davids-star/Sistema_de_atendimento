"""Gestão de quem tem acesso ao painel. Só o dono usa estas rotas."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.user import UserOut
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])

STATUSES = "^(pending_email|pending_approval|active|disabled)$"


def _target(db: Session, user_id: int) -> AdminUser:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    return user


@router.get("", response_model=list[UserOut])
def list_users(status_: str | None = Query(None, alias="status", pattern=STATUSES), db: Session = Depends(get_db),
               _: AdminUser = Depends(get_current_owner)):
    users = db.scalars(select(AdminUser).order_by(AdminUser.created_at.desc(), AdminUser.id.desc())).all()
    return [u for u in users if status_ is None or u.status == status_]


def _run(action, db: Session, owner: AdminUser, user_id: int) -> AdminUser:
    user = _target(db, user_id)
    try:
        action(db, owner, user)
    except users_service.UserActionError as e:
        raise HTTPException(e.status_code, e.message)
    return user


@router.post("/{user_id}/approve", response_model=UserOut)
def approve(user_id: int, db: Session = Depends(get_db), owner: AdminUser = Depends(get_current_owner)):
    return _run(users_service.approve, db, owner, user_id)


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate(user_id: int, db: Session = Depends(get_db), owner: AdminUser = Depends(get_current_owner)):
    return _run(users_service.deactivate, db, owner, user_id)


@router.post("/{user_id}/reactivate", response_model=UserOut)
def reactivate(user_id: int, db: Session = Depends(get_db), owner: AdminUser = Depends(get_current_owner)):
    return _run(users_service.reactivate, db, owner, user_id)
