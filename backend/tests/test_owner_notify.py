import logging
from contextlib import nullcontext
from datetime import datetime, timezone

import pytest
import requests
from sqlalchemy import select

from app.core.config import settings
from app.models import AdminUser, AuditLog
from app.services import geoip, mailer, owner_notify, telegram

CHAT = "424242"


def make_user(db, email="nova@gmail.com", *, verified=True, approved=False, phone="5511988887777", google=False, ip="187.1.2.3"):
    now = datetime.now(timezone.utc)
    user = AdminUser(email=email, name="Maria Souza", phone=phone, password_hash=None, signup_ip=ip,
                     google_sub="g-1" if google else None, email_verified_at=now if verified else None,
                     approved_at=now if approved else None)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def tg(monkeypatch):
    """Telegram ligado, com as chamadas à API registradas em vez de enviadas."""
    monkeypatch.setattr(settings, "telegram_bot_token", "123:SECRET-TOKEN")
    monkeypatch.setattr(settings, "telegram_chat_id", CHAT)
    calls = []
    monkeypatch.setattr(telegram, "call", lambda method, payload, timeout=15: calls.append((method, payload)) or {"ok": True, "result": {}})
    return calls


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


@pytest.fixture
def use_test_db(monkeypatch, db):
    monkeypatch.setattr(owner_notify, "SessionLocal", lambda: nullcontext(db))


def sent_texts(calls, method="sendMessage"):
    return [p for m, p in calls if m == method]


# ---------- localização ----------
class FakeResp:
    def __init__(self, data, ok=True): self._d, self.ok = data, ok
    def json(self): return self._d


def test_geoip_private_and_invalid_ips_never_call_the_network(monkeypatch):
    monkeypatch.setattr(geoip.requests, "get", lambda *a, **k: pytest.fail("não deveria consultar a rede"))
    assert "rede local" in geoip.describe_location("127.0.0.1")
    assert "rede local" in geoip.describe_location("192.168.0.10")
    assert geoip.describe_location("testclient") == geoip.UNKNOWN
    assert geoip.describe_location(None) == geoip.UNKNOWN


def test_geoip_formats_the_answer(monkeypatch):
    seen = {}
    monkeypatch.setattr(geoip.requests, "get", lambda url, **k: seen.update(url=url) or FakeResp(
        {"city": "São Paulo", "region": "São Paulo", "country_name": "Brazil"}))
    out = geoip.describe_location("187.1.2.3")
    assert out == "São Paulo, São Paulo, Brazil (aproximado, pelo IP)"
    assert seen["url"] == "https://ipapi.co/187.1.2.3/json/" and seen["url"].startswith("https://")


@pytest.mark.parametrize("answer", [FakeResp({"error": True, "reason": "RateLimited"}), FakeResp({}, ok=False), FakeResp([1, 2]), FakeResp({"city": None})])
def test_geoip_bad_answers_degrade_gracefully(monkeypatch, answer):
    monkeypatch.setattr(geoip.requests, "get", lambda *a, **k: answer)
    assert geoip.describe_location("187.1.2.3") == geoip.UNKNOWN


def test_geoip_network_failure_does_not_leak_the_ip_in_logs(monkeypatch, caplog):
    def boom(*a, **k): raise requests.ConnectionError("falha em https://ipapi.co/187.1.2.3/json/")
    monkeypatch.setattr(geoip.requests, "get", boom)
    with caplog.at_level(logging.DEBUG):
        assert geoip.describe_location("187.1.2.3") == geoip.UNKNOWN
    assert "187.1.2.3" not in caplog.text


def test_geoip_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(settings, "geoip_url", "")
    monkeypatch.setattr(geoip.requests, "get", lambda *a, **k: pytest.fail("desligado"))
    assert geoip.describe_location("187.1.2.3") == geoip.UNKNOWN


# ---------- mensagem e envio ----------
def test_message_has_name_phone_location_and_ip_but_no_secrets(db):
    user = make_user(db)
    text = owner_notify.build_message(user, "São Paulo, SP (aproximado, pelo IP)", "e-mail e senha")
    for expected in ("Maria Souza", "(11) 98888-7777", "São Paulo, SP", "187.1.2.3", "nova@gmail.com", "Se não reconhece"):
        assert expected in text
    assert "senha:" not in text.lower() and "token" not in text.lower()


def test_message_without_phone_says_so(db):
    assert "ainda não informado" in owner_notify.build_message(make_user(db, phone=None), "x", "Google")


