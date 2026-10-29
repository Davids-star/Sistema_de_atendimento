"""Avisos à cliente (remarcação/cancelamento pelo painel) e lembrete 4h antes. O Telegram é simulado."""
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.bot import reminders, texts
from app.bot.channels import telegram
from app.bot.types import Reply
from app.core.config import Settings, settings
from app.models import Appointment, Client, Conversation, Service
from app.services import client_notify

UTC = timezone.utc
NOW = datetime(2030, 1, 7, 13, 0, tzinfo=UTC)         # 10:00 em São Paulo (fora do horário de silêncio)


@pytest.fixture
def sent(monkeypatch):
    """Telegram simulado: registra (chat_id, texto, botões). `sent.ok` controla se o envio "funciona"."""
    box = SimpleNamespace(items=[], ok=True)
    def fake(chat_id, reply: Reply):
        box.items.append((chat_id, reply.text, [b.data for row in reply.buttons for b in row]))
        return box.ok
    monkeypatch.setattr(telegram, "send_reply", fake)
    monkeypatch.setattr(settings, "customer_bot_token", "999:TOKEN")
    monkeypatch.setattr(settings, "bot_allow_typed_phone", False)
    return box


def make_client(db, phone="5511977776666", *, chat="777", verified=True, channel="telegram"):
    client = Client(name="Maria", phone=phone)
    db.add(client)
    db.flush()
    if chat:
        db.add(Conversation(channel=channel, external_id=chat, client_id=client.id, phone=phone, phone_verified=verified, state="idle", context={}))
        db.flush()
    return client


def make_appt(db, client, start, *, status="confirmed", **extra):
    service = db.scalar(select(Service).where(Service.name == "Manicure")) or Service(name="Manicure", price_cents=4500, duration_minutes=45)
    db.add(service)
    db.flush()
    appt = Appointment(client_id=client.id, service_id=service.id, starts_at=start, ends_at=start + timedelta(minutes=45),
                       status=status, price_cents=4500, source="admin", **extra)
    db.add(appt)
    db.flush()
    return appt


# ===================================================================== avisos à cliente
def test_only_verified_telegram_conversations_are_targets(db, sent):
    c = make_client(db, chat="1", verified=True)
    db.add_all([Conversation(channel="telegram", external_id="2", client_id=c.id, phone_verified=False, state="idle", context={}),
                Conversation(channel="whatsapp", external_id="3", client_id=c.id, phone_verified=True, state="idle", context={})])
    db.flush()
    assert [t.external_id for t in client_notify.targets(db, c.id)] == ["1"]


def test_unverified_numbers_are_targets_only_in_test_mode(db, sent, monkeypatch):
    c = make_client(db, chat="2", verified=False)
    assert client_notify.targets(db, c.id) == []
    monkeypatch.setattr(settings, "bot_allow_typed_phone", True)
    assert [t.external_id for t in client_notify.targets(db, c.id)] == ["2"]


def test_send_reaches_every_conversation_and_counts_deliveries(db, sent):
    c = make_client(db, chat="1")
    db.add(Conversation(channel="telegram", external_id="2", client_id=c.id, phone_verified=True, state="idle", context={}))
    db.flush()
    assert client_notify.send(db, c.id, "oi") == 2 and {i[0] for i in sent.items} == {"1", "2"}
    sent.ok = False
    assert client_notify.send(db, c.id, "oi") == 0


def test_nothing_is_sent_to_a_client_who_never_talked_to_the_bot(db, sent):
    c = make_client(db, chat=None)
    assert client_notify.send(db, c.id, "oi") == 0 and sent.items == []


def test_reschedule_notice_shows_old_and_new_times_in_local_time(db, sent):
    c = make_client(db)
    appt = make_appt(db, c, datetime(2030, 1, 9, 17, 0, tzinfo=UTC))           # nova: qua 14:00 local
    old = datetime(2030, 1, 7, 15, 0, tzinfo=UTC)                              # antiga: seg 12:00 local
    assert client_notify._rescheduled(db, appt.id, old) == 1
    chat, text, _ = sent.items[0]
    assert chat == "777" and "De: seg, 07/01 às 12:00" in text and "Para: qua, 09/01 às 14:00" in text and "Manicure" in text


