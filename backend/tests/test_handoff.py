"""Falar com o dono: encaminhamento da conversa, avisos e a tela de atendimento."""
import itertools
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select, update

from app.bot import engine, texts
from app.bot.channels import telegram as tg
from app.bot.types import Button, Incoming, Reply
from app.core.config import settings
from app.models import AdminUser, BusinessHours, Client, Conversation, Notification, Service
from app.services import mailer, notifications, owner_notify
from app.services import telegram as owner_telegram
from app.services.shop_settings import get_settings
from app.utils_links import whatsapp_url

_ids = itertools.count(1)
OWNER_PHONE = "5511988887777"
CLIENT_PHONE = "5511977776666"


@pytest.fixture(autouse=True)
def setup(db, admin, monkeypatch):
    """Cenário isolado + avisos externos capturados (e-mail/Telegram do dono) e segundo plano síncrono."""
    db.execute(update(Service).values(is_active=False))
    db.execute(delete(BusinessHours))
    db.add(Service(name="Manicure", price_cents=4500, duration_minutes=45))
    db.flush()
    for u in db.scalars(select(AdminUser).where(AdminUser.id != admin.id)):
        u.approved_at = None                                   # só o dono (fixture) recebe avisos neste teste
    box = SimpleNamespace(mails=[], telegram=[])
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body: box.mails.append((to, subject, body)))
    monkeypatch.setattr(owner_telegram, "send_message", lambda chat, text, buttons=None: box.telegram.append((chat, text)) or {"ok": True})
    monkeypatch.setattr(settings, "telegram_bot_token", "1:T")
    monkeypatch.setattr(settings, "telegram_chat_id", "42")
    monkeypatch.setattr(settings, "bot_allow_typed_phone", False)
    monkeypatch.setattr(owner_notify, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(engine, "run_in_background", lambda fn, *a: fn(*a))
    get_settings(db).contact_phone = OWNER_PHONE
    db.flush()
    return box


class Chat:
    def __init__(self, db, external="3001", channel="telegram"):
        self.db, self.external, self.channel = db, external, channel

    def send(self, text=None, data=None, phone=None):
        self.last = engine.handle(self.db, Incoming(channel=self.channel, external_id=self.external, message_id=f"h{next(_ids)}",
                                                    text=text, data=data, phone=phone))
        return self.last

    def conv(self):
        return self.db.scalar(select(Conversation).where(Conversation.channel == self.channel, Conversation.external_id == self.external))

    def buttons(self):
        return [b for r in self.last for row in r.buttons for b in row]

    def text(self):
        return "\n".join(r.text for r in self.last)


def mine(db, user, kind="handoff"):
    return db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.kind == kind)).all()


# ---------------- pedir pelo botão ----------------
def test_the_menu_offers_talking_to_the_owner(db):
    c = Chat(db)
    c.send("/start")
    assert ("human", "🙋 Falar com o dono") in [(b.data, b.text) for b in c.buttons()]


def test_pressing_the_button_hands_over_and_gives_the_owners_whatsapp(db, setup, admin):
    c = Chat(db)
    c.send("/start")
    r = c.send(data="human")
    assert "Já avisei o dono" in r[0].text and "toque no botão abaixo" in r[0].text
    link = next(b for b in c.buttons() if b.url)
    assert link.text == "💬 Chamar no WhatsApp" and link.data == ""
    assert link.url.startswith(f"https://wa.me/{OWNER_PHONE}?text=") and "Vim%20pelo%20atendimento%20autom" in link.url
    conv = c.conv()
    assert conv.needs_human and conv.handoff_at and conv.state == "handoff"
    assert [b.data for b in c.buttons() if not b.url] == ["menu"]


def test_without_a_contact_number_the_client_is_told_the_owner_will_answer(db):
    get_settings(db).contact_phone = None
    db.flush()
    c = Chat(db)
    r = c.send(data="human")
    assert "Ele responde assim que puder" in r[0].text and not any(b.url for b in c.buttons())


def test_the_owner_is_warned_in_the_panel_by_email_and_by_telegram(db, setup, admin):
    c = Chat(db)
    c.send("/start")
    c.send(data="mine")                                                           # (sem agendamentos)
    client = Client(name="Maria Souza", phone=CLIENT_PHONE)
    db.add(client); db.flush()
    c.conv().client_id = client.id
    c.send("quero falar com a dona sobre o meu pedido")
    n = mine(db, admin)[0]
    assert n.title == "Cliente quer falar com você" and n.link == "/atendimento"
    assert "Maria Souza (5511977776666)" in n.body and "Telegram" in n.body and "quero falar com a dona" in n.body
    assert any(to == admin.email for to, _, _ in setup.mails) and setup.telegram and setup.telegram[0][0] == "42"
    for text in [t for _, _, t in setup.mails] + [t for _, t in setup.telegram]:
        assert "Maria Souza" in text and "(11) 97777-6666" in text and "Escreveu: quero falar com a dona" in text
        assert f"https://wa.me/{CLIENT_PHONE}?text=" in text and "/atendimento" in text