def test_notifies_owner_by_email_and_telegram_once(db, admin, tg, mails, use_test_db, monkeypatch):
    monkeypatch.setattr(geoip, "describe_location", lambda ip: "Curitiba, Paraná, Brazil (aproximado, pelo IP)")
    user = make_user(db)
    owner_notify.notify_owner_new_user(user.id)

    assert any(to == admin.email for to, _, _ in mails)
    assert all("Curitiba" in body and "Maria Souza" in body and "/usuarios" in body for _, _, body in mails)
    msgs = sent_texts(tg)
    assert len(msgs) == 1 and msgs[0]["chat_id"] == CHAT
    assert "Curitiba" in msgs[0]["text"] and "(11) 98888-7777" in msgs[0]["text"]
    buttons = msgs[0]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == [f"approve:{user.id}", f"reject:{user.id}"]
    assert "parse_mode" not in msgs[0]                       # texto puro: nome malicioso não injeta formatação

    n_mails, n_tg = len(mails), len(tg)
    owner_notify.notify_owner_new_user(user.id)              # segunda vez: não repete
    assert (len(mails), len(tg)) == (n_mails, n_tg)
    db.refresh(user)
    assert user.owner_notified_at is not None


def test_works_with_email_only_when_telegram_is_not_configured(db, admin, mails, use_test_db, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(telegram, "call", lambda *a, **k: pytest.fail("Telegram desligado"))
    monkeypatch.setattr(geoip, "describe_location", lambda ip: "x")
    user = make_user(db)
    owner_notify.notify_owner_new_user(user.id)
    assert any(to == admin.email for to, _, _ in mails)


def test_does_not_notify_for_approved_missing_or_unknown_users(db, admin, tg, mails, use_test_db):
    owner_notify.notify_owner_new_user(make_user(db, "a@gmail.com", approved=True).id)
    owner_notify.notify_owner_new_user(99999999)
    assert mails == [] and tg == []


def test_a_failure_never_raises_and_can_be_retried(db, admin, mails, use_test_db, monkeypatch, caplog):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(geoip, "describe_location", lambda ip: (_ for _ in ()).throw(RuntimeError("boom")))
    user = make_user(db)
    with caplog.at_level(logging.ERROR):
        owner_notify.notify_owner_new_user(user.id)          # não levanta erro: o cadastro não pode quebrar
    assert "falha ao avisar o dono" in caplog.text
    db.refresh(user)
    assert user.owner_notified_at is None                    # não marcou como avisado: tenta de novo depois


# ---------- gatilhos nas rotas ----------
@pytest.fixture
def notified(monkeypatch):
    ids = []
    monkeypatch.setattr(owner_notify, "notify_owner_new_user", lambda user_id: ids.append(user_id))
    return ids


def test_signup_stores_the_ip_and_confirming_the_email_triggers_the_notice(client, db, mails, notified):
    body = {"name": "Maria", "phone": "(11) 98888-7777", "email": "maria@gmail.com",
            "password": "uma-senha-forte-123", "password_confirm": "uma-senha-forte-123"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 202
    user = db.scalar(select(AdminUser).where(AdminUser.email == "maria@gmail.com"))
    assert user.signup_ip == "testclient" and notified == []          # ainda não confirmou: nada de avisar o dono
    import re
    token = re.search(r"token=(\S+)", mails[-1][2]).group(1)
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 204
    assert notified == [user.id]                                      # e-mail confirmado: agora avisa


def test_google_signup_triggers_the_notice(client, db, notified, monkeypatch):
    from app.api.v1 import auth as auth_module
    monkeypatch.setattr(settings, "google_client_id", "x.apps.googleusercontent.com")
    monkeypatch.setattr(auth_module, "verify_google_token", lambda c: {"sub": "9", "email": "novo@gmail.com", "email_verified": True, "name": "Novo"})
    assert client.post("/api/v1/auth/google", json={"credential": "x"}).status_code == 200
    user = db.scalar(select(AdminUser).where(AdminUser.email == "novo@gmail.com"))
    assert notified == [user.id] and user.signup_ip == "testclient"


def test_an_approved_owner_logging_in_with_google_is_not_reported(client, admin, db, notified, monkeypatch):
    from app.api.v1 import auth as auth_module
    monkeypatch.setattr(settings, "google_client_id", "x.apps.googleusercontent.com")
    monkeypatch.setattr(auth_module, "verify_google_token", lambda c: {"sub": "1", "email": admin.email, "email_verified": True})
    client.post("/api/v1/auth/google", json={"credential": "x"})
    assert notified == []


# ---------- Telegram: cliques ----------
def click(action, user_id, *, chat=CHAT, sender=CHAT, cid="cb-1"):
    return {"callback_query": {"id": cid, "from": {"id": int(sender)}, "data": f"{action}:{user_id}",
                               "message": {"message_id": 7, "chat": {"id": int(chat)}, "text": "Novo cadastro"}}}


def answers(calls):
    return [p["text"] for m, p in calls if m == "answerCallbackQuery"]


def test_owner_approves_from_telegram(db, admin, tg):
    user = make_user(db)
    telegram.handle_update(db, click("approve", user.id))
    db.refresh(user)
    assert user.approved
    edit = sent_texts(tg, "editMessageText")[0]
    assert "Acesso liberado para Maria Souza" in edit["text"] and "reply_markup" not in edit      # botões saem
    audit = db.scalars(select(AuditLog).where(AuditLog.entity_id == user.id, AuditLog.action == "user_approve")).all()
    assert audit and audit[-1].changes == {"via": "telegram"}


def test_owner_rejects_from_telegram_and_the_account_is_disabled(db, admin, tg):
    user = make_user(db)
    telegram.handle_update(db, click("reject", user.id))
    db.refresh(user)
    assert not user.is_active and not user.approved
    assert "recusado" in sent_texts(tg, "editMessageText")[0]["text"]


@pytest.mark.parametrize("chat,sender", [("999", "999"), (CHAT, "999"), ("999", CHAT)])
def test_clicks_from_other_chats_or_senders_change_nothing(db, admin, tg, chat, sender):
    user = make_user(db)
    telegram.handle_update(db, click("approve", user.id, chat=chat, sender=sender))
    db.refresh(user)
    assert not user.approved and user.is_active
    assert answers(tg) == ["Você não tem permissão para isso."] and sent_texts(tg, "editMessageText") == []


def test_clicks_are_refused_when_telegram_is_not_configured(db, admin, monkeypatch):
    """Sem configuração, o chat autorizado é "" e um clique sem identificação também chega "": não podem "bater"."""
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_chat_id", "")
    calls = []
    monkeypatch.setattr(telegram, "call", lambda m, p, timeout=15: calls.append((m, p)))
    user = make_user(db)
    update = {"callback_query": {"id": "x", "data": f"approve:{user.id}", "message": {"chat": {}}}}   # sem chat nem remetente
    telegram.handle_update(db, update)
    db.refresh(user)
    assert not user.approved


def test_clicks_with_a_missing_sender_are_refused_even_when_configured(db, admin, tg):
    user = make_user(db)
    update = click("approve", user.id)
    del update["callback_query"]["from"]
    telegram.handle_update(db, update)
    db.refresh(user)
    assert not user.approved


def test_double_click_is_harmless(db, admin, tg):
    user = make_user(db)
    telegram.handle_update(db, click("approve", user.id))
    telegram.handle_update(db, click("approve", user.id, cid="cb-2"))
    assert "já tinha acesso" in sent_texts(tg, "editMessageText")[-1]["text"]


def test_cannot_approve_an_unconfirmed_email_via_telegram(db, admin, tg):
    user = make_user(db, verified=False)
    telegram.handle_update(db, click("approve", user.id))
    db.refresh(user)
    assert not user.approved and "ainda não foi confirmado" in answers(tg)[0]


def test_cannot_reject_an_owner_via_telegram(db, admin, tg):
    telegram.handle_update(db, click("reject", admin.id))
    db.refresh(admin)
    assert admin.is_active and "dono" in answers(tg)[0].lower()


@pytest.mark.parametrize("data", ["approve:abc", "approve:99999999", "hack:1", "approve", ""])
def test_malformed_or_unknown_callbacks_are_rejected(db, admin, tg, data):
    update = click("approve", 1)
    update["callback_query"]["data"] = data
    telegram.handle_update(db, update)
    assert answers(tg) == ["Pedido inválido ou usuário não encontrado."]


def test_start_command_helps_to_configure_without_exposing_secrets(db, tg):
    telegram.handle_update(db, {"message": {"text": "/start", "chat": {"id": 555}}})
    out = sent_texts(tg)[0]
    assert out["chat_id"] == "555" and "TELEGRAM_CHAT_ID=555" in out["text"]
    assert "SECRET-TOKEN" not in out["text"]
    telegram.handle_update(db, {"message": {"text": "/start", "chat": {"id": int(CHAT)}}})
    assert "Tudo certo" in sent_texts(tg)[-1]["text"]


def test_token_never_appears_in_logs_when_the_api_fails(monkeypatch, caplog):
    monkeypatch.setattr(settings, "telegram_bot_token", "123:SECRET-TOKEN")
    def boom(url, **k): raise requests.ConnectionError(f"falha em {url}")
    monkeypatch.setattr(telegram.requests, "post", boom)
    with caplog.at_level(logging.DEBUG):
        assert telegram.call("sendMessage", {"chat_id": 1, "text": "x"}) is None
    assert "SECRET-TOKEN" not in caplog.text
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: FakeResp({"ok": False, "description": "Unauthorized"}))
    with caplog.at_level(logging.DEBUG):
        assert telegram.call("sendMessage", {"chat_id": 1, "text": "x"}) is None
    assert "SECRET-TOKEN" not in caplog.text and "Unauthorized" in caplog.text
