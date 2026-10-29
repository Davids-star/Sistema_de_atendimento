"""Central de notificações: cada pessoa só enxerga e altera os PRÓPRIOS avisos."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, Notification
from app.schemas.notification import NotificationList, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _unread(db: Session, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None)))


@router.get("", response_model=NotificationList)
def list_notifications(limit: int = Query(20, ge=1, le=50), after_id: int | None = Query(None, ge=0),
                       unread_only: bool = False, db: Session = Depends(get_db), me: AdminUser = Depends(get_current_admin)):
    """Mais recentes primeiro. `after_id` devolve só o que chegou depois daquele aviso (para atualizar a tela)."""
    query = select(Notification).where(Notification.user_id == me.id).order_by(Notification.id.desc()).limit(limit)
    if after_id is not None:
        query = query.where(Notification.id > after_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return NotificationList(items=db.scalars(query).all(), unread_count=_unread(db, me.id))


@router.post("/read-all")
def read_all(db: Session = Depends(get_db), me: AdminUser = Depends(get_current_admin)):
    result = db.execute(update(Notification).where(Notification.user_id == me.id, Notification.read_at.is_(None))
                        .values(read_at=datetime.now(timezone.utc)))
    db.commit()
    return {"updated": result.rowcount}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: Session = Depends(get_db), me: AdminUser = Depends(get_current_admin)):
    item = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == me.id))
    if item is None:   # inexistente OU de outra pessoa: mesma resposta
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notificação não encontrada")
    if item.read_at is None:
        item.read_at = datetime.now(timezone.utc)
        db.commit()
    return item