def test_a_client_without_a_phone_is_still_reported_without_a_whatsapp_link(db, setup, admin):
    c = Chat(db)
    c.send(data="human")
    text = setup.telegram[0][1]
    assert "ainda não informado" in text and "wa.me" not in text and "Ela ainda não informou o celular" in text


def test_asking_twice_does_not_warn_the_owner_twice(db, setup, admin):
    c = Chat(db)
    c.send(data="human"); c.send(data="menu"); c.send(data="human")
    to_owner = [m for m in setup.mails if m[0] == admin.email]                    # (o banco real pode ter outros donos)
    assert len(mine(db, admin)) == 1 and len(to_owner) == 1 and len(setup.telegram) == 1


def test_after_the_owner_resolves_a_new_request_warns_again(db, setup, admin):
    c = Chat(db)
    c.send(data="human")
    conv = c.conv()
    conv.needs_human, conv.state = False, "idle"                                  # o dono marcou como resolvido
    conv.handoff_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.flush()
    c.send(data="human")
    assert len(mine(db, admin)) == 2 and len(setup.telegram) == 2


def test_all_panel_users_are_warned_not_only_the_owner(db, setup, admin):
    now = datetime.now(timezone.utc)
    staff = AdminUser(email="bia@gmail.com", name="Bia", password_hash=None, email_verified_at=now, approved_at=now)
    db.add(staff); db.flush()
    Chat(db).send(data="human")
    assert len(mine(db, staff)) == 1 and len(mine(db, admin)) == 1


# ---------------- pedir por palavras ----------------
@pytest.mark.parametrize("phrase", ["quero um atendente", "Preciso falar com o DONO", "falar com a dona", "isso é urgente!", "tenho uma RECLAMAÇÃO",
                                     "quero falar com uma pessoa", "cadê o humano?", "Atendente, por favor", "gostaria de falar com alguém"])
def test_words_that_ask_for_a_person_hand_over_immediately(db, phrase):
    c = Chat(db)
    c.send("/start")
    r = c.send(phrase)
    assert "Já avisei o dono" in r[0].text and c.conv().needs_human and c.conv().handoff_note == phrase[:200]


@pytest.mark.parametrize("phrase", ["quero agendar", "qual o preço da manicure?", "pedicure amanhã", "obrigada", "donato", "abandono"])
def test_ordinary_messages_do_not_trigger_a_handoff(db, phrase):
    c = Chat(db)
    c.send("/start")
    c.send(phrase)
    assert not c.conv().needs_human


def test_a_name_that_contains_the_word_dona_is_not_mistaken_for_a_request(db):
    """Quando o bot está pedindo o NOME, "Dona Maria" é um nome, não um pedido de atendente."""
    c = Chat(db)
    c.send("/start"); c.send(data="book"); c.send(data=f"svc:{db.scalar(select(Service.id).where(Service.name == 'Manicure'))}")
    c.conv().state = "ask_name"
    c.conv().phone, c.conv().phone_verified = CLIENT_PHONE, True
    db.flush()
    c.send("Dona Maria")
    assert not c.conv().needs_human and c.conv().client_id is not None
    assert db.get(Client, c.conv().client_id).name == "Dona Maria"


def test_the_handoff_note_is_cleaned_and_limited(db):
    c = Chat(db)
    c.send("quero falar com o dono " + "x" * 400 + "\x07\x1b")
    note = c.conv().handoff_note
    assert len(note) <= 200 and "\x07" not in note and "\x1b" not in note


# ---------------- não entendeu ----------------
def test_after_two_misunderstandings_it_offers_a_person(db):
    c = Chat(db)
    c.send("/start")
    first = c.send("blablabla")
    assert first[0].text == texts.NOT_UNDERSTOOD and [b.data for b in c.buttons()][:2] == ["book", "hours"]
    second = c.send("asdfgh")
    assert second[0].text == texts.HANDOFF_OFFER
    assert [b.data for b in c.buttons()] == ["human", "menu"] and not c.conv().needs_human           # só oferece, não encaminha sozinho
    c.send(data="human")
    assert c.conv().needs_human


def test_a_button_press_resets_the_misunderstanding_counter(db):
    c = Chat(db)
    c.send("/start"); c.send("blablabla")
    c.send(data="hours"); c.send(data="menu")
    assert c.send("blablabla")[0].text == texts.NOT_UNDERSTOOD                    # recomeçou do zero (1º, não 2º)