def test_no_reschedule_notice_if_the_time_did_not_change_or_the_appointment_is_not_active(db, sent):
    c = make_client(db)
    start = datetime(2030, 1, 9, 17, 0, tzinfo=UTC)
    assert client_notify._rescheduled(db, make_appt(db, c, start).id, start) == 0
    assert client_notify._rescheduled(db, make_appt(db, c, start + timedelta(hours=3), status="cancelled").id, start) == 0
    assert client_notify._rescheduled(db, 99999999, start) == 0
    assert sent.items == []


def test_cancellation_notice_offers_to_book_again(db, sent):
    c = make_client(db)
    appt = make_appt(db, c, datetime(2030, 1, 9, 17, 0, tzinfo=UTC), status="cancelled")
    assert client_notify._cancelled(db, appt.id) == 1
    _, text, buttons = sent.items[0]
    assert "Precisamos cancelar" in text and "qua, 09/01 às 14:00" in text and buttons == ["book"]
    assert client_notify._cancelled(db, make_appt(db, c, datetime(2030, 1, 9, 19, 0, tzinfo=UTC), status="confirmed").id) == 0   # só se foi cancelado


def test_a_failure_in_the_background_task_never_raises(monkeypatch, caplog):
    monkeypatch.setattr(client_notify, "SessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("banco fora do ar")))
    client_notify.notify_cancelled(1)
    client_notify.notify_rescheduled(1, "2030-01-07T15:00:00+00:00")
    assert "falha ao avisar a cliente" in caplog.text


# ---------- ganchos nas rotas do painel ----------
@pytest.fixture
def hooks(monkeypatch):
    calls = []
    monkeypatch.setattr(client_notify, "notify_rescheduled", lambda aid, old: calls.append(("rescheduled", aid, old)))
    monkeypatch.setattr(client_notify, "notify_cancelled", lambda aid: calls.append(("cancelled", aid)))
    return calls


def setup_panel(client, auth, db):
    from sqlalchemy import delete, update
    from app.models import BusinessHours
    db.execute(update(Service).values(is_active=False)); db.execute(delete(BusinessHours))
    sid = client.post("/api/v1/services", headers=auth, json={"name": "Corte", "price_cents": 4000, "duration_minutes": 30}).json()["id"]
    cid = client.post("/api/v1/clients", headers=auth, json={"name": "Ana", "phone": "11999990000"}).json()["id"]
    start = datetime.now(UTC) + timedelta(days=10)
    start = start.replace(minute=0, second=0, microsecond=0)
    r = client.post("/api/v1/appointments", headers=auth, json={"client_id": cid, "service_id": sid, "starts_at": start.isoformat()})
    return r.json()["id"], start


def test_rescheduling_in_the_panel_notifies_with_the_old_time(client, auth, db, hooks):
    aid, start = setup_panel(client, auth, db)
    new = start + timedelta(hours=2)
    assert client.patch(f"/api/v1/appointments/{aid}", headers=auth, json={"starts_at": new.isoformat()}).status_code == 200
    assert len(hooks) == 1 and hooks[0][:2] == ("rescheduled", aid)
    assert datetime.fromisoformat(hooks[0][2]) == start                                # o mesmo instante (o texto pode vir com outro fuso)


def test_editing_only_the_notes_does_not_notify(client, auth, db, hooks):
    aid, _ = setup_panel(client, auth, db)
    client.patch(f"/api/v1/appointments/{aid}", headers=auth, json={"notes": "trazer foto"})
    assert hooks == []


def test_a_rejected_reschedule_does_not_notify(client, auth, db, hooks):
    aid, start = setup_panel(client, auth, db)
    other, _ = setup_panel(client, auth, db) if False else (None, None)
    r = client.patch(f"/api/v1/appointments/{aid}", headers=auth, json={"starts_at": "2020-01-01T10:00:00Z"})
    assert r.status_code == 422 and hooks == []                                       # passado: recusado


def test_cancelling_in_the_panel_notifies_but_other_actions_do_not(client, auth, db, hooks):
    aid, _ = setup_panel(client, auth, db)
    assert client.post(f"/api/v1/appointments/{aid}/cancel", headers=auth).status_code == 200
    assert hooks == [("cancelled", aid)]
    hooks.clear()
    assert client.post(f"/api/v1/appointments/{aid}/cancel", headers=auth).status_code == 409   # já cancelado
    assert hooks == []


def test_confirming_does_not_notify(client, auth, db, hooks):
    aid, _ = setup_panel(client, auth, db)
    client.post(f"/api/v1/appointments/{aid}/confirm", headers=auth)
    assert hooks == []


def test_rescheduling_resets_the_reminder(client, auth, db, hooks):
    aid, start = setup_panel(client, auth, db)
    appt = db.get(Appointment, aid)
    appt.reminder_sent_at, appt.reminder_attempts = NOW, 3
    db.flush()
    client.patch(f"/api/v1/appointments/{aid}", headers=auth, json={"starts_at": (start + timedelta(hours=1)).isoformat()})
    db.refresh(appt)
    assert appt.reminder_sent_at is None and appt.reminder_attempts == 0


def test_changing_only_the_service_keeps_the_reminder_state(client, auth, db, hooks):
    aid, _ = setup_panel(client, auth, db)
    appt = db.get(Appointment, aid)
    appt.reminder_sent_at = NOW
    db.flush()
    client.patch(f"/api/v1/appointments/{aid}", headers=auth, json={"notes": "x"})
    db.refresh(appt)
    assert appt.reminder_sent_at == NOW


# ===================================================================== lembrete
def test_defaults_match_the_request():
    f = Settings.model_fields
    assert (f["reminder_hours_before"].default, f["arrive_early_minutes"].default) == (4, 20)
    assert (f["reminder_quiet_start_hour"].default, f["reminder_quiet_end_hour"].default) == (21, 7)


def test_reminder_text_says_to_arrive_20_minutes_early_with_the_exact_time():
    text = texts.reminder("Manicure", datetime(2030, 1, 7, 17, 0, tzinfo=UTC))      # 14:00 local
    assert "Manicure" in text and "seg, 07/01 às 14:00" in text
    assert "chegue 20 minutos antes" in text and "por volta das 13:40" in text


def test_the_early_arrival_minutes_are_configurable(monkeypatch):
    monkeypatch.setattr(settings, "arrive_early_minutes", 30)
    text = texts.reminder("Manicure", datetime(2030, 1, 7, 17, 0, tzinfo=UTC))
    assert "chegue 30 minutos antes" in text and "13:30" in text


def test_only_confirmed_appointments_inside_the_4_hour_window_are_due(db, sent):
    c = make_client(db)
    # Horários espaçados: o banco recusa agendamentos ativos que se sobrepõem.
    past = make_appt(db, c, NOW - timedelta(minutes=1))                                # já começou
    exhausted = make_appt(db, c, NOW + timedelta(minutes=45), reminder_attempts=settings.reminder_max_attempts)
    done = make_appt(db, c, NOW + timedelta(minutes=90), reminder_sent_at=NOW)         # já enviado
    pending = make_appt(db, c, NOW + timedelta(minutes=135), status="pending")         # ainda não confirmado
    due = make_appt(db, c, NOW + timedelta(hours=3))
    edge = make_appt(db, c, NOW + timedelta(hours=4))                                  # exatamente 4h: já entra
    far = make_appt(db, c, NOW + timedelta(hours=4, minutes=1, seconds=1) + timedelta(minutes=45))   # fora da janela
    cancelled = make_appt(db, c, NOW + timedelta(hours=2), status="cancelled")
    ids = {a.id for a in reminders.due_appointments(db, NOW)}
    assert {due.id, edge.id} <= ids
    assert not ({far.id, past.id, pending.id, cancelled.id, done.id, exhausted.id} & ids)


@pytest.mark.parametrize("utc_hour,utc_minute,quiet", [
    (23, 59, False),   # 20:59 local
    (0, 0, True),      # 21:00 local: começa o silêncio
    (5, 0, True),      # 02:00 local
    (9, 59, True),     # 06:59 local
    (10, 0, False),    # 07:00 local: acabou o silêncio
    (13, 0, False),    # 10:00 local
])
def test_quiet_hours_are_21h_to_7h_local(utc_hour, utc_minute, quiet):
    assert reminders.in_quiet_hours(datetime(2030, 1, 8, utc_hour, utc_minute, tzinfo=UTC)) is quiet


def test_nothing_is_sent_at_night_even_if_due_and_an_early_appointment_is_reminded_at_7h(db, sent):
    c = make_client(db)
    early = make_appt(db, c, datetime(2030, 1, 7, 10, 40, tzinfo=UTC))                 # 07:40 local
    night = datetime(2030, 1, 7, 7, 0, tzinfo=UTC)                                     # 04:00 local: já está a menos de 4h
    assert reminders.send_due(db, night) == {"sent": 0, "failed": 0, "quiet": True, "disabled": False} and sent.items == []
    assert reminders.send_due(db, datetime(2030, 1, 7, 10, 0, tzinfo=UTC))["sent"] == 1    # 07:00 local
    assert "07/01 às 07:40" in sent.items[0][1]


def test_the_reminder_is_sent_once_with_the_right_content(db, sent):
    c = make_client(db)
    appt = make_appt(db, c, NOW + timedelta(hours=3))                                  # 13:00 local
    assert reminders.send_due(db, NOW)["sent"] == 1
    chat, text, buttons = sent.items[0]
    assert chat == "777" and "Manicure" in text and "chegue 20 minutos antes" in text and "por volta das 12:40" in text
    assert buttons == ["mine"]
    db.refresh(appt)
    assert appt.reminder_sent_at == NOW and appt.reminder_attempts == 1
    assert reminders.send_due(db, NOW + timedelta(minutes=5))["sent"] == 0 and len(sent.items) == 1     # não repete


def test_a_failed_delivery_is_retried_until_the_attempt_limit(db, sent, monkeypatch):
    monkeypatch.setattr(settings, "reminder_max_attempts", 3)
    c = make_client(db)
    appt = make_appt(db, c, NOW + timedelta(hours=3))
    sent.ok = False
    for minute in range(3):
        assert reminders.send_due(db, NOW + timedelta(minutes=minute))["failed"] == 1
    db.refresh(appt)
    assert appt.reminder_attempts == 3 and appt.reminder_sent_at is None
    assert reminders.send_due(db, NOW + timedelta(minutes=4)) == {"sent": 0, "failed": 0, "quiet": False, "disabled": False}   # desistiu
    sent.ok = True
    appt.reminder_attempts = 0                                                          # (ex.: remarcação zera o controle)
    db.flush()
    assert reminders.send_due(db, NOW + timedelta(minutes=5))["sent"] == 1


def test_clients_who_never_used_the_bot_are_skipped_without_burning_attempts(db, sent):
    c = make_client(db, chat=None)
    appt = make_appt(db, c, NOW + timedelta(hours=2))
    assert reminders.send_due(db, NOW)["sent"] == 0 and sent.items == []
    db.refresh(appt)
    assert appt.reminder_attempts == 0                                                  # continua elegível se ela falar com o bot depois


def test_without_a_customer_bot_token_the_reminders_are_disabled(db, sent, monkeypatch):
    monkeypatch.setattr(settings, "customer_bot_token", "")
    c = make_client(db)
    appt = make_appt(db, c, NOW + timedelta(hours=2))
    assert reminders.send_due(db, NOW)["disabled"] is True and sent.items == []
    db.refresh(appt)
    assert appt.reminder_attempts == 0


def test_two_programs_cannot_send_the_same_reminder(db, sent, monkeypatch):
    """Se outro processo já reservou o lembrete, este desiste (a reserva é atômica no banco)."""
    c = make_client(db)
    appt = make_appt(db, c, NOW + timedelta(hours=2), reminder_attempts=1)             # o outro programa já reservou
    stale = SimpleNamespace(id=appt.id, client_id=c.id, reminder_attempts=0, starts_at=appt.starts_at,   # nossa visão ficou velha
                            service=SimpleNamespace(name="Manicure"))
    monkeypatch.setattr(reminders, "due_appointments", lambda db_, now: [stale])
    assert reminders.send_due(db, NOW)["sent"] == 0 and sent.items == []


def test_the_reminder_loop_survives_errors_and_stops_on_request(monkeypatch, caplog):
    stop, calls = threading.Event(), []
    def flaky(db, now=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("banco caiu")
        stop.set()
        return {"sent": 1, "failed": 0, "quiet": False, "disabled": False}
    monkeypatch.setattr(reminders, "send_due", flaky)
    monkeypatch.setattr(reminders, "SessionLocal", lambda: __import__("contextlib").nullcontext(None))
    t = threading.Thread(target=reminders.run_loop, kwargs={"interval": 0.01, "stop": stop})
    t.start(); t.join(5)
    assert not t.is_alive() and len(calls) == 2 and "falha no ciclo de lembretes" in caplog.text


def test_the_bot_program_starts_the_reminder_loop():
    import importlib, sys
    sys.path.insert(0, "backend")
    src = open("backend/customer_bot.py", encoding="utf-8").read()
    assert "reminders.run_loop" in src and "daemon=True" in src
