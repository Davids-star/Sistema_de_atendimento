"""Registro dos aparelhos (app Android) que recebem push."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, DeviceToken

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    platform: str = Field(default="android", pattern="^android$")

    @field_validator("token")
    @classmethod
    def _plausible(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_:\-\.]+", v):   # tokens do FCM só têm esses caracteres
            raise ValueError("token inválido")
        return v


class DeviceOut(BaseModel):
    registered: bool = True


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def register(data: DeviceIn, db: Session = Depends(get_db), me: AdminUser = Depends(get_current_admin)):
    """Registra (ou atualiza) o aparelho. Se o mesmo aparelho entrar com outra conta, o token passa para ela."""
    device = db.scalar(select(DeviceToken).where(DeviceToken.token == data.token))
    if device is None:
        db.add(DeviceToken(user_id=me.id, token=data.token, platform=data.platform))
    else:
        device.user_id = me.id
        device.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return DeviceOut()


@router.post("/remove", status_code=status.HTTP_204_NO_CONTENT)
def unregister(data: DeviceIn, db: Session = Depends(get_db), me: AdminUser = Depends(get_current_admin)):
    """Chamado ao sair: este aparelho para de receber os avisos desta conta. Só apaga o que é da própria pessoa."""
    db.execute(delete(DeviceToken).where(DeviceToken.token == data.token, DeviceToken.user_id == me.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