# ---------------- o bot não fala por cima ----------------
def test_while_waiting_for_the_owner_the_bot_stays_quiet_after_one_reminder(db):
    c = Chat(db)
    c.send(data="human")
    first = c.send("alguém aí?")
    assert first == []                                                              # logo após o pedido o aviso já foi dado: silêncio
    for msg in ["oi?", "estou aguardando", "pode me ajudar?"]:
        assert c.send(msg) == []                                                    # silêncio
    assert c.conv().handoff_note == "pode me ajudar?"                               # mas o dono vê a última mensagem


def test_the_reminder_returns_after_ten_minutes(db):
    c = Chat(db)
    c.send(data="human")
    c.conv().context = {"ack_at": (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()}
    db.flush()
    r = c.send("e então?")
    assert r and r[0].text == texts.HANDOFF_WAIT


def test_tapping_menu_brings_the_assistant_back_but_the_request_stays_open(db):
    c = Chat(db)
    c.send(data="human")
    r = c.send(data="menu")
    assert "assistente de agendamentos" in r[0].text
    assert c.conv().state == "idle" and c.conv().needs_human is True                # o dono ainda precisa resolver
    c.send(data="book")
    assert "Qual serviço" in c.text()                                               # o assistente voltou a funcionar


def test_any_button_in_handoff_resumes_the_assistant(db):
    c = Chat(db)
    c.send(data="human")
    c.send(data="hours")
    assert c.conv().state == "idle" and "Horários de atendimento" in c.text() or "não foram cadastrados" in c.text()


def test_sharing_the_phone_while_waiting_is_recorded_silently(db):
    c = Chat(db)
    c.send(data="human")
    assert c.send(phone=CLIENT_PHONE) == [] and c.conv().phone == CLIENT_PHONE and c.conv().phone_verified


def test_an_expired_session_does_not_keep_the_assistant_muted_forever(db):
    c = Chat(db)
    c.send(data="human")
    c.conv().last_message_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.flush()
    r = c.send("oi")
    assert c.conv().state == "idle" and r                                           # o assistente responde de novo


# ---------------- Telegram: botão de link ----------------
def test_the_telegram_adapter_sends_a_url_button_without_callback_data():
    reply = Reply("x", [[Button("💬 Chamar no WhatsApp", "", url="https://wa.me/5511988887777?text=Ol%C3%A1")], [Button("⬅️ Menu", "menu")]])
    kb = tg.to_payload("1", reply)["reply_markup"]["inline_keyboard"]
    assert kb[0][0] == {"text": "💬 Chamar no WhatsApp", "url": "https://wa.me/5511988887777?text=Ol%C3%A1"}
    assert kb[1][0] == {"text": "⬅️ Menu", "callback_data": "menu"}
    assert "callback_data" not in kb[0][0]


def test_the_handoff_button_labels_fit_the_whatsapp_limit():
    from app.bot.types import MAX_BUTTON_TEXT
    assert len(texts.BTN_HUMAN) <= MAX_BUTTON_TEXT and len(texts.BTN_WHATSAPP) <= MAX_BUTTON_TEXT


def test_the_whatsapp_helper_only_accepts_brazilian_numbers():
    assert whatsapp_url(OWNER_PHONE, "oi") == f"https://wa.me/{OWNER_PHONE}?text=oi"
    for bad in (None, "", "123", "11988887777", "+1 415 555 2671", "5511abc"):
        assert whatsapp_url(bad, "oi") is None
    assert "%26" in whatsapp_url(OWNER_PHONE, "a&phone=1") and "&phone" not in whatsapp_url(OWNER_PHONE, "a&phone=1")


# ---------------- configuração do número do dono ----------------
def test_the_owner_sets_and_clears_the_contact_number(client, auth, db):
    r = client.put("/api/v1/settings", headers=auth, json={"contact_phone": "(11) 98888-7777"})
    assert r.status_code == 200 and r.json()["contact_phone"] == OWNER_PHONE
    assert client.get("/api/v1/settings", headers=auth).json()["contact_phone"] == OWNER_PHONE
    assert client.put("/api/v1/settings", headers=auth, json={"contact_phone": ""}).json()["contact_phone"] is None
    assert client.put("/api/v1/settings", headers=auth, json={"contact_phone": None}).json()["contact_phone"] is None


def test_the_contact_number_is_validated_and_the_interval_is_untouched(client, auth, db):
    before = client.get("/api/v1/settings", headers=auth).json()["slot_interval_minutes"]
    for bad in ("123", "abc", "+1 415 555 2671"):
        assert client.put("/api/v1/settings", headers=auth, json={"contact_phone": bad}).status_code == 422
    assert client.put("/api/v1/settings", headers=auth, json={"contact_phone": "11988887777"}).json()["slot_interval_minutes"] == before


def test_each_field_can_be_updated_alone_and_empty_updates_are_refused(client, auth):
    assert client.put("/api/v1/settings", headers=auth, json={"slot_interval_minutes": 45}).json()["slot_interval_minutes"] == 45
    assert client.put("/api/v1/settings", headers=auth, json={}).status_code == 422
    assert client.put("/api/v1/settings", headers=auth, json={"slot_interval_minutes": None}).status_code == 422
    assert client.put("/api/v1/settings", headers=auth, json={"slot_interval_minutes": 1}).status_code == 422
    assert client.put("/api/v1/settings", json={"contact_phone": "11988887777"}).status_code == 401


# ---------------- tela "Atendimento" (API) ----------------
URL = "/api/v1/conversations"


def make_waiting(db, name="Maria Souza", phone=CLIENT_PHONE, minutes_ago=5, note="preciso remarcar", ext=None):
    client = Client(name=name, phone=phone) if name else None
    if client:
        db.add(client); db.flush()
    conv = Conversation(channel="telegram", external_id=ext or f"w{next(_ids)}", client_id=client.id if client else None,
                        phone=phone, phone_verified=True, state="handoff", context={}, needs_human=True,
                        handoff_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago), handoff_note=note)
    db.add(conv); db.flush()
    return conv


