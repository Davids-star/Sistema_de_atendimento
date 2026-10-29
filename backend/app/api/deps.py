"""Dependências compartilhadas pelas rotas: quem está logado e o que pode fazer.

Camadas:
  get_current_user   qualquer conta logada (mesmo sem acesso liberado ainda)
  get_current_admin  conta logada E liberada pelo dono  -> rotas do painel
  get_current_owner  dono                               -> gestão de usuários
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token_claims, password_version
from app.db.session import get_db
from app.models import AdminUser

bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AdminUser | None:
    if creds is None:
        return None
    claims = decode_token_claims(creds.credentials)
    user = db.get(AdminUser, claims[0]) if claims else None
    # Token de antes da última troca de senha não vale mais.
    if user is None or not user.is_active or claims[1] != password_version(user):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def get_current_user(user: AdminUser | None = Depends(get_optional_user)) -> AdminUser:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def get_optional_admin(user: AdminUser | None = Depends(get_optional_user)) -> AdminUser | None:
    """Para rotas públicas que mostram mais coisas ao administrador. Conta não liberada = visitante."""
    return user if user is not None and user.approved else None


def get_current_admin(user: AdminUser = Depends(get_current_user)) -> AdminUser:
    if not user.approved:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu acesso ainda não foi liberado pelo dono da barbearia")
    return user


def get_current_owner(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    if not admin.is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas o dono pode fazer isso")
    return admin
