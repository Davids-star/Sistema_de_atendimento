import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core.config import settings
from app.core.security import create_access_token, password_version
from app.models import AdminUser, AuditLog, EmailVerificationToken
from app.services import mailer

from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD

REGISTER, VERIFY, RESEND, LOGIN, ME = ("/api/v1/auth/" + p for p in ("register", "verify-email", "resend-verification", "login", "me"))
PW = "uma-senha-forte-123"
BODY = {"name": "Maria Souza", "phone": "(11) 98888-7777", "email": "maria@gmail.com", "password": PW, "password_confirm": PW}


@pytest.fixture
def outbox(monkeypatch):
    """Captura os e-mails: lista de (tipo, destinatário, token ou None)."""
    sent = []
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body: sent.append(
        (("verify" if "confirmar-email" in body else "already"), to,
         (re.search(r"token=(\S+)", body).group(1) if "token=" in body else None))))
    return sent


def signup(client, **over):
    return client.post(REGISTER, json={**BODY, **over})


def confirm(client, outbox):
    token = [o for o in outbox if o[0] == "verify"][-1][2]
    return client.post(VERIFY, json={"token": token})


def auth_of(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, password_version(user))}"}


# ---------- cadastro ----------
def test_signup_creates_an_unconfirmed_account_without_access(client, db, outbox):
    r = signup(client)
    assert r.status_code == 202
    user = db.scalar(select(AdminUser).where(AdminUser.email == "maria@gmail.com"))
    assert user.name == "Maria Souza" and user.phone == "5511988887777"
    assert not user.email_verified and not user.approved and not user.is_owner and user.is_active
    assert user.password_hash and PW not in user.password_hash          # senha guardada só como hash
    assert [(k, to) for k, to, _ in outbox] == [("verify", "maria@gmail.com")]


def test_signup_validation(client, outbox):
    bad = [
        {"password_confirm": "outra-senha-forte-1"},        # confirmação diferente
        {"password": "curta", "password_confirm": "curta"},  # senha curta
        {"phone": "123"},                                    # telefone inválido
        {"phone": "+1 415 555 2671"},                        # fora do Brasil
        {"email": "isso-nao-e-email"},
        {"name": "A"},
    ]
    for override in bad:
        assert signup(client, **override).status_code == 422, override
    assert outbox == []


def test_cannot_login_before_confirming_the_email(client, db, outbox):
    signup(client)
    r = client.post(LOGIN, json={"email": "maria@gmail.com", "password": PW})
    assert r.status_code == 403 and "Confirme seu e-mail" in r.json()["detail"]
    wrong = client.post(LOGIN, json={"email": "maria@gmail.com", "password": "senha-errada-123"})
    assert wrong.status_code == 401        # com senha errada ninguém descobre que a conta existe/está pendente


def test_confirming_the_email_lets_the_user_in_but_with_no_access(client, db, outbox):
    signup(client)
    assert confirm(client, outbox).status_code == 204
    login = client.post(LOGIN, json={"email": "maria@gmail.com", "password": PW})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get(ME, headers=headers).json()
    assert me["status"] == "pending_approval" and me["email_verified"] is True and me["approved"] is False
    for path in ("/api/v1/clients", "/api/v1/appointments", "/api/v1/dashboard/summary", "/api/v1/users"):
        assert client.get(path, headers=headers).status_code == 403, path
    assert client.post("/api/v1/services", headers=headers, json={"name": "x", "price_cents": 1, "duration_minutes": 5}).status_code == 403


def test_verification_link_is_single_use_and_expires(client, db, outbox):
    signup(client)
    token = outbox[-1][2]
    assert client.post(VERIFY, json={"token": token}).status_code == 204
    assert client.post(VERIFY, json={"token": token}).status_code == 400      # já usado
    signup(client, email="joao@gmail.com")
    expired = outbox[-1][2]
    db.execute(update(EmailVerificationToken).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    assert client.post(VERIFY, json={"token": expired}).status_code == 400
    assert client.post(VERIFY, json={"token": "x" * 43}).status_code == 400


def test_token_is_stored_only_as_hash(client, db, outbox):
    signup(client)
    raw = outbox[-1][2]
    assert raw not in [t.token_hash for t in db.scalars(select(EmailVerificationToken))]


def test_existing_email_gets_the_same_answer_and_a_different_email(client, admin, db, outbox):
    new = signup(client)
    dup = signup(client, email=ADMIN_EMAIL)
    assert dup.status_code == new.status_code == 202 and dup.json() == new.json()   # não revela quem tem conta
    assert [o[0] for o in outbox] == ["verify", "already"]
    assert db.scalar(select(AdminUser).where(AdminUser.email == ADMIN_EMAIL)).name == "Dono"   # a conta existente não mudou


def test_duplicate_signup_of_a_confirmed_account_cannot_change_its_password(client, admin, outbox):
    signup(client, email=ADMIN_EMAIL, password="senha-do-atacante-1", password_confirm="senha-do-atacante-1")
    assert client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).status_code == 200
    assert client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": "senha-do-atacante-1"}).status_code == 401


