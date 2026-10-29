from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core.security import create_access_token, password_version
from app.models import AdminUser, Appointment, Client, Notification, Service
from app.services import appointments as svc
from app.services import notifications, owner_notify

URL = "/api/v1/notifications"
UTC = timezone.utc


def make_user(db, email, *, owner=False, approved=True, active=True):
    now = datetime.now(UTC)
    u = AdminUser(email=email, name=email.split("@")[0].title(), password_hash=None, is_owner=owner, is_active=active,
                  email_verified_at=now, approved_at=now if approved else None)
    db.add(u)
    db.flush()
    return u


def headers(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, password_version(u))}"}


def make_appt(db, name="Maria Souza", phone="5511977776666"):
    client = Client(name=name, phone=phone)
    service = db.scalar(select(Service).where(Service.name == "Manicure")) or Service(name="Manicure", price_cents=4500, duration_minutes=45)
    db.add_all([client, service])
    db.flush()
    start = datetime.now(UTC) + timedelta(days=3)
    a = Appointment(client_id=client.id, service_id=service.id, starts_at=start, ends_at=start + timedelta(minutes=45), status="confirmed", price_cents=4500, source="admin")
    db.add(a)
    db.flush()
    return a


@pytest.fixture
def team(db, admin):
    """Dono (fixture) + uma atendente + alguém sem acesso liberado + alguém desativado. Isola do banco real."""
    for u in db.scalars(select(AdminUser).where(AdminUser.id != admin.id)):
        u.approved_at = None          # só dentro da transação do teste: ninguém mais do banco real recebe avisos
    staff = make_user(db, "bia@gmail.com")
    pending = make_user(db, "pendente@gmail.com", approved=False)
    off = make_user(db, "off@gmail.com", active=False)
    return admin, staff, pending, off


def mine(db, user, kind=None):
    q = select(Notification).where(Notification.user_id == user.id)
    if kind:
        q = q.where(Notification.kind == kind)
    return db.scalars(q).all()


# ---------------- quem é avisado ----------------
def test_a_cancellation_by_the_client_notifies_everyone_with_panel_access_and_nobody_else(db, team):
    owner, staff, pending, off = team
    appt = make_appt(db)
    svc.change_status(db, None, appt.id, "cancel", by="Maria Souza (cliente, pelo Telegram)")
    assert len(mine(db, owner, "appointment_cancelled")) == 1 and len(mine(db, staff, "appointment_cancelled")) == 1
    assert mine(db, pending) == [] and mine(db, off) == []                    # sem acesso liberado / desativado: nada


def test_whoever_cancelled_is_not_notified_of_their_own_action(db, team):
    owner, staff, *_ = team
    appt = make_appt(db)
    svc.change_status(db, staff, appt.id, "cancel")
    assert mine(db, staff) == [] and len(mine(db, owner, "appointment_cancelled")) == 1


def test_the_notice_says_who_what_and_when_and_opens_the_agenda(db, team):
    owner, *_ = team
    appt = make_appt(db)
    svc.change_status(db, None, appt.id, "cancel", by="Maria Souza (cliente, pelo Telegram)")
    n = mine(db, owner, "appointment_cancelled")[0]
    assert n.title == "Agendamento cancelado" and n.link == "/agendamentos" and n.appointment_id == appt.id
    assert "Maria Souza" in n.body and "Manicure" in n.body and "Cancelado por Maria Souza (cliente, pelo Telegram)" in n.body
    assert n.read_at is None


def test_the_same_event_never_notifies_twice(db, team):
    owner, staff, *_ = team
    appt = make_appt(db)
    svc.change_status(db, None, appt.id, "cancel", by="cliente")
    assert len(mine(db, owner)) == 1 and len(mine(db, staff)) == 1                      # a primeira vez criou um para cada
    assert notifications.appointment_cancelled(db, appt, exclude_user_id=None) == 0      # repetir é inofensivo (nada novo criado)
    assert len(mine(db, owner)) == 1 and len(mine(db, staff)) == 1


def test_other_status_changes_do_not_notify(db, team):
    owner, *_ = team
    appt = make_appt(db)
    appt.status = "pending"
    db.flush()
    svc.change_status(db, owner, appt.id, "confirm")
    assert mine(db, owner) == []


def test_a_booking_made_by_the_client_in_the_bot_notifies_the_panel_but_one_made_in_the_panel_does_not(db, team):
    owner, staff, *_ = team
    service = db.scalar(select(Service).where(Service.name == "Manicure")) or Service(name="Manicure", price_cents=4500, duration_minutes=45)
    client = Client(name="Ana", phone="5511900000001")
    db.add_all([service, client])
    db.flush()
    start = datetime.now(UTC) + timedelta(days=2)
    svc.create_appointment(db, admin=staff, client_id=client.id, client_phone=None, client_name=None, service_id=service.id,
                           starts_at=start, notes=None, status="confirmed", source="admin", strict=False)
    assert mine(db, owner, "appointment_booked") == []                         # criado no painel: quem criou já sabe
    svc.create_appointment(db, admin=None, client_id=client.id, client_phone=None, client_name=None, service_id=service.id,
                           starts_at=start + timedelta(days=1), notes=None, status="confirmed", source="telegram", strict=False)
    booked = mine(db, owner, "appointment_booked")
    assert len(booked) == 1 and "Ana" in booked[0].body and booked[0].title == "Novo agendamento"


