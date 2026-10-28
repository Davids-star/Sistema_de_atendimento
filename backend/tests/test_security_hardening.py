from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core import rate_limit
from app.core.config import settings
from app.models import Appointment

from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD

LOGIN = "/api/v1/auth/login"


def login(client, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


# ---------- limite de tentativas de login ----------
def test_login_locks_after_repeated_failures(client, admin):
    for _ in range(settings.login_max_failures):
        assert login(client, password="errada").status_code == 401
    blocked = login(client, password="errada")
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0


def test_lock_applies_even_with_correct_password(client, admin):
    for _ in range(settings.login_max_failures):
        login(client, password="errada")
    assert login(client).status_code == 429


def test_success_resets_email_counter(client, admin):
    for _ in range(settings.login_max_failures - 1):
        login(client, password="errada")
    assert login(client).status_code == 200
    for _ in range(settings.login_max_failures - 1):  # contador recomeçou do zero
        assert login(client, password="errada").status_code == 401


def test_lock_is_per_email_not_global(client, admin):
    for _ in range(settings.login_max_failures):
        login(client, email="outro@x.com", password="errada")
    assert login(client, email="outro@x.com").status_code == 429
    assert login(client).status_code == 200  # o dono ainda consegue entrar


def test_ip_limit_blocks_spraying_many_emails(client, admin):
    limit = settings.login_max_failures * 4
    for i in range(limit):
        assert login(client, email=f"alvo{i}@x.com", password="x").status_code == 401
    assert login(client, email="novo@x.com", password="x").status_code == 429


def test_lock_expires(client, admin, monkeypatch):
    for _ in range(settings.login_max_failures):
        login(client, password="errada")
    assert login(client).status_code == 429
    real = rate_limit.time.monotonic
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: real() + settings.login_lockout_minutes * 60 + 1)
    assert login(client).status_code == 200


# ---------- limite geral ----------
def test_general_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 5)
    codes = [client.get("/api/v1/services").status_code for _ in range(7)]
    assert codes == [200] * 5 + [429] * 2
    r = client.get("/api/v1/services")
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_health_is_exempt(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    assert all(client.get("/health").status_code == 200 for _ in range(10))


def test_rate_limit_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    assert all(client.get("/api/v1/services").status_code == 200 for _ in range(10))


# ---------- CORS ----------
def test_cors_allows_configured_origin(client):
    r = client.options("/api/v1/services", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_other_origin(client):
    r = client.get("/api/v1/services", headers={"Origin": "http://site-malicioso.com"})
    assert "access-control-allow-origin" not in r.headers


def test_429_carries_cors_header(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
    client.get("/api/v1/services")
    r = client.get("/api/v1/services", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 429 and r.headers["access-control-allow-origin"] == "http://localhost:5173"


# ---------- agendamentos sem desfecho ----------
def test_needs_outcome_filter(client, auth, db):
    sid = client.post("/api/v1/services", headers=auth,
                      json={"name": "S", "price_cents": 1000, "duration_minutes": 30}).json()["id"]
    cid = client.post("/api/v1/clients", headers=auth, json={"name": "A", "phone": "11999990000"}).json()["id"]
    now = datetime.now(timezone.utc)

    def book(offset_h):
        r = client.post("/api/v1/appointments", headers=auth, json={
            "client_id": cid, "service_id": sid, "starts_at": (now + timedelta(days=30, hours=offset_h)).isoformat()})
        return r.json()["id"]

    old, future, done = book(0), book(2), book(4)
    for aid, hours_ago in ((old, 5), (done, 8)):  # simula horários que já terminaram
        db.execute(update(Appointment).where(Appointment.id == aid).values(
            starts_at=now - timedelta(hours=hours_ago), ends_at=now - timedelta(hours=hours_ago) + timedelta(minutes=30)))
    db.expire_all()
    client.post(f"/api/v1/appointments/{done}/complete", headers=auth)

    ids = [a["id"] for a in client.get("/api/v1/appointments", params={"needs_outcome": True}, headers=auth).json()]
    assert ids == [old]  # o futuro e o já concluído ficam de fora
