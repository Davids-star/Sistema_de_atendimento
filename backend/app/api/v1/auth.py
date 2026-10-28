import logging

from fastapi import APIRouter, Depends, Request, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.security import DUMMY_HASH, create_access_token, verify_password
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.auth import AdminOut, LoginRequest, TokenResponse

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    admin = db.scalar(select(AdminUser).where(AdminUser.email == data.email.lower()))
    ok = verify_password(data.password, admin.password_hash if admin else DUMMY_HASH)
    if not admin or not ok or not admin.is_active:
        logger.warning("login falhou (ip=%s)", request.client.host if request.client else "?")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
    return TokenResponse(access_token=create_access_token(admin.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: AdminUser = Depends(get_current_admin)):
    # O token é stateless: o logout real é o frontend descartá-lo. O token expira sozinho.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AdminOut)
def me(admin: AdminUser = Depends(get_current_admin)):
    return admin