def test_conversations_require_login(client):
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/1/resolve").status_code == 401


def test_the_list_shows_who_is_waiting_oldest_first_with_what_they_wrote(client, auth, db):
    newer = make_waiting(db, "Nova", "5511900000002", 2, "oi")
    older = make_waiting(db, "Antiga", "5511900000001", 30, "urgente!")
    resolved = make_waiting(db, "Resolvida", "5511900000003", 60)
    resolved.needs_human = False
    db.flush()
    rows = [r for r in client.get(URL, headers=auth).json() if r["id"] in {newer.id, older.id, resolved.id}]
    assert [r["id"] for r in rows] == [older.id, newer.id]                          # a que espera há mais tempo vem primeiro
    first = rows[0]
    assert first["client_name"] == "Antiga" and first["client_phone"] == "5511900000001" and first["handoff_note"] == "urgente!"
    assert first["channel"] == "telegram" and first["needs_human"] is True and first["handoff_at"]
    assert set(first) == {"id", "channel", "client_name", "client_phone", "phone_verified", "needs_human", "handoff_at", "handoff_note", "last_message_at"}


def test_a_conversation_without_a_registered_client_still_appears_with_the_phone(client, auth, db):
    conv = make_waiting(db, name=None, phone="5511900000009", note=None)
    row = next(r for r in client.get(URL, headers=auth).json() if r["id"] == conv.id)
    assert row["client_name"] is None and row["client_phone"] == "5511900000009"


def test_resolving_removes_it_from_the_list_and_returns_the_assistant(client, auth, db, admin):
    conv = make_waiting(db)
    r = client.post(f"{URL}/{conv.id}/resolve", headers=auth)
    assert r.status_code == 200 and r.json()["needs_human"] is False and r.json()["handoff_note"] is None
    assert conv.id not in [x["id"] for x in client.get(URL, headers=auth).json()]
    db.refresh(conv)
    assert conv.state == "idle" and conv.needs_human is False
    from app.models import AuditLog
    assert db.scalars(select(AuditLog).where(AuditLog.entity_id == conv.id, AuditLog.action == "handoff_resolve")).one().admin_user_id == admin.id
    assert client.post(f"{URL}/{conv.id}/resolve", headers=auth).status_code == 200      # repetir é inofensivo
    assert client.post(f"{URL}/99999999/resolve", headers=auth).status_code == 404


def test_the_flag_can_be_filtered_and_the_limit_is_validated(client, auth, db):
    done = make_waiting(db)
    done.needs_human = False
    db.flush()
    assert done.id in [r["id"] for r in client.get(URL, params={"needs_human": False}, headers=auth).json()]
    assert client.get(URL, params={"limit": 0}, headers=auth).status_code == 422
    assert client.get(URL, params={"limit": 201}, headers=auth).status_code == 422


def test_a_user_without_panel_access_cannot_see_conversations(client, db):
    from app.core.security import create_access_token, password_version
    pending = AdminUser(email="p@gmail.com", name="P", password_hash=None, email_verified_at=datetime.now(timezone.utc))
    db.add(pending); db.flush()
    h = {"Authorization": f"Bearer {create_access_token(pending.id, password_version(pending))}"}
    assert client.get(URL, headers=h).status_code == 403


def test_after_resolving_the_client_can_ask_again_and_the_owner_is_warned_again(client, auth, db, setup, admin):
    c = Chat(db)
    c.send(data="human")
    conv_id = c.conv().id
    client.post(f"{URL}/{conv_id}/resolve", headers=auth)
    c.send(data="human")
    assert len(mine(db, admin)) == 2 and c.conv().needs_human
