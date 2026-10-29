"""Quem cancelou e o aviso ao dono. Telegram e e-mail são simulados."""
import logging
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select, update

from app.bot import engine
from app.bot.types import Incoming
from app.core.config import settings
from app.core.security import create_access_token, password_version
from app.models import AdminUser, Appointment, AuditLog, BusinessHours, Client, Conversation, Service
from app.services import appointments as svc
from app.services import mailer, owner_notify, telegram

URL = "/api/v1/appointments"
UTC = timezone.utc


@pytest.fixture
def outbox(monkeypatch, db):
    """Captura e-mails e mensagens de Telegram; faz o aviso usar a sessão do teste."""
    box = SimpleNamespace(mails=[], telegram=[])
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body: box.mails.append((to, subject, body)))
    monkeypatch.setattr(telegram, "send_message", lambda chat, text, buttons=None: box.telegram.append((chat, text)) or {"ok": True})
    monkeypatch.setattr(settings, "telegram_bot_token", "1:T")
    monkeypatch.setattr(settings, "telegram_chat_id", "42")
    monkeypatch.setattr(owner_notify, "SessionLocal", lambda: nullcontext(db))
    return box


def make_appt(db, *, name="Maria Souza", phone="5511977776666", source="telegram"):
    client = Client(name=name, phone=phone)
    service = db.scalar(select(Service).where(Service.name == "Manicure")) or Service(name="Manicure", price_cents=4500, duration_minutes=45)
    db.add_all([client, service])
    db.flush()
    start = datetime.now(UTC) + timedelta(days=3)
    appt = Appointment(client_id=client.id, service_id=service.id, starts_at=start, ends_at=start + timedelta(minutes=45),
                       status="confirmed", price_cents=4500, source=source)
    db.add(appt)
    db.flush()
    return appt


# ---------------- registro de quem cancelou ----------------
def test_cancelling_in_the_panel_records_the_users_name_and_time(db, admin):
    appt = make_appt(db)
    svc.change_status(db, admin, appt.id, "cancel")
    assert appt.cancelled_by == "Dono (painel)" and appt.cancelled_at is not None
    log = db.scalars(select(AuditLog).where(AuditLog.entity_id == appt.id, AuditLog.action == "cancel")).one()
    assert log.changes["by"] == "Dono (painel)" and log.admin_user_id == admin.id


def test_a_custom_author_is_recorded_for_the_bot(db):
    appt = make_appt(db)
    svc.change_status(db, None, appt.id, "cancel", by="Maria Souza (cliente, pelo Telegram)")
    assert appt.cancelled_by == "Maria Souza (cliente, pelo Telegram)"
    assert db.scalars(select(AuditLog).where(AuditLog.entity_id == appt.id, AuditLog.action == "cancel")).one().changes["by"] == appt.cancelled_by


def test_other_actions_do_not_fill_the_cancellation_fields(db, admin):
    appt = make_appt(db)
    svc.change_status(db, admin, appt.id, "confirm") if appt.status == "pending" else None
    assert appt.cancelled_by is None and appt.cancelled_at is None


def test_the_api_exposes_who_cancelled(client, auth, db, admin):
    appt = make_appt(db)
    r = client.post(f"{URL}/{appt.id}/cancel", headers=auth)
    assert r.status_code == 200
    body = client.get(f"{URL}/{appt.id}", headers=auth).json()
    assert body["cancelled_by"] == "Dono (painel)" and body["cancelled_at"]
    assert client.get(URL, params={"status": "cancelled"}, headers=auth).json()[0]["cancelled_by"]


# ---------------- aviso ao dono ----------------
def test_the_notice_says_who_cancelled_which_appointment_and_when(db, outbox, admin):
    appt = make_appt(db)
    svc.change_status(db, None, appt.id, "cancel", by="Maria Souza (cliente, pelo Telegram)")
    owner_notify.notify_owner_cancellation(appt.id)
    texts_sent = [t for _, _, t in outbox.mails] + [t for _, t in outbox.telegram]
    assert texts_sent and all("Agendamento cancelado" in t for t in texts_sent)
    for t in texts_sent:
        assert "Maria Souza · (11) 97777-6666" in t and "Manicure" in t
        assert "Cancelado por: Maria Souza (cliente, pelo Telegram)" in t
        assert "Horário:" in t and "Quando:" in t
    assert any(to == admin.email for to, _, _ in outbox.mails)
    assert outbox.telegram and outbox.telegram[0][0] == "42"


def test_no_notice_for_appointments_that_are_not_cancelled_or_do_not_exist(db, outbox, admin):
    owner_notify.notify_owner_cancellation(make_appt(db).id)
    owner_notify.notify_owner_cancellation(99999999)
    assert outbox.mails == [] and outbox.telegram == []


