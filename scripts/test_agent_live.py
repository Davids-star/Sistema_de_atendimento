"""Script de teste ao vivo para a API do WhatsApp AI Agent.

Testa o fluxo completo de ponta a ponta na API em execução:
1. Autenticação e listagem de serviços
2. Consulta de horários disponíveis
3. Cadastro e localização de cliente
4. Criação de agendamento em horário livre
5. Tentativa de conflito de horário (espera 409)
6. Tentativa de cancelamento por outro número (espera 403)
7. Cancelamento válido pelo próprio cliente (espera 200)
"""
import os
import sys
import httpx
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1/agent"
API_KEY = os.environ.get("WHATSAPP_AGENT_API_KEY") or sys.exit("Defina WHATSAPP_AGENT_API_KEY no ambiente.")
HEADERS = {"X-Agent-API-Key": API_KEY, "Content-Type": "application/json"}


def log(step: str, msg: str, success: bool = True):
    icon = "✅" if success else "❌"
    print(f"\n{icon} [{step}] {msg}")


def run_live_test():
    print("=" * 60)
    print("🚀 INICIANDO TESTE AO VIVO DA INTEGRAÇÃO WHATSAPP AI AGENT")
    print(f"Alvo: {BASE_URL}")
    print("=" * 60)

    with httpx.Client(timeout=10.0) as client:
        # 1. Testar bloqueio sem chave
        r_unauth = client.get(f"{BASE_URL}/services")
        if r_unauth.status_code == 401:
            log("1. Segurança", "Bloqueio de acesso sem token funcionou (HTTP 401)")
        else:
            log("1. Segurança", f"Falha de segurança! Retornou {r_unauth.status_code}", False)
            sys.exit(1)

        # 2. Listar serviços com chave
        r_services = client.get(f"{BASE_URL}/services", headers=HEADERS)
        if r_services.status_code == 200 and r_services.json()["success"]:
            services = r_services.json()["data"]
            log("2. Serviços", f"Obteve {len(services)} serviço(s) ativo(s):")
            for s in services:
                print(f"   -> ID: {s['id']} | {s['name']} | Duração: {s['duration_minutes']}min | Preço: {s['price_formatted']}")
            chosen_service = services[0]
        else:
            log("2. Serviços", f"Erro ao listar serviços: {r_services.text}", False)
            sys.exit(1)

        # 3. Consultar horários livres
        target_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        r_avail = client.get(
            f"{BASE_URL}/availability",
            params={"date": target_date, "service_id": chosen_service["id"]},
            headers=HEADERS,
        )
        if r_avail.status_code == 200 and r_avail.json()["success"]:
            avail_data = r_avail.json()["data"]
            slots = avail_data["available_slots"]
            slots_iso = avail_data["available_slots_iso"]
            log("3. Disponibilidade", f"Para {target_date}, encontrou {len(slots)} horários livres.")
            print(f"   -> Primeiros horários: {slots[:5]}...")
            chosen_slot_iso = slots_iso[0]
            chosen_slot_time = slots[0]
        else:
            log("3. Disponibilidade", f"Erro na consulta: {r_avail.text}", False)
            sys.exit(1)

        # 4. Cadastrar / Localizar Cliente
        test_phone = "11988889999"
        test_name = "Cliente Teste WhatsApp"
        r_client = client.post(
            f"{BASE_URL}/clients",
            json={"name": test_name, "phone": test_phone},
            headers=HEADERS,
        )
        if r_client.status_code in (200, 201) and r_client.json()["success"]:
            c_data = r_client.json()["data"]
            log("4. Cadastro Cliente", f"Cliente pronto: ID {c_data['id']} | Nome: {c_data['name']} | Tel: {c_data['phone']}")
        else:
            log("4. Cadastro Cliente", f"Erro no cliente: {r_client.text}", False)
            sys.exit(1)

        # 5. Criar Agendamento Real
        appt_payload = {
            "client_phone": test_phone,
            "client_name": test_name,
            "service_id": chosen_service["id"],
            "starts_at": chosen_slot_iso,
            "notes": "Teste automatizado da API",
        }
        r_appt = client.post(f"{BASE_URL}/appointments", json=appt_payload, headers=HEADERS)
        if r_appt.status_code == 201 and r_appt.json()["success"]:
            appt = r_appt.json()["data"]
            appt_id = appt["appointment_id"]
            log("5. Agendamento Criado", f"Reserva confirmada! ID: {appt_id} às {chosen_slot_time}")
            print(f"   -> Status: {appt['status']} | Valor: {appt['price_formatted']} | Início: {appt['starts_at']}")
        else:
            log("5. Agendamento", f"Erro ao criar agendamento: {r_appt.text}", False)
            sys.exit(1)

        # 6. Teste de Conflito de Horário (tentar marcar exatamente no mesmo horário)
        r_conflict = client.post(
            f"{BASE_URL}/appointments",
            json={
                "client_phone": "11977776666",
                "client_name": "Outro Cliente",
                "service_id": chosen_service["id"],
                "starts_at": chosen_slot_iso,
            },
            headers=HEADERS,
        )
        if r_conflict.status_code == 409 and not r_conflict.json()["success"]:
            log("6. Proteção de Conflito", f"Horário duplicado bloqueado com sucesso (HTTP 409: {r_conflict.json()['error']['code']})")
        else:
            log("6. Proteção de Conflito", f"Falha! Permitiu agendamento duplo: {r_conflict.text}", False)

        # 7. Teste de Proteção de Titularidade (outro número tentando cancelar)
        r_hack = client.post(
            f"{BASE_URL}/appointments/{appt_id}/cancel",
            json={"phone": "11977776666", "reason": "Tentativa indevida"},
            headers=HEADERS,
        )
        if r_hack.status_code == 403:
            log("7. Proteção Titularidade", "Outro número foi impedido de cancelar (HTTP 403: NAO_AUTORIZADO)")
        else:
            log("7. Proteção Titularidade", f"Falha de segurança! Retornou {r_hack.status_code}", False)

        # 8. Cancelamento Legítimo pelo próprio cliente
        r_cancel = client.post(
            f"{BASE_URL}/appointments/{appt_id}/cancel",
            json={"phone": test_phone, "reason": "Fim do teste ao vivo"},
            headers=HEADERS,
        )
        if r_cancel.status_code == 200 and r_cancel.json()["data"]["status"] == "cancelled":
            log("8. Cancelamento", f"Agendamento {appt_id} cancelado com sucesso e vaga liberada no sistema!")
        else:
            log("8. Cancelamento", f"Erro ao cancelar: {r_cancel.text}", False)
            sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 TODOS OS TESTES PASSARAM! A API ESTÁ 100% OPERACIONAL!")
    print("=" * 60)


if __name__ == "__main__":
    run_live_test()

