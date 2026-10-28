import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core.config import settings
from app.core.security import hash_reset_token
from app.models import AdminUser, AuditLog, PasswordResetToken
from app.services import mailer

from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD

FORGOT, RESET, CHANGE, LOGIN = ("/api/v1/auth/" + p for p in ("forgot-password", "reset-password", "change-password", "login"))
NEW = "uma-senha-nova-forte-1"


@pytest.fixture
def outbox(monkeypatch):
    """Captura os e-mails em vez de enviar. Cada item: (destinatário, link)."""
    sent = []
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body: sent.append((to, re.search(r"https?://\S+", body).group(0))))
    return sent


def token_from(link: str) -> str:
    return link.split("token=")[1]


def login(client, password, email=ADMIN_EMAIL):
    return client.post(LOGIN, json={"email": email, "password": password})


def request_reset(client, outbox, email=ADMIN_EMAIL):
    assert client.post(FORGOT, json={"email": email}).status_code == 202
    return token_from(outbox[-1][1])


# ---------- pedir o link ----------
def test_forgot_known_email_sends_one_link(client, admin, outbox):
    r = client.post(FORGOT, json={"email": ADMIN_EMAIL})
    assert r.status_code == 202
    assert len(outbox) == 1 and outbox[0][0] == ADMIN_EMAIL
    assert outbox[0][1].startswith(f"{settings.frontend_url}/redefinir-senha?token=")