def test_a_new_signup_notifies_only_the_owner_once(db, team, monkeypatch):
    owner, staff, *_ = team
    monkeypatch.setattr(owner_notify, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(owner_notify.mailer, "send_mail", lambda *a: None)
    monkeypatch.setattr(owner_notify.geoip, "describe_location", lambda ip: "x")
    newbie = make_user(db, "nova@gmail.com", approved=False)
    owner_notify.notify_owner_new_user(newbie.id)
    owner_notify.notify_owner_new_user(newbie.id)                              # reenvio: não duplica no sino
    assert len(mine(db, owner, "user_signup")) == 1 and mine(db, staff, "user_signup") == []
    assert mine(db, owner, "user_signup")[0].link == "/usuarios" and "nova@gmail.com" in mine(db, owner, "user_signup")[0].body


# ---------------- API ----------------
def seed(db, user, n=3, **kw):
    for i in range(n):
        db.add(Notification(user_id=user.id, kind="appointment_cancelled", title=f"T{i}", body=f"B{i}", link="/agendamentos", **kw))
    db.flush()


def test_requires_login_and_panel_access(client, db, team):
    _, _, pending, _ = team
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=headers(pending)).status_code == 403
    assert client.post(f"{URL}/read-all").status_code == 401


def test_list_is_newest_first_with_the_unread_count(client, db, team):
    owner, *_ = team
    seed(db, owner, 3)
    r = client.get(URL, headers=headers(owner)).json()
    assert [i["title"] for i in r["items"]] == ["T2", "T1", "T0"] and r["unread_count"] == 3
    assert set(r["items"][0]) == {"id", "kind", "title", "body", "link", "created_at", "read_at"}


def test_limit_after_id_and_unread_filters(client, db, team):
    owner, *_ = team
    seed(db, owner, 5)
    ids = sorted(n.id for n in mine(db, owner))
    h = headers(owner)
    assert len(client.get(URL, params={"limit": 2}, headers=h).json()["items"]) == 2
    newer = client.get(URL, params={"after_id": ids[2]}, headers=h).json()
    assert sorted(i["id"] for i in newer["items"]) == ids[3:] and newer["unread_count"] == 5     # a contagem é sempre a geral
    assert client.get(URL, params={"limit": 0}, headers=h).status_code == 422
    assert client.get(URL, params={"limit": 51}, headers=h).status_code == 422
    client.post(f"{URL}/{ids[0]}/read", headers=h)
    assert len(client.get(URL, params={"unread_only": True}, headers=h).json()["items"]) == 4


def test_mark_one_as_read(client, db, team):
    owner, *_ = team
    seed(db, owner, 2)
    first = mine(db, owner)[0]
    r = client.post(f"{URL}/{first.id}/read", headers=headers(owner))
    assert r.status_code == 200 and r.json()["read_at"]
    assert client.get(URL, headers=headers(owner)).json()["unread_count"] == 1
    again = client.post(f"{URL}/{first.id}/read", headers=headers(owner))             # repetir não muda a hora
    assert again.json()["read_at"] == r.json()["read_at"]


def test_mark_all_as_read(client, db, team):
    owner, *_ = team
    seed(db, owner, 4)
    assert client.post(f"{URL}/read-all", headers=headers(owner)).json() == {"updated": 4}
    assert client.get(URL, headers=headers(owner)).json()["unread_count"] == 0
    assert client.post(f"{URL}/read-all", headers=headers(owner)).json() == {"updated": 0}


def test_people_cannot_see_or_touch_each_others_notifications(client, db, team):
    owner, staff, *_ = team
    seed(db, owner, 2)
    seed(db, staff, 1)
    theirs = mine(db, owner)[0]
    assert len(client.get(URL, headers=headers(staff)).json()["items"]) == 1
    assert client.get(URL, headers=headers(staff)).json()["unread_count"] == 1
    assert client.post(f"{URL}/{theirs.id}/read", headers=headers(staff)).status_code == 404   # igual a "não existe"
    assert client.post(f"{URL}/read-all", headers=headers(staff)).json() == {"updated": 1}     # só os dela
    db.refresh(theirs)
    assert theirs.read_at is None
    assert client.post(f"{URL}/999999/read", headers=headers(staff)).status_code == 404


def test_old_notifications_are_removed_automatically(db, team):
    owner, *_ = team
    seed(db, owner, 2)
    old_id = mine(db, owner)[0].id
    db.execute(update(Notification).where(Notification.id == old_id).values(created_at=datetime.now(UTC) - timedelta(days=notifications.RETENTION_DAYS + 1)))
    db.expire_all()
    notifications.notify(db, [owner], kind="appointment_booked", title="x", body="y")      # qualquer aviso novo dispara a faxina
    assert old_id not in [n.id for n in mine(db, owner)]


def test_deleting_a_user_removes_their_notifications(db, team):
    _, staff, *_ = team
    seed(db, staff, 2)
    db.delete(staff)
    db.flush()
    assert db.scalars(select(Notification).where(Notification.user_id == staff.id)).all() == []


def test_the_text_is_truncated_to_the_column_size(db, team):
    owner, *_ = team
    notifications.notify(db, [owner], kind="user_signup", title="t" * 500, body="b" * 900)
    n = mine(db, owner)[-1]
    assert len(n.title) == 120 and len(n.body) == 400
