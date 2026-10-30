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
    monkeypatch.setattr(engine, "run_in_background", lambda fn, *a: fn(*a))   # nos testes, roda na hora (sem thread)
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
    assert "assistente de agendamentos" in r[0].text and [b.data for b in c.buttons()] == ["book", "hours", "mine", "human"]

    c.press("Agendar")
    assert "Qual serviço" in c.text()
    by_title = {b.text: b.description for b in c.buttons()}
    assert by_title["Manicure"] == "45 min · R$ 45,00" and by_title["Pedicure"] == "1 h · R$ 55,00"   # título curto + detalhe

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
    assert [b.data for b in c.buttons()] == ["book", "hours", "mine", "human"]


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


# ---------------------------------------------------------------- portabilidade (WhatsApp) e velocidade
def walk_flow(c):
    """Percorre uma conversa inteira e devolve todas as telas (listas de Reply) pelas quais a cliente passou."""
    screens = []
    for step in (lambda: c.send("/start"), lambda: c.press("Agendar"), lambda: c.press("Manicure"), lambda: c.press(""),
                 lambda: c.press(":"), lambda: c.send(phone=PHONE), lambda: c.send("Maria Souza"), lambda: c.press("Confirmar"),
                 lambda: c.press("Meus agendamentos"), lambda: c.press("Cancelar 1")):
        step()
        screens.append(list(c.last))
    return screens


def test_every_screen_respects_whatsapp_limits(db):
    """Botões de até 20 caracteres, descrição de até 72, no máximo 10 opções por tela: assim o WhatsApp entra sem refazer a conversa."""
    from app.bot.types import MAX_BUTTON_TEXT, MAX_DESCRIPTION, MAX_OPTIONS
    for screen in walk_flow(Chat(db)):
        for reply in screen:
            options = [b for row in reply.buttons for b in row]
            assert len(options) <= MAX_OPTIONS, [b.text for b in options]
            for b in options:
                assert len(b.text) <= MAX_BUTTON_TEXT, (len(b.text), b.text)
                assert len(b.description or "") <= MAX_DESCRIPTION


def test_long_service_names_get_a_short_title_and_a_full_description(db):
    db.add(Service(name="Alongamento de unhas em fibra de vidro com decoração", price_cents=18000, duration_minutes=120))
    db.flush()
    c = Chat(db)
    c.send("/start"); c.press("Agendar")
    b = next(b for b in c.buttons() if b.data.startswith("svc:") and b.text.startswith("Alongamento"))
    assert len(b.text) <= 20 and b.text.endswith("…")
    assert "Alongamento de unhas em fibra" in b.description and len(b.description) <= 72


def test_many_services_and_days_are_capped(db):
    db.add_all(Service(name=f"Serviço {i:02d}", price_cents=1000, duration_minutes=30) for i in range(15))
    db.flush()
    c = Chat(db)
    c.send("/start"); c.press("Agendar")
    assert len([b for b in c.buttons() if b.data.startswith("svc:")]) == engine.MAX_SERVICES
    c.press("Serviço 00")
    assert len([b for b in c.buttons() if b.data.startswith("day:")]) <= engine.MAX_DAYS


def test_times_are_paged_with_a_more_button(db, monkeypatch):
    monkeypatch.setattr(engine, "RATE_PER_MINUTE", 1000)   # este teste navega muito; o limite é testado à parte
    c = Chat(db)
    c.send("/start"); c.press("Agendar"); c.press("Manicure")
    c.send(data=next(b.data for b in c.buttons() if b.data.startswith("day:") and not b.text.startswith("Hoje")))
    first = [b.text for b in c.buttons() if b.data.startswith("time:")]
    assert len(first) == engine.TIMES_PER_PAGE and any(b.data == "more:1" for b in c.buttons())
    c.press("Mais horários")
    second = [b.text for b in c.buttons() if b.data.startswith("time:")]
    assert second and set(first).isdisjoint(second)                          # outra página, outros horários
    # chega ao fim e volta ao começo (circular)
    for _ in range(10):
        c.press("Mais horários")
    assert c.conv().state == "choose_time"
    c.press(":")
    assert "Confira" in c.text() or c.last[0].ask_contact                    # um horário da página foi aceito


def test_stale_or_forged_more_button_is_refused(db):
    c = Chat(db)
    assert texts.EXPIRED in c.send(data="more:1")[0].text
    c.send("/start"); c.press("Agendar"); c.press("Manicure")
    assert texts.EXPIRED in c.send(data="more:1")[0].text                    # ainda no passo de escolher o dia
    assert texts.EXPIRED in c.send(data="more:abc")[0].text