def test_squatter_cannot_keep_the_account_after_the_real_owner_signs_up(client, db, outbox):
    """Alguém se cadastra com o e-mail de outra pessoa; quando a dona real se cadastra e confirma, a conta é dela."""
    signup(client, name="Invasor", password="senha-do-invasor-1", password_confirm="senha-do-invasor-1")
    signup(client, name="Maria Real")                    # a dona real usa o mesmo e-mail
    old_link = outbox[0][2]
    assert client.post(VERIFY, json={"token": old_link}).status_code == 400    # o link do invasor morreu
    assert confirm(client, outbox).status_code == 204
    assert client.post(LOGIN, json={"email": "maria@gmail.com", "password": "senha-do-invasor-1"}).status_code == 401
    assert client.post(LOGIN, json={"email": "maria@gmail.com", "password": PW}).status_code == 200
    assert db.scalar(select(AdminUser).where(AdminUser.email == "maria@gmail.com")).name == "Maria Real"


def test_signup_is_rate_limited(client, outbox):
    for i in range(settings.login_max_failures * 4):
        assert signup(client, email=f"pessoa{i}@gmail.com").status_code == 202
    assert signup(client, email="mais-uma@gmail.com").status_code == 429


def test_resend_verification(client, admin, outbox):
    signup(client)
    first = outbox[-1][2]
    assert client.post(RESEND, json={"email": "maria@gmail.com"}).status_code == 202
    second = outbox[-1][2]
    assert first != second and len(outbox) == 2
    assert client.post(VERIFY, json={"token": first}).status_code == 400       # o antigo foi invalidado
    assert client.post(VERIFY, json={"token": second}).status_code == 204
    # já confirmado ou inexistente: mesma resposta e nenhum e-mail novo
    n = len(outbox)
    a = client.post(RESEND, json={"email": "maria@gmail.com"})
    b = client.post(RESEND, json={"email": "ninguem@gmail.com"})
    assert a.json() == b.json() and len(outbox) == n


def test_password_reset_also_proves_the_email(client, db, outbox, monkeypatch):
    signup(client)
    user = db.scalar(select(AdminUser).where(AdminUser.email == "maria@gmail.com"))
    assert not user.email_verified
    links = []
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, body: links.append(re.search(r"token=(\S+)", body).group(1)))
    client.post("/api/v1/auth/forgot-password", json={"email": "maria@gmail.com"})
    assert client.post("/api/v1/auth/reset-password", json={"token": links[-1], "new_password": "outra-senha-forte-9"}).status_code == 204
    db.refresh(user)
    assert user.email_verified
    assert client.post(LOGIN, json={"email": "maria@gmail.com", "password": "outra-senha-forte-9"}).status_code == 200


def test_audit_trail_has_no_secrets(client, db, outbox):
    signup(client)
    confirm(client, outbox)
    rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "admin_user")).all()
    assert {r.action for r in rows} >= {"signup", "email_verified"}
    assert PW not in str([r.changes for r in rows]) and outbox[-1][2] not in str([r.changes for r in rows])


# ---------- perfil / celular ----------
def test_user_can_set_their_phone_even_before_approval(client, db, monkeypatch):
    user = AdminUser(email="g@gmail.com", name="G", password_hash=None, email_verified_at=datetime.now(timezone.utc))
    db.add(user)
    db.flush()
    h = auth_of(user)
    assert client.get(ME, headers=h).json()["phone"] is None
    r = client.patch(ME, headers=h, json={"phone": "11 97777-6666"})
    assert r.status_code == 200 and r.json()["phone"] == "5511977776666"
    assert client.patch(ME, headers=h, json={"phone": "123"}).status_code == 422
    assert client.patch(ME, headers=h, json={"phone": None}).status_code == 422
    assert client.patch(ME, headers=h, json={"name": "Novo Nome"}).json()["name"] == "Novo Nome"


def test_profile_requires_login(client):
    assert client.patch(ME, json={"phone": "11977776666"}).status_code == 401


def test_profile_cannot_escalate_privileges(client, db):
    user = AdminUser(email="g@gmail.com", name="G", password_hash=None, email_verified_at=datetime.now(timezone.utc))
    db.add(user)
    db.flush()
    h = auth_of(user)
    client.patch(ME, headers=h, json={"is_owner": True, "approved": True, "approved_at": "2020-01-01T00:00:00Z"})
    db.refresh(user)
    assert not user.is_owner and not user.approved


# ---------- migração: quem já era admin continua com acesso ----------
def test_owner_fixture_has_full_access(client, auth):
    assert client.get(ME, headers=auth).json()["status"] == "active"
    assert client.get("/api/v1/clients", headers=auth).status_code == 200
