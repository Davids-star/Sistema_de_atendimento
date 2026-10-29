"""Conversas completas com o cérebro do bot, como uma cliente real faria (sem Telegram, sem rede)."""
import itertools
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select, update

from app.bot import engine, texts
from app.bot.types import Incoming
from app.core import rate_limit
from app.models import Appointment, BusinessHours, Client, Conversation, Service, WhatsAppMessage
from app.services import appointments as appt_service
from app.services import owner_notify

_ids = itertools.count(1)
PHONE = "5511977776666"


@pytest.fixture(autouse=True)
def studio(db, monkeypatch):
    """Cenário controlado: o banco real pode ter serviços/horários seus, então isolamos dentro da transação do teste."""
    db.execute(update(Service).values(is_active=False))
    db.execute(delete(BusinessHours))
    db.add_all(BusinessHours(weekday=d, start_time=datetime(2000, 1, 1, 9).time(), end_time=datetime(2000, 1, 1, 18).time())
               for d in range(7))
    db.add_all([Service(name="Manicure", price_cents=4500, duration_minutes=45),
                Service(name="Pedicure", price_cents=5500, duration_minutes=60)])
    db.flush()
    booked = []
    monkeypatch.setattr(owner_notify, "notify_owner_booking", lambda appointment_id, via="bot": booked.append((appointment_id, via)))
    return booked


class Chat:
    """Uma pessoa conversando. `external` identifica a conversa no canal."""

    def __init__(self, db, external="1001", channel="telegram"):
        self.db, self.external, self.channel = db, external, channel

    def send(self, text=None, data=None, phone=None, rejected=False, message_id=None):
        inc = Incoming(channel=self.channel, external_id=self.external, message_id=message_id or f"m{next(_ids)}",
                       text=text, data=data, phone=phone, contact_rejected=rejected)
        self.last = engine.handle(self.db, inc)
        return self.last

    def text(self):
        return "\n".join(r.text for r in self.last)

    def buttons(self):
        return [b for r in self.last for row in r.buttons for b in row]

    def press(self, label_part):
        match = next((b for b in self.buttons() if label_part in b.text), None)
        assert match, f"botão '{label_part}' não encontrado. Botões: {[b.text for b in self.buttons()]}"
        return self.send(data=match.data)

    def conv(self):
        return self.db.scalar(select(Conversation).where(Conversation.channel == self.channel, Conversation.external_id == self.external))


def book_until_confirm(chat, service="Manicure", with_phone=True):
    chat.send("/start")
    chat.press("Agendar")
    chat.press(service)
    chat.press("")            # primeiro dia disponível
    chat.press(":")           # primeiro horário
    if with_phone:
        chat.send(phone=PHONE)


def appointments(db):
    return db.scalars(select(Appointment).join(Client).where(Client.phone == PHONE)).all()


# ---------------------------------------------------------------- fluxo feliz
def test_full_booking_for_a_new_client_on_telegram(db, studio):
    c = Chat(db)
    r = c.send("/start")
    assert "assistente de agendamentos" in r[0].text and [b.data for b in c.buttons()] == ["book", "mine"]

    c.press("Agendar")
    assert "Qual serviço" in c.text()
    assert {"Manicure · 45 min · R$ 45,00", "Pedicure · 1 h · R$ 55,00"} <= {b.text for b in c.buttons()}

    c.press("Manicure")
    assert c.text() == texts.CHOOSE_DAY and any(b.text.startswith("Hoje") or b.text.startswith("Amanhã") or b.data.startswith("day:") for b in c.buttons())
    c.press("")               # escolhe o primeiro dia
    assert c.text() == texts.CHOOSE_TIME
    time_btn = next(b for b in c.buttons() if b.data.startswith("time:"))
    c.send(data=time_btn.data)
    assert c.last[0].ask_contact and "número de celular" in c.text()      # Telegram: pede o contato nativo

    c.send(phone=PHONE)                                                     # contato compartilhado
    assert c.text() == texts.ASK_NAME
    c.send("Maria da Silva")
    assert "Confira o seu agendamento" in c.text() and "Manicure" in c.text() and "R$ 45,00" in c.text() and "Maria da Silva" in c.text()

    c.press("Confirmar")
    assert "✅ Agendado!" in c.text()
    appt = appointments(db)[0]
    assert (appt.status, appt.source, appt.price_cents) == ("confirmed", "telegram", 4500)
    assert appt.client.name == "Maria da Silva" and appt.client.phone == PHONE
    assert c.conv().state == "idle"
    assert studio == [(appt.id, "telegram")]                                # o dono foi avisado