def test_the_owner_is_notified_in_the_background_without_making_the_client_wait(db, monkeypatch):
    import threading
    monkeypatch.undo()                                                       # usa o run_in_background de verdade
    from app.bot import engine as eng
    started, release = threading.Event(), threading.Event()
    def slow_notify(appointment_id, via="bot"):
        started.set(); release.wait(5)                                       # o aviso "demora" até liberarmos
    monkeypatch.setattr(owner_notify, "notify_owner_booking", slow_notify)
    c = Chat(db)
    book_until_confirm(c); c.send("Maria Souza")
    c.press("Confirmar")                                                     # volta mesmo com o aviso travado
    assert "✅ Agendado!" in c.text() and appointments(db)
    assert started.wait(2)                                                   # o aviso foi disparado...
    release.set()                                                            # ...e termina depois, sem bloquear ninguém


def test_a_failing_background_task_never_breaks_the_client(db, caplog, monkeypatch):
    monkeypatch.undo()
    import logging
    def boom(*a): raise RuntimeError("telegram fora do ar")
    t = engine.run_in_background(boom)
    t.join(2)
    assert not t.is_alive()


# ---------------------------------------------------------------- telefone digitado (modo de teste)
@pytest.fixture
def typed_ok(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "bot_allow_typed_phone", True)


def to_phone_step(c):
    c.send("/start"); c.press("Agendar"); c.press("Manicure"); c.press(""); c.press(":")
    assert c.last[0].ask_contact


def test_the_phone_prompt_explains_where_the_button_is():
    assert "Compartilhar meu número" in texts.ASK_PHONE and "ícone de teclado" in texts.ASK_PHONE and "celular" in texts.ASK_PHONE


def test_typed_phone_is_refused_by_default_with_a_helpful_and_different_answer(db, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "bot_allow_typed_phone", False)   # fixa o valor: o .env de quem testa pode ter o modo de teste ligado
    c = Chat(db)
    to_phone_step(c)
    first = c.last[0].text
    r = c.send("11 97777-6666")
    assert r[0].text != first and r[0].text == texts.PHONE_BUTTON_ONLY and r[0].ask_contact     # não repete a mesma resposta
    assert c.conv().phone is None and c.conv().client_id is None


def test_typed_phone_in_test_mode_lets_the_person_book(db, typed_ok):
    c = Chat(db)
    to_phone_step(c)
    c.send("(11) 97777-6666")
    assert c.text() == texts.ASK_NAME and c.conv().phone == "5511977776666" and c.conv().phone_verified is False
    c.send("Maria Teste")
    c.press("Confirmar")
    assert "✅ Agendado!" in c.text()
    appt = appointments(db)[0]
    assert appt.client.name == "Maria Teste" and appt.source == "telegram"


def test_typed_phone_sees_and_cancels_only_what_this_conversation_booked(db, typed_ok):
    c = Chat(db)
    to_phone_step(c)
    c.send("11 97777-6666"); c.send("Maria Teste"); c.press("Confirmar")
    appt = appointments(db)[0]
    assert appt.conversation_id == c.conv().id                                   # o agendamento guarda quem o criou
    c.press("Meus agendamentos")
    assert "Seus próximos agendamentos" in c.text() and "Manicure" in c.text()   # ela VÊ o que marcou
    c.press("Cancelar 1"); c.press("Sim, cancelar")
    assert c.text() == texts.CANCELLED and db.get(Appointment, appt.id).status == "cancelled"


def test_a_typed_number_never_exposes_what_the_real_owner_books_later(db, typed_ok):
    """O ataque que o desenho evita: A digita um número livre ANTES da dona; depois a dona (confirmada) agenda."""
    attacker = Chat(db, "6001")
    to_phone_step(attacker)
    attacker.send("(11) 97777-6666"); attacker.send("Impostora")                  # cadastra o número da futura vítima
    assert attacker.conv().phone_verified is False
    victim = Chat(db, "6002")
    victim.send("/start")
    victim.send(phone="5511977776666")                                            # a dona chega pelo contato confirmado
    victim.press("Agendar"); victim.press("Pedicure"); victim.press(""); victim.press(":")
    victim.press("Confirmar")
    hers = [a for a in appointments(db) if a.conversation_id == victim.conv().id]
    assert len(hers) == 1                                                         # a vítima agendou
    # A impostora está ligada ao MESMO cadastro de cliente, mas não enxerga nem cancela o agendamento da dona.
    assert attacker.conv().client_id == victim.conv().client_id
    assert texts.NOTHING_BOOKED_UNVERIFIED in attacker.send(data="mine")[0].text
    for data in (f"cancel:{hers[0].id}", f"cancel_yes:{hers[0].id}"):
        assert texts.CANNOT_CANCEL in attacker.send(data=data)[0].text
    db.refresh(hers[0])
    assert hers[0].status == "confirmed"
    victim.press("Meus agendamentos")
    assert "Seus próximos agendamentos" in victim.text() and "Pedicure" in victim.text()   # e a dona vê o dela normalmente