def test_the_notice_works_by_email_alone_when_telegram_is_off(db, outbox, admin, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    appt = make_appt(db)
    svc.change_status(db, None, appt.id, "cancel", by="cliente")
    owner_notify.notify_owner_cancellation(appt.id)
    assert outbox.mails and outbox.telegram == []


def test_a_failure_in_the_notice_never_raises(db, outbox, admin, monkeypatch, caplog):
    appt = make_appt(db)
    svc.change_status(db, None, appt.id, "cancel", by="cliente")
    monkeypatch.setattr(mailer, "send_mail", lambda *a: (_ for _ in ()).throw(RuntimeError("smtp caiu")))
    with caplog.at_level(logging.ERROR):
        owner_notify.notify_owner_cancellation(appt.id)
    assert "falha ao avisar o dono do cancelamento" in caplog.text


# ---------------- quem dispara o aviso ----------------
@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(owner_notify, "notify_owner_cancellation", lambda aid: seen.append(aid))
    from app.services import client_notify
    monkeypatch.setattr(client_notify, "notify_cancelled", lambda aid: None)
    return seen


def staff_headers(db, name="Bia Atendente"):
    now = datetime.now(UTC)
    user = AdminUser(email="bia@gmail.com", name=name, password_hash=None, email_verified_at=now, approved_at=now, is_owner=False)
    db.add(user)
    db.flush()
    return user, {"Authorization": f"Bearer {create_access_token(user.id, password_version(user))}"}


def test_the_owner_cancelling_does_not_notify_the_owner(client, auth, db, admin, calls):
    appt = make_appt(db)
    assert client.post(f"{URL}/{appt.id}/cancel", headers=auth).status_code == 200
    assert calls == []                                                            # o dono sabe o que ele mesmo cancelou


def test_a_staff_member_cancelling_notifies_the_owner_with_their_name(client, db, admin, calls):
    _, headers = staff_headers(db)
    appt = make_appt(db)
    assert client.post(f"{URL}/{appt.id}/cancel", headers=headers).status_code == 200
    assert calls == [appt.id]
    db.refresh(appt)
    assert appt.cancelled_by == "Bia Atendente (painel)"


def test_a_failed_cancellation_does_not_notify(client, db, admin, calls):
    _, headers = staff_headers(db)
    appt = make_appt(db)
    client.post(f"{URL}/{appt.id}/cancel", headers=headers)
    calls.clear()
    assert client.post(f"{URL}/{appt.id}/cancel", headers=headers).status_code == 409       # já cancelado
    assert calls == []


# ---------------- cancelamento pela cliente no bot ----------------
@pytest.fixture
def studio(db, monkeypatch):
    db.execute(update(Service).values(is_active=False))
    db.execute(delete(BusinessHours))
    db.add(Service(name="Manicure", price_cents=4500, duration_minutes=45))
    db.flush()
    notified = []
    monkeypatch.setattr(owner_notify, "notify_owner_cancellation", lambda aid: notified.append(aid))
    monkeypatch.setattr(engine, "run_in_background", lambda fn, *a: fn(*a))
    return notified


def test_a_client_cancelling_in_the_bot_records_who_and_notifies_the_owner(db, studio):
    appt = make_appt(db)
    conv = Conversation(channel="telegram", external_id="900", client_id=appt.client_id, phone="5511977776666", phone_verified=True, state="idle", context={})
    db.add(conv)
    db.flush()

    def send(data):
        return engine.handle(db, Incoming(channel="telegram", external_id="900", message_id=f"m{data}{datetime.now().timestamp()}", data=data))

    send("mine")
    r = send(f"cancel:{appt.id}")
    assert "Cancelar Manicure" in r[0].text
    send(f"cancel_yes:{appt.id}")
    db.refresh(appt)
    assert appt.status == "cancelled" and appt.cancelled_by == "Maria Souza (cliente, pelo Telegram)"
    assert studio == [appt.id]                                                    # o dono foi avisado


def test_a_refused_cancellation_in_the_bot_does_not_notify(db, studio):
    appt = make_appt(db)
    stranger = Conversation(channel="telegram", external_id="901", phone_verified=False, state="idle", context={})
    db.add(stranger)
    db.flush()
    engine.handle(db, Incoming(channel="telegram", external_id="901", message_id="x1", data=f"cancel_yes:{appt.id}"))
    db.refresh(appt)
    assert appt.status == "confirmed" and studio == []


# ---------------- dashboard ----------------
def test_dashboard_scheduled_total_excludes_cancelled(client, auth, db):
    from datetime import date
    a = make_appt(db)
    svc.change_status(db, None, a.id, "cancel", by="cliente")
    b = make_appt(db, name="Outra", phone="5511900001111")
    local = a.starts_at.astimezone().date()
    s = client.get("/api/v1/dashboard/summary", params={"date_from": local.isoformat(), "date_to": local.isoformat()}, headers=auth).json()
    assert s["by_status"]["cancelled"] >= 1
    assert s["total_appointments"] == sum(s["by_status"].values())               # o total antigo continua somando tudo
    assert s["scheduled_appointments"] == s["total_appointments"] - s["by_status"]["cancelled"]
