"""Cria o usuário administrador. Uso: python backend/create_admin.py (pede e-mail, nome e senha)."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import AdminUser  # noqa: E402


def main():
    email = input("E-mail: ").strip().lower()
    name = input("Nome: ").strip()
    password = getpass.getpass("Senha (mín. 10 caracteres): ")
    if len(password) < 10 or password != getpass.getpass("Repita a senha: "):
        sys.exit("Senha curta demais ou não confere.")
    with SessionLocal() as db:
        db.add(AdminUser(email=email, name=name, password_hash=hash_password(password)))
        db.commit()
    print("Administrador criado.")


if __name__ == "__main__":
    main()
