from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import AdminUser, AuditLog
from app.services import owner as owner_service
from app.services import owner_notify

from .conftest import ADMIN_EMAIL


def make(db, email, *, verified=True, approved=False, owner=False):
    now = datetime.now(timezone.utc)
    user = AdminUser(email=email, name="X", password_hash=None, is_owner=owner,
                     email_verified_at=now if verified else None, approved_at=now if approved else None)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def only_owner(db, admin, monkeypatch):
    """Isola o teste dos donos que já existem no banco real."""
    monkeypatch.setattr(owner_service, "get_owner", lambda db_: admin)
    return admin


def test_changes_the_owner_email_and_keeps_password_and_access(db, only_owner):
    old_hash = only_owner.password_hash
    owner = owner_service.change_owner_email(db, "  Dono.Real@Gmail.com ")
    assert owner.email == "dono.real@gmail.com"                       # normaliza
    assert owner.password_hash == old_hash and owner.is_owner and owner.approved and owner.is_active
    assert any(a.action == "owner_email_change" for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == owner.id)))


def test_login_works_with_the_new_email_and_old_password(client, db, only_owner):
    from .conftest import ADMIN_PASSWORD
    owner_service.change_owner_email(db, "dono.real@gmail.com")
    assert client.post("/api/v1/auth/login", json={"email": "dono.real@gmail.com", "password": ADMIN_PASSWORD}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).status_code == 401


def test_google_login_with_the_new_email_links_to_the_owner_account(client, db, only_owner, monkeypatch):
    from app.api.v1 import auth as auth_module
    from app.core.config import settings
    only_owner.google_sub = "antigo"
    owner_service.change_owner_email(db, "dono.real@gmail.com")
    assert only_owner.google_sub is None
    monkeypatch.setattr(settings, "google_client_id", "x.apps.googleusercontent.com")
    monkeypatch.setattr(auth_module, "verify_google_token", lambda c: {"sub": "novo", "email": "dono.real@gmail.com", "email_verified": True})
    r = client.post("/api/v1/auth/google", json={"credential": "x"})
    assert r.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["is_owner"] is True and me["status"] == "active"        # entrou como dono, não como conta nova


@pytest.mark.parametrize("bad", ["", "sem-arroba", "a@b", "a b@c.com"])
def test_rejects_invalid_emails(db, only_owner, bad):
    with pytest.raises(owner_service.OwnerError):
        owner_service.change_owner_email(db, bad)


def test_rejects_the_same_email(db, only_owner):
    with pytest.raises(owner_service.OwnerError):
        owner_service.change_owner_email(db, ADMIN_EMAIL.upper())


def test_refuses_an_email_that_belongs_to_a_user_with_access(db, only_owner):
    make(db, "func@gmail.com", approved=True)
    with pytest.raises(owner_service.OwnerError) as e:
        owner_service.change_owner_email(db, "func@gmail.com", remove_conflict=True)   # nem com a autorização
    assert e.value.conflict is None


def test_a_pending_signup_with_that_email_is_only_removed_with_explicit_consent(db, only_owner):
    pending = make(db, "dono.real@gmail.com", verified=False)
    with pytest.raises(owner_service.OwnerError) as e:
        owner_service.change_owner_email(db, "dono.real@gmail.com")
    assert e.value.conflict.id == pending.id and only_owner.email == ADMIN_EMAIL     # nada mudou

    owner_service.change_owner_email(db, "dono.real@gmail.com", remove_conflict=True)
    assert only_owner.email == "dono.real@gmail.com"
    assert db.get(AdminUser, pending.id) is None


def test_removing_a_conflicting_signup_keeps_its_audit_history(db, only_owner):
    pending = make(db, "dono.real@gmail.com", verified=False)
    db.add(AuditLog(admin_user_id=pending.id, action="signup", entity_type="admin_user", entity_id=pending.id))
    db.flush()
    owner_service.change_owner_email(db, "dono.real@gmail.com", remove_conflict=True)
    row = db.scalar(select(AuditLog).where(AuditLog.action == "signup", AuditLog.entity_id == pending.id))
    assert row is not None and row.admin_user_id is None


def test_renotify_resends_only_for_pending_approval_users(db, monkeypatch):
    sent = []
    monkeypatch.setattr(owner_notify, "notify_owner_new_user", lambda uid: sent.append(uid))
    now = datetime.now(timezone.utc)
    waiting = make(db, "espera@gmail.com")
    waiting.owner_notified_at = now                                  # já tinha sido "avisado" (para o endereço errado)
    approved = make(db, "ok@gmail.com", approved=True)
    unconfirmed = make(db, "nao@gmail.com", verified=False)
    ids = owner_service.renotify_pending(db)
    assert waiting.id in ids and approved.id not in ids and unconfirmed.id not in ids
    assert waiting.id in sent and approved.id not in sent and unconfirmed.id not in sent
    db.refresh(waiting)
    assert waiting.owner_notified_at is None                          # liberado para o aviso poder sair de novo
