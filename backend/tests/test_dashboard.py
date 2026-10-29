from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models import Appointment, Client, Service

TZ = ZoneInfo("America/Sao_Paulo")
URL = "/api/v1/dashboard"
P = {"date_from": "2029-03-01", "date_to": "2029-03-31"}


def at(day, h, m=0):
    return datetime(2029, 3, day, h, m, tzinfo=TZ)


@pytest.fixture
def data(db):
    """Março/2029: valores conhecidos para conferir as contas."""
    corte = Service(name="Corte", price_cents=4000, duration_minutes=30)
    barba = Service(name="Barba", price_cents=3000, duration_minutes=30)
    a, b = Client(name="A", phone="5511900000001"), Client(name="B", phone="5511900000002")
    db.add_all([corte, barba, a, b])
    db.flush()

    def add(client, service, start, status, price=None):
        db.add(Appointment(client_id=client.id, service_id=service.id, starts_at=start,
                           ends_at=start + timedelta(minutes=30), status=status,
                           price_cents=price if price is not None else service.price_cents))

    add(a, corte, at(5, 9), "completed")                 # 4000
    add(a, barba, at(5, 10), "completed")                # 3000
    add(b, corte, at(6, 9), "completed", price=4500)     # 4500 (preço histórico diferente)
    add(b, corte, at(6, 10), "no_show")
    add(a, corte, at(7, 23, 30), "completed")            # 23:30 local = 02:30 UTC do dia 8; 4000
    add(b, barba, at(20, 9), "confirmed")                # 3000 previsto
    add(b, barba, at(21, 9), "pending")                  # 3000 previsto
    add(a, corte, at(22, 9), "cancelled")
    add(a, corte, datetime(2029, 4, 2, 9, tzinfo=TZ), "completed")  # fora do período
    db.flush()


def test_requires_auth(client):
    for path in ("summary", "appointments-by-day", "revenue"):
        assert client.get(f"{URL}/{path}").status_code == 401


def test_summary(client, auth, data):
    r = client.get(f"{URL}/summary", params=P, headers=auth)
    assert r.status_code == 200
    s = r.json()
    assert s["total_appointments"] == 8
    assert s["by_status"] == {"pending": 1, "confirmed": 1, "cancelled": 1, "completed": 4, "no_show": 1}
    assert s["revenue_cents"] == 4000 + 3000 + 4500 + 4000  # só concluídos, com o preço gravado
    assert s["expected_revenue_cents"] == 6000
    assert s["no_show_rate"] == 0.2  # 1 / (4 concluídos + 1 ausência)
    assert s["unique_clients"] == 2
    assert [t["name"] for t in s["top_services"]] == ["Corte", "Barba"]
    assert s["top_services"][0] == {"service_id": s["top_services"][0]["service_id"], "name": "Corte",
                                    "count": 3, "revenue_cents": 12500}


def test_summary_empty_period(client, auth):
    s = client.get(f"{URL}/summary", params={"date_from": "2020-01-01", "date_to": "2020-01-31"}, headers=auth).json()
    assert s["total_appointments"] == 0 and s["revenue_cents"] == 0 and s["no_show_rate"] is None
    assert s["top_services"] == []


def test_default_period_is_current_month(client, auth):
    s = client.get(f"{URL}/summary", headers=auth).json()
    today = datetime.now(TZ).date()
    assert s["date_from"] == today.replace(day=1).isoformat()
    assert s["date_to"] >= today.isoformat() and s["date_to"][:7] == s["date_from"][:7]


def test_by_day_fills_gaps_and_uses_local_timezone(client, auth, data):
    days = client.get(f"{URL}/appointments-by-day", params=P, headers=auth).json()
    assert len(days) == 31
    by = {d["date"]: d for d in days}
    assert by["2029-03-05"]["total"] == 2 and by["2029-03-05"]["by_status"]["completed"] == 2
    assert by["2029-03-06"]["by_status"]["no_show"] == 1
    assert by["2029-03-07"]["total"] == 1 and by["2029-03-08"]["total"] == 0  # 23:30 local fica no dia 7
    assert by["2029-03-01"]["total"] == 0
    assert sum(d["total"] for d in days) == 8


def test_revenue_by_day_and_month(client, auth, data):
    r = client.get(f"{URL}/revenue", params=P, headers=auth).json()
    assert r["total_cents"] == 15500 and r["group_by"] == "day"
    assert r["points"] == [
        {"period": "2029-03-05", "revenue_cents": 7000, "completed_count": 2},
        {"period": "2029-03-06", "revenue_cents": 4500, "completed_count": 1},
        {"period": "2029-03-07", "revenue_cents": 4000, "completed_count": 1},
    ]
    m = client.get(f"{URL}/revenue", params={"date_from": "2029-03-01", "date_to": "2029-04-30", "group_by": "month"},
                   headers=auth).json()
    assert m["points"] == [{"period": "2029-03", "revenue_cents": 15500, "completed_count": 4},
                           {"period": "2029-04", "revenue_cents": 4000, "completed_count": 1}]


def test_period_validation(client, auth):
    bad = [{"date_from": "2029-03-10", "date_to": "2029-03-01"},
           {"date_from": "2020-01-01", "date_to": "2022-01-01"},
           {"date_from": "nao-e-data"}]
    for params in bad:
        assert client.get(f"{URL}/summary", params=params, headers=auth).status_code == 422
    assert client.get(f"{URL}/revenue", params={"group_by": "ano"}, headers=auth).status_code == 422


def test_attended_clients_counts_only_those_with_a_completed_service(client, auth, db):
    """Quem só cancelou, faltou ou ainda está pendente/confirmado não foi atendido."""
    svc = Service(name="Corte", price_cents=4000, duration_minutes=30)
    people = {k: Client(name=k, phone=f"55119000000{i}") for i, k in enumerate(["atendida", "cancelou", "faltou", "pendente", "confirmada", "mista"])}
    db.add(svc)
    db.add_all(people.values())
    db.flush()
    plan = [("atendida", "completed", 9), ("cancelou", "cancelled", 10), ("faltou", "no_show", 11), ("pendente", "pending", 12),
            ("confirmada", "confirmed", 13), ("mista", "cancelled", 14), ("mista", "completed", 15), ("atendida", "completed", 16)]
    for who, status, hour in plan:
        start = at(12, hour - 9)
        db.add(Appointment(client_id=people[who].id, service_id=svc.id, starts_at=start, ends_at=start + timedelta(minutes=30),
                           status=status, price_cents=4000))
    db.flush()
    s = client.get(f"{URL}/summary", params={"date_from": "2029-03-12", "date_to": "2029-03-12"}, headers=auth).json()
    assert s["unique_clients"] == 2                                          # só "atendida" e "mista" (que teve um concluído)
    assert s["total_appointments"] == 8 and s["scheduled_appointments"] == 6   # cancelados fora do "agendados"


def test_attended_clients_is_zero_when_nobody_was_attended(client, auth, db):
    svc = Service(name="Corte", price_cents=4000, duration_minutes=30)
    cli = Client(name="So cancelou", phone="5511900000099")
    db.add_all([svc, cli])
    db.flush()
    db.add(Appointment(client_id=cli.id, service_id=svc.id, starts_at=at(12, 0), ends_at=at(12, 0) + timedelta(minutes=30),
                       status="cancelled", price_cents=4000))
    db.flush()
    s = client.get(f"{URL}/summary", params={"date_from": "2029-03-12", "date_to": "2029-03-12"}, headers=auth).json()
    assert s["unique_clients"] == 0 and s["scheduled_appointments"] == 0