def test_a_returning_client_skips_phone_and_name(db):
    first = Chat(db)
    book_until_confirm(first)
    first.send("Ana Paula")
    first.press("Confirmar")
    again = Chat(db)                                                         # mesma conversa de novo, dias depois
    again.send("/start")
    assert "Olá, Ana!" in again.text()
    again.press("Agendar"); again.press("Pedicure"); again.press(""); again.press(":")
    assert "Confira o seu agendamento" in again.text() and "Pedicure" in again.text()
    again.press("Confirmar")
    assert len(appointments(db)) == 2


def test_known_client_by_phone_is_recognized_and_not_asked_for_a_name(db):
    db.add(Client(name="Beatriz Souza", phone=PHONE))
    db.flush()
    c = Chat(db)
    book_until_confirm(c)                                                    # compartilha o contato
    assert "Confira o seu agendamento" in c.text() and "Beatriz Souza" in c.text()
    assert c.conv().client_id is not None


def test_whatsapp_style_channel_already_has_the_phone(db):
    """No WhatsApp o número vem em toda mensagem: nunca pede o telefone, só o nome (se for cliente nova)."""
    c = Chat(db, "5511977776666", channel="whatsapp")
    c.send("oi", phone=PHONE)
    c.press("Agendar"); c.press("Manicure"); c.press(""); c.press(":")
    assert c.text() == texts.ASK_NAME and not c.last[0].ask_contact
    c.send("Júlia Mota")
    c.press("Confirmar")
    assert appointments(db)[0].source == "whatsapp"


# ---------------------------------------------------------------- horário
def test_slot_taken_by_someone_else_before_confirming(db):
    c = Chat(db)
    book_until_confirm(c)
    c.send("Maria Souza")
    ctx = c.conv().context
    service = db.scalar(select(Service).where(Service.name == "Manicure"))
    other = Client(name="Outra Pessoa", phone="5511900001111")
    db.add(other)
    db.flush()
    appt_service.create_appointment(db, admin=None, client_id=other.id, client_phone=None, client_name=None, service_id=service.id,
                                    starts_at=datetime.fromisoformat(ctx["start"]), notes=None, status="confirmed", source="admin", strict=False)
    c.press("Confirmar")
    assert texts.SLOT_TAKEN in c.text() and c.conv().state == "choose_time"   # volta a oferecer horários
    assert appointments(db) == []
    c.press(":")                                                              # escolhe outro horário livre
    assert "Confira o seu agendamento" in c.text()
    c.press("Confirmar")
    assert len(appointments(db)) == 1


def test_a_forged_or_stale_time_button_is_not_booked(db):
    c = Chat(db)
    c.send("/start"); c.press("Agendar"); c.press("Manicure"); c.press("")
    c.send(data="time:20200101T1200")                                         # passado
    assert texts.SLOT_GONE in c.text() and appointments(db) == []
    c.send(data="time:isso-nao-e-data")
    assert texts.EXPIRED in c.text()
    c.send(data="time:20991231T0300")                                         # fora do expediente
    assert appointments(db) == []


def test_buttons_out_of_order_are_refused(db):
    c = Chat(db)
    r = c.send(data="yes")                                                    # confirmar sem ter escolhido nada
    assert texts.EXPIRED in r[0].text and appointments(db) == []
    for bad in ["svc:999999", "svc:abc", "day:nao-e-data", "time:x", "cancel:1", "cancel_yes:1", "hack:1", "", "svc:"]:
        c.send(data=bad)
        assert appointments(db) == []


