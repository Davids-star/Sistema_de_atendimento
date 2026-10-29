"""Push para o app Android via Firebase Cloud Messaging (API HTTP v1).

- O envio sai de um despachante em segundo plano que varre as notificações novas (assim um aviso nunca atrasa quem o causou).
- Só o erro UNREGISTERED apaga o token do aparelho (regra oficial do FCM). 429/500/503 pedem nova tentativa com espera.
- Tokens e a chave da conta de serviço nunca aparecem nos logs.
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import service_account
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import DeviceToken, Notification

logger = logging.getLogger("app.push")
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
CHANNEL_ID = "avisos"   # o app Android cria um canal com este mesmo id (senão o Android usa o canal padrão)

_creds = None
_creds_lock = threading.Lock()


def configured() -> bool:
    return bool(settings.fcm_service_account_file)


def _credentials():
    global _creds
    with _creds_lock:
        if _creds is None:
            _creds = service_account.Credentials.from_service_account_file(settings.fcm_service_account_file, scopes=[SCOPE])
        if not _creds.valid:
            _creds.refresh(google_requests.Request())
        return _creds


def build_message(token: str, title: str, body: str, link: str | None, notification_id: int, kind: str) -> dict:
    data = {"notification_id": str(notification_id), "kind": kind}   # valores de "data" precisam ser texto
    if link:
        data["link"] = link
    return {"message": {"token": token, "notification": {"title": title, "body": body}, "data": data,
                        "android": {"priority": "HIGH", "notification": {"channel_id": CHANNEL_ID}}}}


def _error_code(response) -> str | None:
    try:
        error = response.json().get("error", {})
    except Exception:
        return None
    for detail in error.get("details", []):
        if detail.get("errorCode"):
            return detail["errorCode"]
    return error.get("status")


def send_one(token: str, payload: dict, *, attempts: int = 2) -> str:
    """'ok' | 'unregistered' (apagar o token) | 'error' (não repetir igual) | 'failed' (esgotou as tentativas)."""
    creds = _credentials()
    url = ENDPOINT.format(project=creds.project_id)
    for attempt in range(1, attempts + 1):
        try:
            r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {creds.token}"}, timeout=15)
        except Exception:
            logger.warning("falha de rede ao falar com o FCM")
            r = None
        if r is not None and r.ok:
            return "ok"
        code = _error_code(r) if r is not None else None
        if r is not None and (code == "UNREGISTERED" or (r.status_code == 404 and code == "NOT_FOUND")):
            return "unregistered"
        retryable = r is None or r.status_code in (500, 503) or code in ("UNAVAILABLE", "INTERNAL")
        if r is not None and not retryable:
            logger.warning("FCM recusou o envio (%s %s)", r.status_code, code)   # sem token, sem corpo da resposta
            return "error"
        if attempt < attempts:
            time.sleep(min(2 ** attempt, 8))   # espera crescente: 2 s, 4 s, 8 s (nunca mais que isso)
    return "failed"


def send_to_user(db: Session, user_id: int, notification: Notification) -> dict:
    result = {"ok": 0, "removed": 0, "error": 0, "failed": 0}
    for device in db.scalars(select(DeviceToken).where(DeviceToken.user_id == user_id)).all():
        payload = build_message(device.token, notification.title, notification.body, notification.link, notification.id, notification.kind)
        outcome = send_one(device.token, payload)
        if outcome == "unregistered":
            db.execute(delete(DeviceToken).where(DeviceToken.id == device.id))
            db.commit()
            result["removed"] += 1
        else:
            result[outcome] += 1
    return result


def dispatch_pending(db: Session, now: datetime | None = None) -> int:
    """Envia o push das notificações novas que ainda não foram despachadas. Devolve quantas foram tratadas."""
    if not configured():
        return 0
    now = now or datetime.now(timezone.utc)
    pending = db.scalars(select(Notification).where(
        Notification.pushed_at.is_(None), Notification.created_at > now - timedelta(minutes=settings.push_max_age_minutes))
        .order_by(Notification.id).limit(50)).all()
    handled = 0
    for n in pending:
        # Reserva atômica: se houver dois processos, só um envia este aviso.
        claimed = db.execute(update(Notification).where(Notification.id == n.id, Notification.pushed_at.is_(None))
                             .values(pushed_at=now)).rowcount
        db.commit()
        if not claimed:
            continue
        handled += 1
        if n.read_at is None:   # quem já leu dentro do app não precisa de push
            send_to_user(db, n.user_id, n)
    return handled


def run_loop(interval: float = 5, stop: threading.Event | None = None) -> None:
    while not (stop is not None and stop.is_set()):
        try:
            with SessionLocal() as db:
                dispatch_pending(db)
        except Exception:
            logger.exception("falha no despachante de push")
        if stop is not None:
            stop.wait(interval)
        else:
            time.sleep(interval)
