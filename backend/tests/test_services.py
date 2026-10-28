from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Appointment, AuditLog, Client

URL = "/api/v1/services"
CORTE = {"name": "Corte", "price_cents": 4000, "duration_minutes": 30}


def test_admin_routes_require_auth(client):
    assert client.post(URL, json=CORTE).status_code == 401
    assert client.patch(f"{URL}/1", json={"name": "x"}).status_code == 401
    assert client.delete(f"{URL}/1").status_code == 401
    assert client.get(URL, params={"include_inactive": True}).status_code == 401


def test_create_get_list(client, auth):
    r = client.post(URL, json=CORTE, headers=auth)
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.get(f"{URL}/{sid}").json()["name"] == "Corte"
    assert sid in [s["id"] for s in client.get(URL).json()]


def test_validation(client, auth):
    for bad in ({**CORTE, "price_cents": -1}, {**CORTE, "duration_minutes": 0}, {**CORTE, "name": ""}, {"name": "x"}):
        assert client.post(URL, json=bad, headers=auth).status_code == 422


def test_patch_partial_and_audit(client, auth, db):
    sid = client.post(URL, json=CORTE, headers=auth).json()["id"]
    r = client.patch(f"{URL}/{sid}", json={"price_cents": 4500}, headers=auth)
    assert r.status_code == 200
    assert r.json()["price_cents"] == 4500 and r.json()["name"] == "Corte"
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == sid))]
    assert actions == ["create", "update"]


def test_patch_null_rejected(client, auth):
    sid = client.post(URL, json=CORTE, headers=auth).json()["id"]
    assert client.patch(f"{URL}/{sid}", json={"name": None}, headers=auth).status_code == 422


def test_inactive_hidden_from_public(client, auth):
    sid = client.post(URL, json=CORTE, headers=auth).json()["id"]
    client.patch(f"{URL}/{sid}", json={"is_active": False}, headers=auth)
    assert client.get(f"{URL}/{sid}").status_code == 404
    assert sid not in [s["id"] for s in client.get(URL).json()]
    assert client.get(f"{URL}/{sid}", headers=auth).status_code == 200
    assert sid in [s["id"] for s in client.get(URL, params={"include_inactive": True}, headers=auth).json()]


def test_delete_unused_removes(client, auth):
    sid = client.post(URL, json=CORTE, headers=auth).json()["id"]
    assert client.delete(f"{URL}/{sid}", headers=auth).status_code == 204
    assert client.get(f"{URL}/{sid}", headers=auth).status_code == 404


def test_delete_used_deactivates(client, auth, db):
    sid = client.post(URL, json=CORTE, headers=auth).json()["id"]
    c = Client(name="A", phone="5511911111111")
    db.add(c)
    db.flush()
    start = datetime(2030, 1, 7, 12, tzinfo=timezone.utc)
    db.add(Appointment(client_id=c.id, service_id=sid, starts_at=start,
                       ends_at=start + timedelta(minutes=30), price_cents=4000))
    db.flush()
    assert client.delete(f"{URL}/{sid}", headers=auth).status_code == 204
    assert client.get(f"{URL}/{sid}", headers=auth).json()["is_active"] is False


def test_not_found(client):
    assert client.get(f"{URL}/999999").status_code == 404