def test_inactive_service_cannot_be_booked(db):
    c = Chat(db)
    c.send("/start"); c.press("Agendar")
    sid = int(next(b.data for b in c.buttons() if b.data.startswith("svc:") and "Manicure" in b.text).split(":")[1])
    db.get(Service, sid).is_active = False
    db.flush()
    c.send(data=f"svc:{sid}")
    assert texts.EXPIRED in c.text()


def test_cannot_book_in_the_past_even_with_a_lucky_guess(db):
    c = Chat(db)
    book_until_confirm(c)
    c.send("Maria Souza")
    ctx = c.conv().context
    c.conv().context = {**ctx, "start": "2020-01-06T12:00:00+00:00"}          # adultera o estado guardado
    db.flush()
    c.press("Confirmar")
    assert appointments(db) == []                                             # strict=True recusa o passado


# ---------------------------------------------------------------- identidade / segurança
def test_a_contact_from_another_person_is_rejected(db):
    c = Chat(db)
    book_until_confirm(c, with_phone=False)
    r = c.send(rejected=True)
    assert r[0].text == texts.BAD_CONTACT and r[0].ask_contact
    assert c.conv().phone is None and c.conv().client_id is None


def test_typing_a_phone_does_not_identify_the_person_on_telegram(db):
    """No Telegram só vale o contato nativo. Digitar o número de outra pessoa não dá acesso aos dados dela."""
    victim = Client(name="Vítima", phone=PHONE)
    db.add(victim)
    db.flush()
    c = Chat(db)
    book_until_confirm(c, with_phone=False)
    c.send(PHONE)                                                             # digita o número da vítima
    assert c.last[0].ask_contact and c.conv().client_id is None and c.conv().phone is None
    c.send("(11) 97777-6666")
    assert c.conv().client_id is None
    c.send(data="mine")
    assert texts.NOTHING_BOOKED in c.text()                                   # não enxerga nada da vítima


def test_invalid_names_are_refused(db):
    c = Chat(db)
    book_until_confirm(c)
    for bad in ["", "A", "12345", "!!!", "x" * 200]:
        c.send(bad or "  ")
        assert c.conv().client_id is None, bad
    assert c.conv().state == "ask_name"
    c.send("  Maria   do\u0007 Carmo  ")                                       # espaços e caractere de controle são limpos
    assert c.conv().client_id is not None
    assert db.get(Client, c.conv().client_id).name == "Maria do Carmo"


def test_names_with_markup_are_stored_as_plain_text(db):
    c = Chat(db)
    book_until_confirm(c)
    c.send("<b>Ana</b> *Souza*")
    assert db.get(Client, c.conv().client_id).name == "<b>Ana</b> *Souza*"    # guardado literal; o envio é sem formatação


# ---------------------------------------------------------------- meus agendamentos / cancelar
def test_list_and_cancel_my_appointment(db):
    c = Chat(db)
    book_until_confirm(c); c.send("Maria Souza"); c.press("Confirmar")
    c.press("Meus agendamentos")
    assert "Seus próximos agendamentos" in c.text() and "Manicure" in c.text() and "confirmado" in c.text()
    c.press("Cancelar 1")
    assert "Cancelar Manicure" in c.text()
    c.press("Sim, cancelar")
    assert c.text() == texts.CANCELLED
    assert appointments(db)[0].status == "cancelled"
    c.press("Meus agendamentos")
    assert texts.NOTHING_BOOKED in c.text()
    assert db.scalars(select(Appointment).where(Appointment.status == "cancelled")).first() is not None


def test_cannot_cancel_someone_elses_appointment(db):
    owner_chat = Chat(db, "1001")
    book_until_confirm(owner_chat); owner_chat.send("Maria Souza"); owner_chat.press("Confirmar")
    victim_appt = appointments(db)[0]

    attacker = Chat(db, "2002")
    attacker.send("/start")
    attacker.send(phone="5511988880000")
    attacker.send("/start"); attacker.press("Agendar")
    for data in (f"cancel:{victim_appt.id}", f"cancel_yes:{victim_appt.id}"):
        r = attacker.send(data=data)
        assert texts.CANNOT_CANCEL in r[0].text
    db.refresh(victim_appt)
    assert victim_appt.status == "confirmed"