def test_unverified_with_nothing_booked_here_is_invited_to_share_the_contact(db, typed_ok):
    c = Chat(db)
    to_phone_step(c)
    c.send("11 97777-6666"); c.send("Maria Teste")
    r = c.send(data="mine")
    assert r[0].text == texts.NOTHING_BOOKED_UNVERIFIED and r[0].ask_contact


def test_appointments_made_in_the_panel_are_not_visible_to_unverified_numbers(db, typed_ok):
    c = Chat(db)
    to_phone_step(c)
    c.send("11 97777-6666"); c.send("Maria Teste")
    from app.services import appointments as svc
    service = db.scalar(select(Service).where(Service.name == "Pedicure"))
    appt, _ = svc.create_appointment(db, admin=None, client_id=c.conv().client_id, client_phone=None, client_name=None, service_id=service.id,
                                     starts_at=datetime.now(timezone.utc) + timedelta(days=3), notes=None, status="confirmed", source="admin", strict=False)
    assert appt.conversation_id is None
    assert texts.NOTHING_BOOKED_UNVERIFIED in c.send(data="mine")[0].text


def test_sharing_the_contact_later_unlocks_viewing_and_cancelling(db, typed_ok):
    c = Chat(db)
    to_phone_step(c)
    c.send("11 97777-6666"); c.send("Maria Teste"); c.press("Confirmar")
    c.send(phone="5511977776666")                                                                # agora confirmou pelo botão
    assert c.conv().phone_verified is True
    c.press("Meus agendamentos")
    assert "Seus próximos agendamentos" in c.text()                                              # confirmado: vê todos os da cliente


def test_typed_phone_of_an_existing_client_is_refused(db, typed_ok):
    victim = Client(name="Cliente Antiga", phone="5511977776666")
    db.add(victim)
    db.flush()
    c = Chat(db)
    to_phone_step(c)
    r = c.send("(11) 97777-6666")
    assert r[0].text == texts.PHONE_ALREADY_REGISTERED and r[0].ask_contact
    assert c.conv().phone is None and c.conv().client_id is None


def test_a_number_registered_in_the_middle_of_the_flow_is_not_linked_to_an_unverified_person(db, typed_ok):
    c = Chat(db)
    to_phone_step(c)
    c.send("11 97777-6666")                                                                      # digitou um número livre
    db.add(Client(name="Chegou Depois", phone="5511977776666"))                                  # ...e alguém o cadastrou agora
    db.flush()
    r = c.send("Impostora")
    assert r[0].text == texts.PHONE_ALREADY_REGISTERED and c.conv().client_id is None and c.conv().state == "ask_phone"


def test_invalid_typed_phones_are_refused(db, typed_ok):
    c = Chat(db)
    to_phone_step(c)
    for bad in ["123", "abc", "+1 415 555 2671", "99999999999999999999"]:
        assert c.send(bad)[0].text == texts.BAD_PHONE, bad
    assert c.conv().phone is None


def test_typed_phone_mode_is_off_by_default():
    from app.core.config import Settings
    assert Settings.model_fields["bot_allow_typed_phone"].default is False


def test_whatsapp_numbers_are_always_verified(db):
    c = Chat(db, "5511977776666", channel="whatsapp")
    c.send("oi", phone=PHONE)
    assert c.conv().phone_verified is True


# ---------------------------------------------------------------- horários de atendimento
def set_hours(db, rows):
    db.execute(delete(BusinessHours))
    from datetime import time
    for day, start, end in rows:
        db.add(BusinessHours(weekday=day, start_time=time(*start), end_time=time(*end)))
    db.flush()


def test_menu_has_four_clear_options_with_the_right_names(db):
    c = Chat(db)
    c.send("/start")
    assert [(b.data, b.text) for b in c.buttons()] == [("book", "💅 Agendar horário"), ("hours", "🕒 Horários de atend."), ("mine", "🗓 Meus agendamentos"), ("human", "🙋 Falar com o dono")]


def test_the_hours_screen_shows_the_studio_schedule_and_the_next_free_days(db):
    set_hours(db, [(d, (9, 0), (12, 0)) for d in range(5)] + [(d, (14, 0), (19, 0)) for d in range(5)] + [(5, (9, 0), (16, 0))])
    c = Chat(db)
    c.send("/start"); c.press("Horários de atend.")
    t = c.text()
    assert "Horários de atendimento" in t
    assert "Seg a sex: 09:00–12:00 e 14:00–19:00" in t and "Sábado: 09:00–16:00" in t and "Domingo: fechado" in t
    assert "Próximos dias com horário livre:" in t
    assert [b.data for b in c.buttons()] == ["book", "menu"]                       # dá para agendar direto dali
    assert c.conv().state == "idle"


