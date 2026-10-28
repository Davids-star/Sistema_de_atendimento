"""Redefine a senha de um administrador direto no servidor (último recurso, sem e-mail).

Uso: python backend/reset_admin_password.py
Quem consegue rodar este script já tem acesso ao servidor e ao banco, por isso não pede a senha antiga.
"""
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import AdminUser  # noqa: E402
from app.services import audit  # noqa: E402


def main():
    email = input("E-mail do administrador: ").strip().lower()
    password = getpass.getpass("Nova senha (mín. 10 caracteres): ")
    if len(password) < 10 or password != getpass.getpass("Repita a senha: "):
        sys.exit("Senha curta demais ou não confere.")
    with SessionLocal() as db:
        admin = db.scalar(select(AdminUser).where(AdminUser.email == email))
        if admin is None:
            sys.exit("Administrador não encontrado.")
        admin.password_hash = hash_password(password)
        admin.password_changed_at = datetime.now(timezone.utc)   # encerra as sessões antigas
        audit.record(db, None, "password_reset_cli", "admin_user", admin.id)
        db.commit()
    print("Senha redefinida. Sessões antigas foram encerradas.")


if __name__ == "__main__":
    main()
