from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from app.models import Appointment, BlockedTime, BusinessHours, Client
from app.services.availability import compute_slots

TZ = ZoneInfo("America/Sao_Paulo")
FUTURE = date(2030, 1, 7)  # segunda-feira
LONG_AGO = datetime(2000, 1, 1, tzinfo=timezone.utc)


def at(h, m=0, day=FUTURE):
    return datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)


# ---------- função pura ----------
def test_slots_basic_grid():
    s = compute_slots(FUTURE, 30, [(time(9), time(11))], 30, [], TZ, LONG_AGO)
    assert s == [at(9), at(9, 30), at(10), at(10, 30)]


def test_service_must_end_before_closing():
    s = compute_slots(FUTURE, 45, [(time(9), time(10, 30))], 30, [], TZ, LONG_AGO)
    assert s == [at(9), at(9, 30)]  # 10:00 + 45min passaria de 10:30


def test_custom_interval_equals_duration():
    s = compute_slots(FUTURE, 45, [(time(9), time(11, 15))], 45, [], TZ, LONG_AGO)
    assert s == [at(9), at(9, 45), at(10, 30)]


def test_busy_blocks_overlapping_but_allows_touching():
    busy = [(at(10), at(10, 30))]
    s = compute_slots(FUTURE, 30, [(time(9), time(11))], 30, busy, TZ, LONG_AGO)
    assert s == [at(9), at(9, 30), at(10, 30)]


def test_long_service_blocked_by_later_appointment():
    busy = [(at(10), at(10, 30))]
    s = compute_slots(FUTURE, 60, [(time(9), time(12))], 30, busy, TZ, LONG_AGO)
    assert at(9, 30) not in s and at(9) in s and at(10, 30) in s  # 9:00-10:00 só encosta no bloqueio


def test_lunch_break_two_intervals():
    s = compute_slots(FUTURE, 60, [(time(14), time(16)), (time(9), time(11))], 60, [], TZ, LONG_AGO)
    assert s == [at(9), at(10), at(14), at(15)]


def test_past_slots_hidden():
    s = compute_slots(FUTURE, 30, [(time(9), time(11))], 30, [], TZ, at(9, 30))
    assert s == [at(10), at(10, 30)]


# ---------- API ----------
def _setup_hours(client, auth):
    items = [{"weekday": 0, "start_time": "09:00", "end_time": "12:00"}]
    r = client.put("/api/v1/business-hours", json={"items": items}, headers=auth)
    assert r.status_code == 200
    return r


def _service(client, auth, minutes=30):
    return client.post("/api/v1/services", json={"name": "S", "price_cents": 1000, "duration_minutes": minutes},
                       headers=auth).json()["id"]


def test_business_hours_requires_auth_to_change(client):
    assert client.put("/api/v1/business-hours", json={"items": []}).status_code == 401


def test_business_hours_replace_and_read(client, auth, db):
    db.execute(delete(BusinessHours))
    _setup_hours(client, auth)
    got = client.get("/api/v1/business-hours").json()
    assert got == [{"weekday": 0, "start_time": "09:00:00", "end_time": "12:00:00"}]
    client.put("/api/v1/business-hours", json={"items": []}, headers=auth)
    assert client.get("/api/v1/business-hours").json() == []


def test_business_hours_validation(client, auth):
    bad_order = {"items": [{"weekday": 0, "start_time": "12:00", "end_time": "09:00"}]}
    overlap = {"items": [{"weekday": 0, "start_time": "09:00", "end_time": "12:00"},
                         {"weekday": 0, "start_time": "11:00", "end_time": "13:00"}]}
    bad_day = {"items": [{"weekday": 7, "start_time": "09:00", "end_time": "12:00"}]}
    for body in (bad_order, overlap, bad_day):
        assert client.put("/api/v1/business-hours", json=body, headers=auth).status_code == 422


