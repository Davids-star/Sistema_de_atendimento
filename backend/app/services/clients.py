"""Regras de clientes: normalização de telefone e busca/criação sem duplicar."""
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Client


def normalize_phone(raw: str) -> str:
    """Devolve só dígitos com DDI (E.164 sem '+'). Ex.: '(11) 99999-8888' -> '5511999998888'.

    Aceita números brasileiros com ou sem DDI 55. Lança ValueError se não parecer um telefone.
    """
    digits = re.sub(r"\D", "", raw)
    # Suporte nativo para identificadores WhatsApp (LID - Linked Identity de 14 a 16 dígitos)
    if len(digits) in (14, 15, 16):
        return digits
    explicit_intl = raw.strip().startswith("+")  # com "+", o DDI foi dito de propósito: não adivinhar
    if len(digits) in (10, 11) and not explicit_intl:
        digits = "55" + digits
    if not (len(digits) in (12, 13) and digits.startswith("55")):
        raise ValueError("Telefone inválido. Use DDD + número, ex.: (11) 99999-8888")
    return digits


def get_or_create_by_phone(db: Session, phone: str, name: str) -> tuple[Client, bool]:
    """Usado pelo agendamento e pelo WhatsApp. Retorna (cliente, criado_agora)."""
    phone = normalize_phone(phone)
    client = db.scalar(select(Client).where(Client.phone == phone))
    if client:
        return client, False
    try:
        with db.begin_nested():  # savepoint: se outra requisição criou antes, só este bloco é desfeito
            client = Client(name=name, phone=phone)
            db.add(client)
            db.flush()
        return client, True
    except IntegrityError:
        return db.scalar(select(Client).where(Client.phone == phone)), False
