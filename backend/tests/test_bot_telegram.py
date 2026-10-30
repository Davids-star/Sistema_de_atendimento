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
    keyboard = sent[0]["reply_markup"]["inline_keyboard"]
    assert [b["callback_data"] for row in keyboard for b in row] == ["book", "hours", "mine", "human"]


def test_a_click_edits_the_message_in_place_with_a_single_main_call(wire):
    tg.process_update(msg("/start", uid=1))
    wire.clear()
    tg.process_update(click("book", uid=2))
    names = methods(wire)
    assert "answerCallbackQuery" in names                                    # tira o "relógio" do botão
    assert names.count("editMessageText") == 1 and "sendMessage" not in names   # 1 chamada principal, não 3
    edit = next(p for m, p in wire if m == "editMessageText")
    assert edit["chat_id"] == 555 and edit["message_id"] == 9 and "Qual serviço" in edit["text"]
    assert "inline_keyboard" in edit["reply_markup"] and "parse_mode" not in edit


def test_edit_without_buttons_also_removes_the_old_buttons(wire):
    tg.process_update(msg("/start", uid=1))
    tg.process_update(click("book", uid=2)); tg.process_update(click("svc:1", uid=3)) if False else None
    from app.bot.types import Reply
    payload = tg._edit_payload(555, 9, Reply("só texto"))
    assert "reply_markup" not in payload and payload["text"] == "só texto"   # sem reply_markup, o Telegram tira os botões


def test_contact_request_cannot_be_an_edit_so_it_sends_a_new_message(wire, monkeypatch):
    from app.bot import engine as eng
    from app.bot.types import Reply
    monkeypatch.setattr(eng, "handle", lambda db, inc: [Reply("preciso do número", ask_contact=True)])
    tg.process_update(click("time:20300101T1200", uid=5))
    names = methods(wire)
    assert "editMessageReplyMarkup" in names and "sendMessage" in names and "editMessageText" not in names
    sent = next(p for m, p in wire if m == "sendMessage")
    assert sent["reply_markup"]["keyboard"][0][0]["request_contact"] is True


def test_if_the_edit_fails_the_reply_is_sent_as_a_new_message(monkeypatch, db):
    monkeypatch.setattr(settings, "customer_bot_token", "999:CUSTOMER-SECRET")
    monkeypatch.setattr(tg, "SessionLocal", lambda: nullcontext(db))
    calls = []
    def fake(method, payload, timeout=15):
        calls.append(method)
        return None if method == "editMessageText" else {"ok": True, "result": []}   # a edição falhou (ex.: mensagem apagada)
    monkeypatch.setattr(tg, "call", fake)
    tg.process_update(msg("/start", uid=1)); calls.clear()
    tg.process_update(click("book", uid=2))
    assert "editMessageText" in calls and "sendMessage" in calls               # não deixa a cliente sem resposta


def test_the_connection_is_reused_across_calls():
    import requests as rq
    assert isinstance(tg._session, rq.Session)
    adapter = tg._session.get_adapter("https://api.telegram.org")
    assert adapter.max_retries.connect == 2 and adapter.max_retries.read == 0   # tenta de novo só ao CONECTAR: nunca duplica mensagem


def test_responses_log_their_timing_without_content(wire, caplog):
    with caplog.at_level(logging.INFO):
        tg.process_update(msg("/start", uid=1))
    line = next(r.getMessage() for r in caplog.records if "resposta em" in r.getMessage())
    assert "cérebro" in line and "envio" in line and "assistente" not in line   # só tempos, nunca o texto da conversa


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
    monkeypatch.setattr(tg._session, "post", boom)
    with caplog.at_level(logging.DEBUG):
        assert tg.call("sendMessage", {"chat_id": 1, "text": "x"}) is None
    assert "CUSTOMER-SECRET" not in caplog.text


def test_no_token_means_no_calls(monkeypatch):
    monkeypatch.setattr(settings, "customer_bot_token", "")
    monkeypatch.setattr(tg._session, "post", lambda *a, **k: pytest.fail("não deveria chamar a rede"))
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