def test_past_or_already_cancelled_appointments_cannot_be_cancelled(db):
    c = Chat(db)
    book_until_confirm(c); c.send("Maria Souza"); c.press("Confirmar")
    appt = appointments(db)[0]
    db.execute(update(Appointment).where(Appointment.id == appt.id).values(
        starts_at=datetime.now(timezone.utc) - timedelta(hours=2), ends_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    db.expire_all()
    r = c.send(data=f"cancel_yes:{appt.id}")
    assert texts.CANNOT_CANCEL in r[0].text and db.get(Appointment, appt.id).status == "confirmed"


# ---------------------------------------------------------------- robustez
def test_duplicate_messages_are_processed_once(db):
    c = Chat(db)
    first = c.send("/start", message_id="tg:777")
    again = c.send("/start", message_id="tg:777")                             # o Telegram reentregou
    assert first and again == []
    assert db.scalars(select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == "tg:777")).all().__len__() == 1


def test_writing_instead_of_pressing_a_button_repeats_the_step(db):
    c = Chat(db)
    c.send("/start"); c.press("Agendar")
    r = c.send("quero amanhã de manhã")
    assert r[0].text == texts.USE_BUTTONS and any(b.data.startswith("svc:") for b in c.buttons())


def test_menu_words_reset_the_conversation_anywhere(db):
    c = Chat(db)
    book_until_confirm(c)
    c.send("menu")
    assert c.conv().state == "idle" and c.conv().context == {}
    assert [b.data for b in c.buttons()] == ["book", "mine"]


def test_an_old_conversation_expires(db):
    c = Chat(db)
    c.send("/start"); c.press("Agendar"); c.press("Manicure")
    c.conv().last_message_at = datetime.now(timezone.utc) - timedelta(hours=3)
    db.flush()
    r = c.send(data="day:2030-01-07")                                         # botão de uma conversa que já passou
    assert texts.EXPIRED in r[0].text and c.conv().state == "idle"


def test_flooding_is_ignored(db):
    c = Chat(db)
    replies = [c.send("oi") for _ in range(engine.RATE_PER_MINUTE + 5)]
    assert all(replies[: engine.RATE_PER_MINUTE]) and replies[-1] == []


def test_conversations_are_isolated_per_chat(db):
    a, b = Chat(db, "1"), Chat(db, "2")
    a.send("/start"); a.press("Agendar"); a.press("Manicure")
    b.send("/start")
    assert b.conv().state == "idle" and a.conv().state == "choose_day"


def test_no_services_or_no_availability_are_handled(db):
    db.execute(update(Service).values(is_active=False))
    c = Chat(db)
    c.send("/start"); c.press("Agendar")
    assert c.text() == texts.NO_SERVICES
    db.add(Service(name="Spa", price_cents=1000, duration_minutes=30))
    db.execute(delete(BusinessHours))                                         # fechado todos os dias
    db.flush()
    c.send("/start"); c.press("Agendar"); c.press("Spa")
    assert c.text() == texts.NO_DAYS


def test_an_unexpected_error_never_reaches_the_customer_as_a_crash(db, monkeypatch):
    monkeypatch.setattr(engine, "_menu", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = Chat(db).send("/start")
    assert "probleminha" in r[0].text


def test_texts_have_no_barbershop_wording():
    import inspect
    assert "barbe" not in inspect.getsource(texts).lower()


def test_every_button_fits_telegrams_64_byte_limit(db):
    c = Chat(db)
    seen = []
    book_until_confirm(c)
    c.send("Maria Souza")
    for step in (lambda: c.send("/start"), lambda: c.press("Agendar"), lambda: c.press("Manicure"), lambda: c.press(""),
                 lambda: c.press(":"), lambda: c.press("Confirmar"), lambda: c.press("Meus agendamentos")):
        step()
        seen += [b.data for b in c.buttons()]
    assert seen and all(len(d.encode()) <= 64 for d in seen), max(seen, key=len)
