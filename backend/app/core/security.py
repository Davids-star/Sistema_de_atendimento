"""Hash de senha (argon2) e tokens JWT."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_hasher = PasswordHash.recommended()  # argon2
# Hash falso usado para gastar o mesmo tempo quando o e-mail não existe (evita revelar quais e-mails são válidos).
DUMMY_HASH = _hasher.hash("senha-falsa-para-igualar-tempo")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


def password_version(admin) -> int:
    """Muda sempre que a senha é trocada (milissegundos). 0 = nunca trocada."""
    return int(admin.password_changed_at.timestamp() * 1000) if admin.password_changed_at else 0


def create_access_token(admin_id: int, pv: int = 0) -> str:
    """`pv` amarra o token à versão da senha: trocar a senha invalida todos os tokens anteriores."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(admin_id), "pv": pv, "exp": exp}, settings.secret_key, algorithm="HS256")


def decode_token_claims(token: str) -> tuple[int, int] | None:
    """(id do admin, versão da senha) ou None se o token for inválido/expirado."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return int(payload["sub"]), int(payload.get("pv", 0))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def decode_access_token(token: str) -> int | None:
    claims = decode_token_claims(token)
    return claims[0] if claims else None


def new_reset_token() -> tuple[str, str]:
    """(token para enviar ao usuário, hash para guardar no banco)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_reset_token(raw)


def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
