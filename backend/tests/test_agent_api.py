"""Testes para a API de integração do WhatsApp AI Agent."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.config import settings
from app.models import BusinessHours, Client, Service
from app.services.availability import TZ

AGENT_KEY = "chave-super-secreta-do-agente-123"
URL_BASE = "/api/v1/agent"


@pytest.fixture(autouse=True)
def setup_agent_key(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_agent_api_key", AGENT_KEY)


@pytest.fixture
def agent_headers():
    return {"X-Agent-API-Key": AGENT_KEY}


@pytest.fixture
def agent_bearer_headers():
    return {"Authorization": f"Bearer {AGENT_KEY}"}


@pytest.fixture
def setup_hours(db):
    """Garante horário comercial (segunda a domingo, 08:00 às 18:00)."""
    db.query(BusinessHours).delete()
    for d in range(7):
        db.add(BusinessHours(weekday=d, start_time=time(8, 0), end_time=time(18, 0)))
    db.flush()


@pytest.fixture
def sample_service(db):
    s = Service(name="Corte Tradicional", duration_minutes=30, price_cents=5000, is_active=True)
    db.add(s)
    db.flush()
    return s


# ----------------------------------------------------------------------
# 1. Autenticação e Segurança
# ----------------------------------------------------------------------
def test_agent_auth_required(client):
    r = client.get(f"{URL_BASE}/services")
    assert r.status_code == 401

    r = client.get(f"{URL_BASE}/services", headers={"X-Agent-API-Key": "chave-errada"})
    assert r.status_code == 401


def test_agent_auth_success_with_header_or_bearer(client, sample_service, agent_headers, agent_bearer_headers):
    r1 = client.get(f"{URL_BASE}/services", headers=agent_headers)
    assert r1.status_code == 200
    assert r1.json()["success"] is True

    r2 = client.get(f"{URL_BASE}/services", headers=agent_bearer_headers)
    assert r2.status_code == 200
    assert r2.json()["success"] is True


def test_agent_auth_503_if_key_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_agent_api_key", "")
    r = client.get(f"{URL_BASE}/services", headers={"X-Agent-API-Key": "qualquer"})
    assert r.status_code == 503


# ----------------------------------------------------------------------
# 2. Consultar Serviços e Preços
# ----------------------------------------------------------------------
def test_list_services(client, db, agent_headers, sample_service):
    # Inativo não deve aparecer
    inactive = Service(name="Inativo", duration_minutes=30, price_cents=2000, is_active=False)
    db.add(inactive)
    db.flush()

    r = client.get(f"{URL_BASE}/services", headers=agent_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    names = [s["name"] for s in body["data"]]
    assert "Corte Tradicional" in names
    assert "Inativo" not in names
    item = next(s for s in body["data"] if s["name"] == "Corte Tradicional")
    assert item["price_cents"] == 5000
    assert "50,00" in item["price_formatted"]


# ----------------------------------------------------------------------
# 3. Consultar Horários Disponíveis
# ----------------------------------------------------------------------
def test_get_availability(client, agent_headers, sample_service, setup_hours):
    tomorrow = (datetime.now(TZ) + timedelta(days=2)).date()
    r = client.get(
        f"{URL_BASE}/availability",
        params={"date": tomorrow.isoformat(), "service_id": sample_service.id},
        headers=agent_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["date"] == tomorrow.isoformat()
    assert len(body["data"]["available_slots"]) > 0
    assert len(body["data"]["available_slots_iso"]) > 0


def test_get_availability_service_not_found(client, agent_headers):
    tomorrow = (datetime.now(TZ) + timedelta(days=2)).date()
    r = client.get(
        f"{URL_BASE}/availability",
        params={"date": tomorrow.isoformat(), "service_id": 99999},
        headers=agent_headers,
    )
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SERVICO_INEXISTENTE"


# ----------------------------------------------------------------------
# 4. Localizar e Cadastrar Clientes
# ----------------------------------------------------------------------
def test_client_endpoints(client, agent_headers):
    phone = "11999998888"

    # 1. Busca inexistente -> 404
    r = client.get(f"{URL_BASE}/clients/by-phone", params={"phone": phone}, headers=agent_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CLIENTE_NAO_ENCONTRADO"

    # 2. Cadastro de cliente -> 201
    r_create = client.post(
        f"{URL_BASE}/clients",
        json={"name": "Lucas Silva", "phone": phone},
        headers=agent_headers,
    )
    assert r_create.status_code == 201
    data = r_create.json()["data"]
    assert data["name"] == "Lucas Silva"
    assert data["phone"] == "5511999998888"
    assert data["created"] is True

    # 3. Busca existente -> 200
    r_found = client.get(f"{URL_BASE}/clients/by-phone", params={"phone": phone}, headers=agent_headers)
    assert r_found.status_code == 200
    assert r_found.json()["data"]["name"] == "Lucas Silva"


# ----------------------------------------------------------------------
# 5. Criar Agendamento (com validação estrita e concorrência)
# ----------------------------------------------------------------------
def test_create_appointment_flow(client, agent_headers, sample_service, setup_hours):
    tomorrow = (datetime.now(TZ) + timedelta(days=2)).date()
    # Pega slot livre real da API
    r_avail = client.get(
        f"{URL_BASE}/availability",
        params={"date": tomorrow.isoformat(), "service_id": sample_service.id},
        headers=agent_headers,
    )
    slots = r_avail.json()["data"]["available_slots_iso"]
    assert len(slots) >= 2
    chosen_slot = slots[0]

    # 1. Criação com sucesso
    payload = {
        "client_phone": "11988887777",
        "client_name": "Rafael Santos",
        "service_id": sample_service.id,
        "starts_at": chosen_slot,
        "notes": "Agendado via WhatsApp Agent",
    }
    r = client.post(f"{URL_BASE}/appointments", json=payload, headers=agent_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["success"] is True
    appt_id = body["data"]["appointment_id"]
    assert body["data"]["client_phone"] == "5511988887777"
    assert body["data"]["status"] == "confirmed"

    # 2. Conflito: tentar reservar o mesmo horário -> 409
    payload_duplicate = {
        "client_phone": "11977776666",
        "client_name": "Outro Cliente",
        "service_id": sample_service.id,
        "starts_at": chosen_slot,
    }
    r_conflict = client.post(f"{URL_BASE}/appointments", json=payload_duplicate, headers=agent_headers)
    assert r_conflict.status_code == 409
    assert r_conflict.json()["error"]["code"] == "HORARIO_INDISPONIVEL"

    # 3. Rejeição no passado
    past_time = datetime.now(TZ) - timedelta(hours=2)
    payload_past = {
        "client_phone": "11988887777",
        "service_id": sample_service.id,
        "starts_at": past_time.isoformat(),
    }
    r_past = client.post(f"{URL_BASE}/appointments", json=payload_past, headers=agent_headers)
    assert r_past.status_code == 422
    assert r_past.json()["error"]["code"] == "DADOS_INVALIDOS"


# ----------------------------------------------------------------------
# 6. Consultar Agendamentos de um Cliente
# ----------------------------------------------------------------------
def test_list_client_appointments(client, agent_headers, sample_service, setup_hours):
    tomorrow = (datetime.now(TZ) + timedelta(days=2)).date()
    r_avail = client.get(
        f"{URL_BASE}/availability",
        params={"date": tomorrow.isoformat(), "service_id": sample_service.id},
        headers=agent_headers,
    )
    chosen_slot = r_avail.json()["data"]["available_slots_iso"][0]

    phone_a = "11911112222"
    phone_b = "11933334444"

    client.post(
        f"{URL_BASE}/appointments",
        json={"client_phone": phone_a, "client_name": "Cliente A", "service_id": sample_service.id, "starts_at": chosen_slot},
        headers=agent_headers,
    )

    # Consulta cliente A -> 1 agendamento
    r_a = client.get(f"{URL_BASE}/appointments", params={"phone": phone_a}, headers=agent_headers)
    assert r_a.status_code == 200
    assert len(r_a.json()["data"]) == 1
    assert r_a.json()["data"][0]["client_name"] == "Cliente A"

    # Consulta cliente B (sem agendamentos) -> lista vazia
    r_b = client.get(f"{URL_BASE}/appointments", params={"phone": phone_b}, headers=agent_headers)
    assert r_b.status_code == 200
    assert len(r_b.json()["data"]) == 0


# ----------------------------------------------------------------------
# 7. Remarcação e Cancelamento com Validação de Titularidade (Ownership)
# ----------------------------------------------------------------------
def test_reschedule_and_cancel_ownership_validation(client, agent_headers, sample_service, setup_hours):
    tomorrow = (datetime.now(TZ) + timedelta(days=2)).date()
    r_avail = client.get(
        f"{URL_BASE}/availability",
        params={"date": tomorrow.isoformat(), "service_id": sample_service.id},
        headers=agent_headers,
    )
    slots = r_avail.json()["data"]["available_slots_iso"]
    assert len(slots) >= 2
    slot1 = slots[0]
    slot2 = slots[1]

    phone_owner = "11955556666"
    phone_other = "11977778888"

    # Cria agendamento
    r_create = client.post(
        f"{URL_BASE}/appointments",
        json={"client_phone": phone_owner, "client_name": "Titular", "service_id": sample_service.id, "starts_at": slot1},
        headers=agent_headers,
    )
    assert r_create.status_code == 201
    appt_id = r_create.json()["data"]["appointment_id"]

    # Tentativa de remarcar por outra pessoa -> 403 NÃO AUTORIZADO
    r_hack_reschedule = client.patch(
        f"{URL_BASE}/appointments/{appt_id}",
        json={"phone": phone_other, "starts_at": slot2},
        headers=agent_headers,
    )
    assert r_hack_reschedule.status_code == 403
    assert r_hack_reschedule.json()["error"]["code"] == "NAO_AUTORIZADO"

    # Remarcação válida pelo titular -> 200
    r_reschedule_ok = client.patch(
        f"{URL_BASE}/appointments/{appt_id}",
        json={"phone": phone_owner, "starts_at": slot2},
        headers=agent_headers,
    )
    assert r_reschedule_ok.status_code == 200
    assert r_reschedule_ok.json()["success"] is True

    # Tentativa de cancelar por outra pessoa -> 403 NÃO AUTORIZADO
    r_hack_cancel = client.post(
        f"{URL_BASE}/appointments/{appt_id}/cancel",
        json={"phone": phone_other, "reason": "Trote"},
        headers=agent_headers,
    )
    assert r_hack_cancel.status_code == 403
    assert r_hack_cancel.json()["error"]["code"] == "NAO_AUTORIZADO"

    # Cancelamento válido pelo titular -> 200
    r_cancel_ok = client.post(
        f"{URL_BASE}/appointments/{appt_id}/cancel",
        json={"phone": phone_owner, "reason": "Imprevisto no trabalho"},
        headers=agent_headers,
    )
    assert r_cancel_ok.status_code == 200
    assert r_cancel_ok.json()["data"]["status"] == "cancelled"

    # Horário slot2 foi liberado! Outro cliente agora pode agendar nele
    r_reuse = client.post(
        f"{URL_BASE}/appointments",
        json={"client_phone": phone_other, "client_name": "Novo Cliente", "service_id": sample_service.id, "starts_at": slot2},
        headers=agent_headers,
    )
    assert r_reuse.status_code == 201
    assert r_reuse.json()["success"] is True