def test_settings_default_and_update(client, auth):
    assert client.get("/api/v1/settings", headers=auth).json() == {"slot_interval_minutes": 30}
    assert client.get("/api/v1/settings").status_code == 401
    assert client.put("/api/v1/settings", json={"slot_interval_minutes": 45}, headers=auth).status_code == 200
    assert client.put("/api/v1/settings", json={"slot_interval_minutes": 1}, headers=auth).status_code == 422


def test_availability_end_to_end(client, auth, db):
    _setup_hours(client, auth)
    sid = _service(client, auth)
    r = client.get("/api/v1/availability", params={"date": FUTURE.isoformat(), "service_id": sid})
    assert r.status_code == 200
    assert len(r.json()["slots"]) == 6  # 9:00-12:00 de 30 em 30

    # Admin muda o intervalo para 60 min
    client.put("/api/v1/settings", json={"slot_interval_minutes": 60}, headers=auth)
    r = client.get("/api/v1/availability", params={"date": FUTURE.isoformat(), "service_id": sid})
    assert len(r.json()["slots"]) == 3

    # Dia fechado (terça)
    r = client.get("/api/v1/availability", params={"date": "2030-01-08", "service_id": sid})
    assert r.json()["slots"] == []


def test_availability_respects_block_and_appointment(client, auth, db):
    _setup_hours(client, auth)
    sid = _service(client, auth)
    blk = client.post("/api/v1/blocked-times", headers=auth,
                      json={"starts_at": at(9).isoformat(), "ends_at": at(10).isoformat(), "reason": "médico"})
    assert blk.status_code == 201

    c = Client(name="X", phone="5511900001111")
    db.add(c)
    db.flush()
    db.add(Appointment(client_id=c.id, service_id=sid, starts_at=at(10), ends_at=at(10, 30),
                       status="confirmed", price_cents=1000))
    cancelled = Appointment(client_id=c.id, service_id=sid, starts_at=at(11), ends_at=at(11, 30),
                            status="cancelled", price_cents=1000)
    db.add(cancelled)
    db.flush()

    slots = client.get("/api/v1/availability", params={"date": FUTURE.isoformat(), "service_id": sid}).json()["slots"]
    got = [datetime.fromisoformat(s) for s in slots]
    assert got == [at(10, 30), at(11), at(11, 30)]  # cancelado libera 11:00

    # remover o bloqueio libera 9:00-10:00
    client.delete(f"/api/v1/blocked-times/{blk.json()['id']}", headers=auth)
    slots = client.get("/api/v1/availability", params={"date": FUTURE.isoformat(), "service_id": sid}).json()["slots"]
    assert len(slots) == 5


def test_availability_unknown_or_inactive_service(client, auth):
    assert client.get("/api/v1/availability", params={"date": "2030-01-07", "service_id": 999999}).status_code == 404
    sid = _service(client, auth)
    client.patch(f"/api/v1/services/{sid}", json={"is_active": False}, headers=auth)
    assert client.get("/api/v1/availability", params={"date": "2030-01-07", "service_id": sid}).status_code == 404


def test_availability_bad_params(client):
    assert client.get("/api/v1/availability", params={"date": "nao-e-data", "service_id": 1}).status_code == 422
    assert client.get("/api/v1/availability", params={"date": "2030-01-07"}).status_code == 422


def test_blocked_times_validation_and_auth(client, auth):
    assert client.get("/api/v1/blocked-times").status_code == 401
    assert client.post("/api/v1/blocked-times", json={}).status_code == 401
    naive = {"starts_at": "2030-01-07T09:00:00", "ends_at": "2030-01-07T10:00:00"}
    assert client.post("/api/v1/blocked-times", json=naive, headers=auth).status_code == 422  # sem fuso
    inverted = {"starts_at": at(10).isoformat(), "ends_at": at(9).isoformat()}
    assert client.post("/api/v1/blocked-times", json=inverted, headers=auth).status_code == 422
    assert client.delete("/api/v1/blocked-times/999999", headers=auth).status_code == 404
