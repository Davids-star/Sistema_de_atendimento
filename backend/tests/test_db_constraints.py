"""Testa as restrições de integridade diretamente no PostgreSQL."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Appointment, Client, Service


def _base(db):
    client = Client(name="Teste", phone="5511900000000")
    service = Service(name="Corte", price_cents=5000, duration_minutes=30)
    db.add_all([client, service])
    db.flush()
    return client, service


def _appt(client, service, start, minutes=30, status="confirmed"):
    return Appointment(
        client_id=client.id, service_id=service.id, starts_at=start,
        ends_at=start + timedelta(minutes=minutes), status=status, price_cents=5000,
    )


T0 = datetime(2030, 1, 7, 12, 0, tzinfo=timezone.utc)


def test_overlap_is_rejected(db):
    c, s = _base(db)
    db.add(_appt(c, s, T0))
    db.flush()
    db.add(_appt(c, s, T0 + timedelta(minutes=15)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_back_to_back_is_allowed(db):
    c, s = _base(db)
    db.add(_appt(c, s, T0))
    db.add(_appt(c, s, T0 + timedelta(minutes=30)))
    db.flush()


def test_cancelled_does_not_block_slot(db):
    c, s = _base(db)
    db.add(_appt(c, s, T0, status="cancelled"))
    db.add(_appt(c, s, T0))
    db.flush()
