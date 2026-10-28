from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select, update

from app.models import Appointment, AuditLog, BusinessHours
from app.services import appointments as svc

TZ = ZoneInfo("America/Sao_Paulo")
URL = "/api/v1/appointments"


def at(h, m=0, day=7):  # segunda-feira, 2030-01-07
    return datetime(2030, 1, day, h, m, tzinfo=TZ)


@pytest.fixture
def setup(client, auth, db):
    db.execute(delete(BusinessHours))
    client.put("/api/v1/business-hours", headers=auth,
               json={"items": [{"weekday": 0, "start_time": "09:00", "end_time": "12:00"}]})
    sid = client.post("/api/v1/services", headers=auth,
                      json={"name": "Corte", "price_cents": 4000, "duration_minutes": 30}).json()["id"]
    cid = client.post("/api/v1/clients", headers=auth, json={"name": "Ana", "phone": "11999990000"}).json()["id"]
    return {"sid": sid, "cid": cid}


def book(client, auth, setup, start, **extra):
    body = {"client_id": setup["cid"], "service_id": setup["sid"], "starts_at": start.isoformat(), **extra}
    return client.post(URL, json=body, headers=auth)


def test_requires_auth(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401
    assert client.post(f"{URL}/1/confirm").status_code == 401


def test_create_ok(client, auth, setup):
    r = book(client, auth, setup, at(9))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "confirmed" and body["price_cents"] == 4000 and body["warnings"] == []
    assert datetime.fromisoformat(body["ends_at"]) == at(9, 30)
    assert client.get(f"{URL}/{body['id']}", headers=auth).json()["id"] == body["id"]


def test_overlap_409_but_touching_ok(client, auth, setup):
    assert book(client, auth, setup, at(9)).status_code == 201
    assert book(client, auth, setup, at(9, 15)).status_code == 409
    assert book(client, auth, setup, at(9, 30)).status_code == 201


def test_conflict_does_not_break_following_requests(client, auth, setup):
    book(client, auth, setup, at(9))
    assert book(client, auth, setup, at(9)).status_code == 409
    assert book(client, auth, setup, at(10)).status_code == 201  # transação continua utilizável


def test_cancelled_frees_slot(client, auth, setup):
    aid = book(client, auth, setup, at(9)).json()["id"]
    assert client.post(f"{URL}/{aid}/cancel", headers=auth).status_code == 200
    assert book(client, auth, setup, at(9)).status_code == 201


def test_admin_warnings_but_allowed(client, auth, setup):
    r = book(client, auth, setup, at(20))
    assert r.status_code == 201 and "Fora do horário de funcionamento" in r.json()["warnings"]
    client.post("/api/v1/blocked-times", headers=auth,
                json={"starts_at": at(10).isoformat(), "ends_at": at(11).isoformat()})
    assert "Coincide com um horário bloqueado" in book(client, auth, setup, at(10, 30)).json()["warnings"]


def test_past_is_rejected_for_admin(client, auth, setup):
    r = book(client, auth, setup, datetime(2020, 1, 6, 10, tzinfo=TZ))
    assert r.status_code == 422 and "passou" in r.json()["detail"]
    aid = book(client, auth, setup, at(9)).json()["id"]
    r = client.patch(f"{URL}/{aid}", headers=auth, json={"starts_at": datetime(2020, 1, 6, 10, tzinfo=TZ).isoformat()})
    assert r.status_code == 422


def make_started(db, aid, minutes_ago):
    """Simula um agendamento que já começou (a API não permite criar no passado)."""
    now = datetime.now(timezone.utc)
    db.execute(update(Appointment).where(Appointment.id == aid).values(
        starts_at=now - timedelta(minutes=minutes_ago), ends_at=now + timedelta(minutes=30 - minutes_ago)))
    db.expire_all()


def test_no_show_frees_the_slot_for_someone_else(client, auth, setup, db):
    aid = book(client, auth, setup, at(9)).json()["id"]
    make_started(db, aid, minutes_ago=10)  # marcado para 10 min atrás; cliente não apareceu
    now_plus = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    walk_in = {"client_id": setup["cid"], "service_id": setup["sid"], "starts_at": now_plus}
    assert client.post(URL, json=walk_in, headers=auth).status_code == 409   # ainda ocupa o horário
    assert client.post(f"{URL}/{aid}/no-show", headers=auth).json()["status"] == "no_show"
    assert client.post(URL, json=walk_in, headers=auth).status_code == 201   # liberado


def test_service_crossing_closing_time_warns(client, auth, setup):
    assert "Fora do horário de funcionamento" in book(client, auth, setup, at(11, 45)).json()["warnings"]


def test_strict_mode_rejects_unavailable(db, admin, setup, client):
    kw = dict(admin=None, client_id=setup["cid"], client_phone=None, client_name=None, service_id=setup["sid"],
              notes=None, status="pending", source="whatsapp", strict=True)
    with pytest.raises(svc.AppointmentError):
        svc.create_appointment(db, starts_at=at(20), **kw)  # fora do expediente
    with pytest.raises(svc.AppointmentError):
        svc.create_appointment(db, starts_at=datetime(2020, 1, 6, 10, tzinfo=TZ), **kw)  # passado
    with pytest.raises(svc.AppointmentError):
        svc.create_appointment(db, starts_at=at(9, 10), **kw)  # fora da grade
    appt, warnings = svc.create_appointment(db, starts_at=at(9), **kw)
    assert appt.status == "pending" and appt.source == "whatsapp" and warnings == []
    with pytest.raises(svc.AppointmentError):
        svc.create_appointment(db, starts_at=at(9), **kw)  # já ocupado


def test_client_by_phone_creates_or_reuses(client, auth, setup):
    new = client.post(URL, headers=auth, json={"client_phone": "(11) 98888-1111", "client_name": "Novo",
                                               "service_id": setup["sid"], "starts_at": at(9).isoformat()})
    assert new.status_code == 201
    again = client.post(URL, headers=auth, json={"client_phone": "5511988881111",
                                                 "service_id": setup["sid"], "starts_at": at(10).isoformat()})
    assert again.json()["client_id"] == new.json()["client_id"]
    no_name = client.post(URL, headers=auth, json={"client_phone": "11977772222",
                                                   "service_id": setup["sid"], "starts_at": at(11).isoformat()})
    assert no_name.status_code == 422


def test_validation(client, auth, setup):
    base = {"service_id": setup["sid"], "starts_at": at(9).isoformat()}
    assert client.post(URL, headers=auth, json=base).status_code == 422  # sem cliente
    both = {**base, "client_id": setup["cid"], "client_phone": "11999990000"}
    assert client.post(URL, headers=auth, json=both).status_code == 422
    naive = {**base, "client_id": setup["cid"], "starts_at": "2030-01-07T09:00:00"}
    assert client.post(URL, headers=auth, json=naive).status_code == 422
    assert client.post(URL, headers=auth, json={**base, "client_id": 999999}).status_code == 404
    assert client.post(URL, headers=auth, json={**base, "client_id": setup["cid"], "service_id": 999999}).status_code == 422
    bad_status = {**base, "client_id": setup["cid"], "status": "completed"}
    assert client.post(URL, headers=auth, json=bad_status).status_code == 422


def test_status_flow(client, auth, setup):
    aid = book(client, auth, setup, at(9), status="pending").json()["id"]
    assert client.post(f"{URL}/{aid}/confirm", headers=auth).json()["status"] == "confirmed"
    assert client.post(f"{URL}/{aid}/confirm", headers=auth).status_code == 409  # já confirmado
    assert client.post(f"{URL}/{aid}/complete", headers=auth).status_code == 409  # ainda é futuro
    assert client.post(f"{URL}/{aid}/cancel", headers=auth).json()["status"] == "cancelled"
    for action in ("confirm", "cancel", "complete", "no-show"):
        assert client.post(f"{URL}/{aid}/{action}", headers=auth).status_code == 409  # terminal
    assert client.post(f"{URL}/999999/cancel", headers=auth).status_code == 404


def test_complete_and_no_show_after_start(client, auth, setup, db):
    a1 = book(client, auth, setup, at(9)).json()["id"]
    a2 = book(client, auth, setup, at(10)).json()["id"]
    make_started(db, a1, 40)
    db.execute(update(Appointment).where(Appointment.id == a2).values(
        starts_at=datetime.now(timezone.utc) - timedelta(hours=3),
        ends_at=datetime.now(timezone.utc) - timedelta(hours=2, minutes=30)))
    db.expire_all()
    assert client.post(f"{URL}/{a1}/complete", headers=auth).json()["status"] == "completed"
    assert client.post(f"{URL}/{a2}/no-show", headers=auth).json()["status"] == "no_show"


def test_patch_reschedule_and_conflict(client, auth, setup):
    a = book(client, auth, setup, at(9)).json()["id"]
    book(client, auth, setup, at(10))
    r = client.patch(f"{URL}/{a}", headers=auth, json={"starts_at": at(11).isoformat(), "notes": "trazer foto"})
    assert r.status_code == 200 and r.json()["notes"] == "trazer foto"
    assert datetime.fromisoformat(r.json()["starts_at"]) == at(11)
    assert client.patch(f"{URL}/{a}", headers=auth, json={"starts_at": at(10).isoformat()}).status_code == 409
    assert client.get(f"{URL}/{a}", headers=auth).json()["starts_at"] == r.json()["starts_at"]  # não mudou


def test_patch_service_changes_price_and_end(client, auth, setup):
    long = client.post("/api/v1/services", headers=auth,
                       json={"name": "Corte+Barba", "price_cents": 7000, "duration_minutes": 60}).json()["id"]
    a = book(client, auth, setup, at(9)).json()["id"]
    r = client.patch(f"{URL}/{a}", headers=auth, json={"service_id": long}).json()
    assert r["price_cents"] == 7000 and datetime.fromisoformat(r["ends_at"]) == at(10)


def test_patch_rules(client, auth, setup):
    a = book(client, auth, setup, at(9)).json()["id"]
    assert client.patch(f"{URL}/{a}", headers=auth, json={}).status_code == 422
    assert client.patch(f"{URL}/{a}", headers=auth, json={"starts_at": None}).status_code == 422
    client.post(f"{URL}/{a}/cancel", headers=auth)
    assert client.patch(f"{URL}/{a}", headers=auth, json={"notes": "x"}).status_code == 409


def test_list_filters(client, auth, setup):
    a = book(client, auth, setup, at(9)).json()["id"]
    b = book(client, auth, setup, at(9, day=14)).json()["id"]
    client.post(f"{URL}/{b}/cancel", headers=auth)
    ids = lambda **p: [x["id"] for x in client.get(URL, params=p, headers=auth).json()]
    assert ids(date_from="2030-01-07", date_to="2030-01-07") == [a]
    assert ids(status="cancelled", date_from="2030-01-01", date_to="2030-02-01") == [b]
    assert set(ids(client_id=setup["cid"], date_from="2030-01-01", date_to="2030-02-01")) == {a, b}
    assert client.get(URL, params={"status": "lixo"}, headers=auth).status_code == 422


def test_client_appointments_endpoint(client, auth, setup):
    a = book(client, auth, setup, at(9)).json()["id"]
    got = client.get(f"/api/v1/clients/{setup['cid']}/appointments", headers=auth).json()
    assert [x["id"] for x in got] == [a]


def test_audit_trail(client, auth, setup, db):
    aid = book(client, auth, setup, at(9), status="pending").json()["id"]
    client.post(f"{URL}/{aid}/confirm", headers=auth)
    client.post(f"{URL}/{aid}/cancel", headers=auth)
    actions = [a.action for a in db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "appointment", AuditLog.entity_id == aid).order_by(AuditLog.id))]
    assert actions == ["create", "confirm", "cancel"]


def test_response_includes_names(client, auth, setup):
    body = book(client, auth, setup, at(9)).json()
    assert body["client_name"] == "Ana" and body["client_phone"] == "5511999990000"
    assert body["service_name"] == "Corte"
    listed = client.get(URL, params={"date_from": "2030-01-07", "date_to": "2030-01-07"}, headers=auth).json()
    assert listed[0]["client_name"] == "Ana" and listed[0]["service_name"] == "Corte"
