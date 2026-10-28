import logging

from fastapi import APIRouter, Depends, Request, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core import rate_limit
from app.core.config import settings
from app.core.middleware import client_ip
from app.core.security import DUMMY_HASH, create_access_token, verify_password
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.auth import AdminOut, LoginRequest, TokenResponse

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email, ip = data.email.lower(), client_ip(request)
    window = settings.login_lockout_minutes * 60
    # Bloqueio vale mesmo se a senha estiver certa: quem adivinha não deve saber quando acertou.
    for key in (f"email:{email}", f"ip:{ip}"):
        limit = settings.login_max_failures * (4 if key.startswith("ip:") else 1)  # IP tolera mais (vários e-mails)
        if rate_limit.login_failures.count(key, window) >= limit:
            logger.warning("login bloqueado por excesso de falhas (ip=%s)", ip)
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Muitas tentativas. Tente novamente mais tarde.",
                                headers={"Retry-After": str(rate_limit.login_failures.retry_after(key, window))})
    admin = db.scalar(select(AdminUser).where(AdminUser.email == email))
    ok = verify_password(data.password, admin.password_hash if admin else DUMMY_HASH)
    if not admin or not ok or not admin.is_active:
        logger.warning("login falhou (ip=%s)", ip)
        rate_limit.login_failures.hit(f"email:{email}", window)
        rate_limit.login_failures.hit(f"ip:{ip}", window)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
    rate_limit.login_failures.clear(f"email:{email}")
    return TokenResponse(access_token=create_access_token(admin.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: AdminUser = Depends(get_current_admin)):
    # O token é stateless: o logout real é o frontend descartá-lo. O token expira sozinho.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AdminOut)
def me(admin: AdminUser = Depends(get_current_admin)):
    return admin