def test_forgot_unknown_email_gives_identical_answer_and_sends_nothing(client, admin, outbox):
    known = client.post(FORGOT, json={"email": ADMIN_EMAIL})
    unknown = client.post(FORGOT, json={"email": "ninguem@x.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()          # não revela quem é administrador
    assert len(outbox) == 1                        # só o conhecido recebeu e-mail


def test_forgot_inactive_admin_gets_no_email(client, admin, db, outbox):
    admin.is_active = False
    db.flush()
    assert client.post(FORGOT, json={"email": ADMIN_EMAIL}).status_code == 202
    assert outbox == []


def test_forgot_is_rate_limited_per_email(client, admin, outbox):
    for _ in range(settings.login_max_failures):
        assert client.post(FORGOT, json={"email": ADMIN_EMAIL}).status_code == 202
    blocked = client.post(FORGOT, json={"email": ADMIN_EMAIL})
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers
    assert len(outbox) == settings.login_max_failures   # o excedente não gerou e-mail


def test_forgot_rate_limit_also_applies_to_unknown_emails(client, admin, outbox):
    for _ in range(settings.login_max_failures):
        client.post(FORGOT, json={"email": "ninguem@x.com"})
    assert client.post(FORGOT, json={"email": "ninguem@x.com"}).status_code == 429


def test_token_is_stored_only_as_hash(client, admin, db, outbox):
    raw = request_reset(client, outbox)
    stored = db.scalars(select(PasswordResetToken)).all()
    assert [t.token_hash for t in stored] == [hash_reset_token(raw)]
    assert raw not in stored[0].token_hash


def test_new_request_invalidates_the_previous_link(client, admin, outbox):
    first = request_reset(client, outbox)
    second = request_reset(client, outbox)
    assert client.post(RESET, json={"token": first, "new_password": NEW}).status_code == 400
    assert client.post(RESET, json={"token": second, "new_password": NEW}).status_code == 204


# ---------- usar o link ----------
def test_reset_changes_the_password(client, admin, outbox):
    raw = request_reset(client, outbox)
    assert client.post(RESET, json={"token": raw, "new_password": NEW}).status_code == 204
    assert login(client, NEW).status_code == 200
    assert login(client, ADMIN_PASSWORD).status_code == 401      # a senha antiga não vale mais


def test_link_is_single_use(client, admin, outbox):
    raw = request_reset(client, outbox)
    assert client.post(RESET, json={"token": raw, "new_password": NEW}).status_code == 204
    again = client.post(RESET, json={"token": raw, "new_password": "outra-senha-forte-2"})
    assert again.status_code == 400
    assert login(client, NEW).status_code == 200                  # a segunda tentativa não mudou nada


def test_expired_link_is_rejected(client, admin, db, outbox):
    raw = request_reset(client, outbox)
    db.execute(update(PasswordResetToken).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    assert client.post(RESET, json={"token": raw, "new_password": NEW}).status_code == 400
    assert login(client, ADMIN_PASSWORD).status_code == 200       # senha antiga intacta


def test_garbage_token_is_rejected_with_the_same_message(client, admin, outbox):
    raw = request_reset(client, outbox)
    bad = client.post(RESET, json={"token": "x" * 43, "new_password": NEW})
    client.post(RESET, json={"token": raw, "new_password": NEW})
    used = client.post(RESET, json={"token": raw, "new_password": NEW})
    assert bad.status_code == used.status_code == 400
    assert bad.json() == used.json()


def test_weak_password_is_rejected_and_link_survives(client, admin, outbox):
    raw = request_reset(client, outbox)
    assert client.post(RESET, json={"token": raw, "new_password": "curta"}).status_code == 422
    assert client.post(RESET, json={"token": raw, "new_password": NEW}).status_code == 204   # ainda vale


def test_inactive_admin_cannot_use_a_link(client, admin, db, outbox):
    raw = request_reset(client, outbox)
    admin.is_active = False
    db.flush()
    assert client.post(RESET, json={"token": raw, "new_password": NEW}).status_code == 400


def test_reset_logs_out_existing_sessions(client, admin, auth, outbox):
    """Quem tinha a sessão aberta (ou roubou um token) perde o acesso quando a senha é redefinida."""
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200
    raw = request_reset(client, outbox)
    client.post(RESET, json={"token": raw, "new_password": NEW})
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
    fresh = login(client, NEW).json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200


def test_reset_unlocks_an_account_blocked_by_failed_logins(client, admin, outbox):
    for _ in range(settings.login_max_failures):
        login(client, "errada")
    assert login(client, ADMIN_PASSWORD).status_code == 429
    raw = request_reset(client, outbox)
    client.post(RESET, json={"token": raw, "new_password": NEW})
    assert login(client, NEW).status_code == 200


def test_invalid_links_are_rate_limited(client, admin):
    for _ in range(settings.login_max_failures * 4):
        assert client.post(RESET, json={"token": "y" * 43, "new_password": NEW}).status_code == 400
    assert client.post(RESET, json={"token": "y" * 43, "new_password": NEW}).status_code == 429


def test_audit_trail_records_the_events_without_secrets(client, admin, db, outbox):
    raw = request_reset(client, outbox)
    client.post(RESET, json={"token": raw, "new_password": NEW})
    rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "admin_user")).all()
    assert {r.action for r in rows} >= {"password_reset_requested", "password_reset"}
    assert raw not in str([r.changes for r in rows]) and NEW not in str([r.changes for r in rows])


# ---------- alterar a senha estando logado ----------
def test_change_password_requires_login(client):
    assert client.post(CHANGE, json={"current_password": "x", "new_password": NEW}).status_code == 401


def test_change_password_ok_and_returns_a_working_new_token(client, admin, auth):
    r = client.post(CHANGE, headers=auth, json={"current_password": ADMIN_PASSWORD, "new_password": NEW})
    assert r.status_code == 200
    new_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200   # a sessão atual continua
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401            # o token antigo não
    assert login(client, NEW).status_code == 200 and login(client, ADMIN_PASSWORD).status_code == 401


def test_change_password_wrong_current(client, admin, auth):
    r = client.post(CHANGE, headers=auth, json={"current_password": "errada", "new_password": NEW})
    assert r.status_code == 400
    assert login(client, ADMIN_PASSWORD).status_code == 200


def test_change_password_requires_current_when_admin_has_one(client, admin, auth):
    assert client.post(CHANGE, headers=auth, json={"new_password": NEW}).status_code == 400


def test_change_password_rejects_same_password(client, admin, auth):
    r = client.post(CHANGE, headers=auth, json={"current_password": ADMIN_PASSWORD, "new_password": ADMIN_PASSWORD})
    assert r.status_code == 400


def test_change_password_weak(client, admin, auth):
    assert client.post(CHANGE, headers=auth, json={"current_password": ADMIN_PASSWORD, "new_password": "curta"}).status_code == 422


def test_change_password_guessing_is_rate_limited(client, admin, auth):
    for _ in range(settings.login_max_failures):
        assert client.post(CHANGE, headers=auth, json={"current_password": "chute", "new_password": NEW}).status_code == 400
    assert client.post(CHANGE, headers=auth, json={"current_password": ADMIN_PASSWORD, "new_password": NEW}).status_code == 429


def test_google_only_admin_can_set_a_first_password(client, db):
    from app.core.security import create_access_token
    only_google = AdminUser(email="g@teste.com", name="G", password_hash=None)
    db.add(only_google)
    db.flush()
    headers = {"Authorization": f"Bearer {create_access_token(only_google.id)}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["has_password"] is False
    assert client.post(CHANGE, headers=headers, json={"new_password": NEW}).status_code == 200
    assert login(client, NEW, "g@teste.com").status_code == 200


# ---------- e-mail ----------
def test_console_mode_prints_the_link_and_never_logs_it(monkeypatch, capsys, caplog):
    monkeypatch.setattr(settings, "mail_mode", "console")
    with caplog.at_level("DEBUG"):
        mailer.send_reset_email("dono@x.com", "TOKEN-SECRETO-123")
    assert "redefinir-senha?token=TOKEN-SECRETO-123" in capsys.readouterr().out
    assert "TOKEN-SECRETO-123" not in caplog.text


def test_off_mode_sends_nothing_and_does_not_crash(monkeypatch, capsys, caplog):
    monkeypatch.setattr(settings, "mail_mode", "off")
    with caplog.at_level("WARNING"):
        mailer.send_reset_email("dono@x.com", "TOKEN-SECRETO-123")
    assert capsys.readouterr().out == "" and "TOKEN-SECRETO-123" not in caplog.text


def test_smtp_mode_sends_via_starttls_and_survives_failures(monkeypatch, caplog):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout): calls.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): calls.append(("starttls",))
        def login(self, u, p): calls.append(("login", u))
        def send_message(self, msg): calls.append(("send", msg["To"], msg["Subject"]))

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    for k, v in dict(mail_mode="smtp", smtp_host="smtp.x.com", smtp_port=587, smtp_user="u@x.com", smtp_password="pw").items():
        monkeypatch.setattr(settings, k, v)
    mailer.send_reset_email("dono@x.com", "T" * 30)
    assert [c[0] for c in calls] == ["connect", "starttls", "login", "send"] and calls[-1][1] == "dono@x.com"

    def broken(*a, **k): raise OSError("sem rede")
    monkeypatch.setattr(mailer.smtplib, "SMTP", broken)
    with caplog.at_level("ERROR"):
        mailer.send_reset_email("dono@x.com", "T" * 30)       # não pode derrubar a requisição
    assert "falha ao enviar e-mail" in caplog.text and "T" * 30 not in caplog.text
