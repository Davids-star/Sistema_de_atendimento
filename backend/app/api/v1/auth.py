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
from app.schemas.auth import AdminOut, AuthConfig, GoogleLoginRequest, LoginRequest, TokenResponse
from app.services import audit
from app.services.google_auth import verify_google_token

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def _check_lockout(keys: list[str], ip: str, window: int) -> None:
    for key in keys:
        limit = settings.login_max_failures * (4 if key.startswith("ip:") else 1)  # IP tolera mais (vários e-mails)
        if rate_limit.login_failures.count(key, window) >= limit:
            logger.warning("login bloqueado por excesso de falhas (ip=%s)", ip)
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Muitas tentativas. Tente novamente mais tarde.",
                                headers={"Retry-After": str(rate_limit.login_failures.retry_after(key, window))})


@router.get("/config", response_model=AuthConfig)
def auth_config():
    """Público: o frontend pergunta se deve mostrar o botão "Entrar com Google"."""
    return AuthConfig(google_client_id=settings.google_client_id or None)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email, ip = data.email.lower(), client_ip(request)
    window = settings.login_lockout_minutes * 60
    # Bloqueio vale mesmo se a senha estiver certa: quem adivinha não deve saber quando acertou.
    _check_lockout([f"email:{email}", f"ip:{ip}"], ip, window)
    admin = db.scalar(select(AdminUser).where(AdminUser.email == email))
    has_password = bool(admin and admin.password_hash)
    # Sem hash (admin só-Google) ou sem usuário: compara com um hash falso só para gastar o mesmo tempo.
    ok = verify_password(data.password, admin.password_hash if has_password else DUMMY_HASH)
    # `has_password` é obrigatório: sem ele, a própria senha do hash falso "abriria" a conta de um admin só-Google.
    if not admin or not has_password or not ok or not admin.is_active:
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


@router.post("/google", response_model=TokenResponse)
def login_google(data: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Entrar com Google. Só funciona para um administrador JÁ cadastrado: nunca cria contas."""
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Login com Google não está configurado")
    ip = client_ip(request)
    window = settings.login_lockout_minutes * 60
    _check_lockout([f"ip:{ip}"], ip, window)

    def reject(message: str):
        logger.warning("login google recusado: %s (ip=%s)", message, ip)
        rate_limit.login_failures.hit(f"ip:{ip}", window)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, message)

    try:
        claims = verify_google_token(data.credential)
    except ValueError:
        reject("Credencial do Google inválida ou expirada")
    if not claims.get("email_verified"):
        reject("E-mail da conta Google não verificado")

    sub, email = claims["sub"], claims["email"].lower()
    admin = db.scalar(select(AdminUser).where(AdminUser.google_sub == sub))
    if admin is None:
        # Primeiro acesso com Google: liga a conta Google ao administrador que tem este e-mail.
        admin = db.scalar(select(AdminUser).where(AdminUser.email == email))
        if admin is None or admin.google_sub:  # e-mail desconhecido, ou já ligado a OUTRA conta Google
            reject("Esta conta Google não tem acesso ao painel")
        admin.google_sub = sub
        audit.record(db, admin, "google_link", "admin_user", admin.id)
    if not admin.is_active:
        reject("Esta conta Google não tem acesso ao painel")
    db.commit()
    return TokenResponse(access_token=create_access_token(admin.id))
