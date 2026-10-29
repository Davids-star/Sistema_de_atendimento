"""Troca o e-mail da conta do dono e, se quiser, reenvia os avisos dos cadastros pendentes.

Uso: python backend/set_owner_email.py
O dono continua com a mesma senha e o mesmo acesso; muda só o e-mail (login, avisos e redefinição de senha).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services import owner as owner_service  # noqa: E402


def main():
    with SessionLocal() as db:
        current = owner_service.get_owner(db)
        print(f"E-mail atual do dono: {current.email}")
        new_email = input("Novo e-mail do dono (o seu e-mail de verdade): ").strip()
        try:
            owner_service.change_owner_email(db, new_email)
        except owner_service.OwnerError as e:
            if e.conflict is None:
                sys.exit(f"Erro: {e.message}")
            print(f"\nJá existe um cadastro comum com este e-mail (status: {e.conflict.status}), criado em testes ou por engano.")
            if input("Apagar esse cadastro para o e-mail ficar com o dono? [s/N] ").strip().lower() != "s":
                sys.exit("Nada foi alterado.")
            owner_service.change_owner_email(db, new_email, remove_conflict=True)
        print("E-mail do dono atualizado.")
        if input("Reenviar os avisos dos cadastros que estão aguardando liberação? [S/n] ").strip().lower() != "n":
            ids = owner_service.renotify_pending(db)
            print(f"{len(ids)} aviso(s) reenviado(s) para o novo e-mail.")


if __name__ == "__main__":
    main()
