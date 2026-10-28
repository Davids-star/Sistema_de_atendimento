"""Teste de concorrência de verdade: várias conexões simultâneas, com commit real no PostgreSQL.

Usa dados próprios e os apaga no final (não usa a transação revertida dos outros testes).
"""
import threading
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import AdminUser, Appointment, AuditLog, Client, Service

EMAIL, PASSWORD = "concorrencia@teste.com", "senha-de-teste-123"
START = datetime(2031, 3, 3, 15, 0, tzinfo=timezone.utc)


def _cleanup():
    with SessionLocal() as s:
        svc_ids = s.scalars(select(Service.id).where(Service.name == "TESTE-CONCORRENCIA")).all()
        s.execute(delete(Appointment).where(Appointment.service_id.in_(svc_ids)))
        s.execute(delete(Client).where(Client.phone.like("5511900099%")))
        s.execute(delete(Service).where(Service.id.in_(svc_ids)))
        admin_ids = s.scalars(select(AdminUser.id).where(AdminUser.email == EMAIL)).all()
        s.execute(delete(AuditLog).where(AuditLog.admin_user_id.in_(admin_ids)))
        s.execute(delete(AdminUser).where(AdminUser.id.in_(admin_ids)))
        s.commit()


def test_simultaneous_bookings_same_slot_only_one_wins():
    _cleanup()
    try:
        with SessionLocal() as s:
            s.add(AdminUser(email=EMAIL, name="T", password_hash=hash_password(PASSWORD)))
            s.add(Service(name="TESTE-CONCORRENCIA", price_cents=1000, duration_minutes=30))
            s.commit()
            sid = s.scalar(select(Service.id).where(Service.name == "TESTE-CONCORRENCIA"))

        with TestClient(app) as c:
            token = c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        n = 10
        barrier = threading.Barrier(n)
        results = []

        def worker(i):
            with TestClient(app) as c:
                barrier.wait()  # todas disparam ao mesmo tempo
                r = c.post("/api/v1/appointments", headers=headers, json={
                    "client_phone": f"1190009900{i}", "client_name": f"C{i}",
                    "service_id": sid, "starts_at": START.isoformat()})
                results.append(r.status_code)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        assert sorted(results) == [201] + [409] * (n - 1), results
        with SessionLocal() as s:
            assert len(s.scalars(select(Appointment).where(Appointment.service_id == sid)).all()) == 1
    finally:
        _cleanup()