def test_free_days_skip_closed_days_and_only_list_days_that_really_have_a_slot(db):
    set_hours(db, [(5, (9, 0), (12, 0))])                                           # só aos sábados
    c = Chat(db)
    c.send("/start"); c.press("Horários de atend.")
    line = next(l for l in c.text().splitlines() if l.startswith("Próximos dias"))
    assert "sáb" in line and not any(d in line for d in ("seg", "ter", "qua", "qui", "sex", "dom"))


def test_the_hours_screen_says_so_when_nothing_is_free(db):
    set_hours(db, [(d, (9, 0), (12, 0)) for d in range(7)])
    db.execute(update(Service).values(is_active=False))                              # sem serviço ativo, não há como agendar
    c = Chat(db)
    c.send("/start"); c.press("Horários de atend.")
    assert "No momento não há horários livres" in c.text() and "Segunda a domingo" not in c.text()


def test_the_hours_screen_without_a_schedule_registered(db):
    db.execute(delete(BusinessHours))
    c = Chat(db)
    c.send("/start"); c.press("Horários de atend.")
    assert "ainda não foram cadastrados" in c.text() and [b.data for b in c.buttons()] == ["menu"]


def test_busy_times_are_not_counted_as_free_days(db):
    set_hours(db, [(d, (9, 0), (10, 0)) for d in range(7)])                          # uma única vaga de 45 min por dia
    c = Chat(db)
    c.send("/start"); c.press("Horários de atend.")
    first = c.text()
    service = db.scalar(select(Service).where(Service.name == "Manicure"))
    other = Client(name="Outra", phone="5511900001111")
    db.add(other)
    db.flush()
    from app.services.availability import slots_for_day
    today = datetime.now(timezone.utc).astimezone(__import__("app.services.availability", fromlist=["TZ"]).TZ).date()
    for offset in range(0, 3):
        for slot in slots_for_day(db, today + timedelta(days=offset), service)[:2]:
            appt_service.create_appointment(db, admin=None, client_id=other.id, client_phone=None, client_name=None, service_id=service.id,
                                            starts_at=slot, notes=None, status="confirmed", source="admin", strict=False)
    c.send("/start"); c.press("Horários de atend.")
    assert c.text() != first                                                         # os dias lotados saíram da lista


@pytest.mark.parametrize("word", ["horários", "Horarios", "/horarios", "agenda", "expediente", "vagas"])
def test_typing_the_word_also_opens_the_hours_screen(db, word):
    set_hours(db, [(0, (9, 0), (18, 0))])
    c = Chat(db)
    c.send("/start")
    r = c.send(word)
    assert "Horários de atendimento" in r[0].text


def test_the_word_agenda_does_not_hijack_a_name_being_typed(db, typed_ok):
    """Se a pessoa está digitando o nome, "Agenda" é um nome, não um pedido de horários."""
    c = Chat(db)
    to_phone_step(c)
    c.send("11 97777-6666")
    assert c.conv().state == "ask_name"
    c.send("agenda")
    assert c.conv().state != "idle" and "Horários de atendimento" not in c.text()


def test_the_hours_screen_never_reveals_other_clients_or_block_reasons(db):
    set_hours(db, [(d, (9, 0), (18, 0)) for d in range(7)])
    other = Client(name="Cliente Secreta", phone="5511911112222")
    db.add(other)
    db.flush()
    c = Chat(db)
    c.send("/start"); c.press("Horários de atend.")
    assert "Secreta" not in c.text() and "5511911112222" not in c.text()


def test_the_new_button_labels_fit_the_whatsapp_limit(db):
    from app.bot.types import MAX_BUTTON_TEXT
    set_hours(db, [(0, (9, 0), (18, 0))])
    c = Chat(db)
    for step in (lambda: c.send("/start"), lambda: c.press("Horários de atend.")):
        step()
        assert all(len(b.text) <= MAX_BUTTON_TEXT for b in c.buttons()), [b.text for b in c.buttons()]


def test_hours_summary_groups_days_and_handles_edge_cases():
    sa = texts.hours_summary
    assert sa([(d, "08:00", "20:00") for d in range(7)]) == "Seg a dom: 08:00–20:00"
    assert sa([(0, "09:00", "18:00"), (1, "09:00", "18:00"), (3, "10:00", "16:00")]).splitlines() == [
        "Segunda e terça: 09:00–18:00", "Quarta: fechado", "Quinta: 10:00–16:00", "Sex a dom: fechado"]
    assert sa([(2, "14:00", "18:00"), (2, "09:00", "12:00")]).splitlines() == [                                    # intervalos fora de ordem
        "Segunda e terça: fechado", "Quarta: 09:00–12:00 e 14:00–18:00", "Qui a dom: fechado"]
    assert sa([]).splitlines() == ["Seg a dom: fechado"]
