import logging
from contextlib import nullcontext

import pytest
import requests

from app.bot import engine
from app.bot.channels import telegram as tg
from app.bot.types import Button, Reply
from app.core.config import settings


def msg(text=None, *, chat_type="private", chat_id=555, from_id=555, contact=None, uid=10):
    m = {"chat": {"id": chat_id, "type": chat_type}, "from": {"id": from_id}}
    if text is not None:
        m["text"] = text
    if contact is not None:
        m["contact"] = contact
    return {"update_id": uid, "message": m}


def click(data, *, chat_type="private", chat_id=555, uid=11):
    return {"update_id": uid, "callback_query": {"id": "cb1", "data": data,
                                                  "message": {"message_id": 9, "chat": {"id": chat_id, "type": chat_type}}}}


# ---------- Telegram -> cérebro ----------
def test_text_message_becomes_incoming():
    inc = tg.to_incoming(msg("oi"))
    assert (inc.channel, inc.external_id, inc.message_id, inc.text, inc.data, inc.phone) == ("telegram", "555", "tg:10", "oi", None, None)


def test_button_click_becomes_incoming_with_data():
    inc = tg.to_incoming(click("svc:3"))
    assert inc.data == "svc:3" and inc.text is None and inc.external_id == "555" and inc.message_id == "tg:11"


def test_group_chats_and_unknown_updates_are_ignored():
    assert tg.to_incoming(msg("oi", chat_type="group")) is None
    assert tg.to_incoming(msg("oi", chat_type="supergroup")) is None
    assert tg.to_incoming(click("book", chat_type="channel")) is None
    assert tg.to_incoming({"update_id": 1, "edited_message": {}}) is None


def test_own_contact_is_accepted_as_a_verified_phone():
    inc = tg.to_incoming(msg(contact={"phone_number": "5511977776666", "user_id": 555, "first_name": "Ana"}))
    assert inc.phone == "5511977776666" and not inc.contact_rejected


@pytest.mark.parametrize("contact", [
    {"phone_number": "5511900001111", "user_id": 999, "first_name": "Outra"},   # contato de outra pessoa
    {"phone_number": "5511900001111", "first_name": "Sem dono"},                # contato sem dono identificado (digitado/da agenda)
])
def test_someone_elses_contact_is_rejected(contact):
    inc = tg.to_incoming(msg(contact=contact))
    assert inc.contact_rejected and inc.phone is None


# ---------- cérebro -> Telegram ----------
def test_payload_shapes():
    plain = tg.to_payload("555", Reply("oi"))
    assert plain["reply_markup"] == {"remove_keyboard": True} and "parse_mode" not in plain      # texto puro

    inline = tg.to_payload("555", Reply("x", [[Button("A", "a"), Button("B", "b")], [Button("C", "c")]]))
    assert inline["reply_markup"]["inline_keyboard"] == [[{"text": "A", "callback_data": "a"}, {"text": "B", "callback_data": "b"}],
                                                          [{"text": "C", "callback_data": "c"}]]
    contact = tg.to_payload("555", Reply("x", ask_contact=True))["reply_markup"]
    assert contact["keyboard"][0][0]["request_contact"] is True and contact["one_time_keyboard"] is True


# ---------- ponta a ponta com o Telegram simulado ----------
@pytest.fixture
def wire(monkeypatch, db):
    """Liga o adaptador ao banco do teste e registra tudo o que seria enviado ao Telegram."""
    monkeypatch.setattr(settings, "customer_bot_token", "999:CUSTOMER-SECRET")
    monkeypatch.setattr(tg, "SessionLocal", lambda: nullcontext(db))
    calls = []
    monkeypatch.setattr(tg, "call", lambda method, payload, timeout=15: calls.append((method, payload)) or {"ok": True, "result": []})
    return calls


def methods(calls):
    return [m for m, _ in calls]


def test_process_update_sends_the_menu_for_start(wire):
    tg.process_update(msg("/start", uid=1))
    sent = [p for m, p in wire if m == "sendMessage"]
    assert len(sent) == 1 and sent[0]["chat_id"] == "555" and "assistente de agendamentos" in sent[0]["text"]
    assert [b["callback_data"] for b in sent[0]["reply_markup"]["inline_keyboard"][0] + sent[0]["reply_markup"]["inline_keyboard"][1]] == ["book", "mine"]


def test_button_clicks_are_acknowledged_and_old_buttons_removed(wire):
    tg.process_update(msg("/start", uid=1))
    wire.clear()
    tg.process_update(click("book", uid=2))
    assert methods(wire)[:2] == ["answerCallbackQuery", "editMessageReplyMarkup"]
    assert wire[1][1]["reply_markup"] == {"inline_keyboard": []}              # botões antigos saem: ninguém toca duas vezes
    assert "sendMessage" in methods(wire)


def test_group_messages_produce_no_traffic(wire):
    tg.process_update(msg("/start", chat_type="group", uid=3))
    assert wire == []


def test_the_telegram_redelivering_an_update_does_not_answer_twice(wire):
    tg.process_update(msg("/start", uid=7))
    first = len(wire)
    tg.process_update(msg("/start", uid=7))
    assert len(wire) == first


def test_token_never_appears_in_logs(monkeypatch, caplog):
    monkeypatch.setattr(settings, "customer_bot_token", "999:CUSTOMER-SECRET")
    def boom(url, **k): raise requests.ConnectionError(f"falha em {url}")
    monkeypatch.setattr(tg.requests, "post", boom)
    with caplog.at_level(logging.DEBUG):
        assert tg.call("sendMessage", {"chat_id": 1, "text": "x"}) is None
    assert "CUSTOMER-SECRET" not in caplog.text


def test_no_token_means_no_calls(monkeypatch):
    monkeypatch.setattr(settings, "customer_bot_token", "")
    monkeypatch.setattr(tg.requests, "post", lambda *a, **k: pytest.fail("não deveria chamar a rede"))
    assert tg.call("sendMessage", {"chat_id": 1}) is None


def test_runner_refuses_to_reuse_the_owner_bot_token(monkeypatch, capsys):
    import importlib, sys
    monkeypatch.setattr(settings, "customer_bot_token", "same:TOKEN")
    monkeypatch.setattr(settings, "telegram_bot_token", "same:TOKEN")
    sys.path.insert(0, "backend")
    runner = importlib.import_module("customer_bot")
    with pytest.raises(SystemExit) as e:
        runner.main()
    assert "mesmo bot do dono" in str(e.value)
