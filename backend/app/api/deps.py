"""Dependências compartilhadas pelas rotas: autenticação do administrador."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token_claims, password_version
from app.db.session import get_db
from app.models import AdminUser

bearer = HTTPBearer(auto_error=False)


def get_optional_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AdminUser | None:
    if creds is None:
        return None
    claims = decode_token_claims(creds.credentials)
    admin = db.get(AdminUser, claims[0]) if claims else None
    # Token de antes da última troca de senha não vale mais.
    if admin is None or not admin.is_active or claims[1] != password_version(admin):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado",
                            headers={"WWW-Authenticate": "Bearer"})
    return admin


def get_current_admin(admin: AdminUser | None = Depends(get_optional_admin)) -> AdminUser:
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária",
                            headers={"WWW-Authenticate": "Bearer"})
    return admin
