"""Cria o usuário administrador. Uso: python backend/create_admin.py (pede e-mail, nome e senha).

Deixe a senha em branco para criar um administrador que só entra com Google (use o e-mail da conta Google)."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timezone  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import AdminUser  # noqa: E402


def main():
    email = input("E-mail: ").strip().lower()
    name = input("Nome: ").strip()
    password = getpass.getpass("Senha (mín. 10 caracteres; deixe em branco para entrar só com Google): ")
    if password and (len(password) < 10 or password != getpass.getpass("Repita a senha: ")):
        sys.exit("Senha curta demais ou não confere.")
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        # Criado por quem tem acesso ao servidor: já nasce confirmado, liberado e dono.
        db.add(AdminUser(email=email, name=name, password_hash=hash_password(password) if password else None,
                         email_verified_at=now, approved_at=now, is_owner=True))
        db.commit()
    print("Administrador criado.")


if __name__ == "__main__":
    main()
