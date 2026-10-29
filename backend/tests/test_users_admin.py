from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, password_version
from app.models import AdminUser, AuditLog

from .conftest import ADMIN_EMAIL

URL = "/api/v1/users"


def make(db, email, *, verified=True, approved=False, owner=False, active=True, name="Fulano"):
    now = datetime.now(timezone.utc)
    user = AdminUser(email=email, name=name, password_hash=None, is_active=active, is_owner=owner,
                     email_verified_at=now if verified else None, approved_at=now if approved else None)
    db.add(user)
    db.flush()
    return user


def h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, password_version(user))}"}


@pytest.fixture
def pending(db):
    return make(db, "pendente@gmail.com")


def test_only_the_owner_can_manage_users(client, auth, db, pending):
    assert client.get(URL).status_code == 401                                              # anônimo
    assert client.get(URL, headers=h(pending)).status_code == 403                          # sem acesso liberado
    staff = make(db, "func@gmail.com", approved=True)                                      # liberado, mas não é dono
    assert client.get(URL, headers=h(staff)).status_code == 403
    assert client.post(f"{URL}/{pending.id}/approve", headers=h(staff)).status_code == 403
    assert client.get(URL, headers=auth).status_code == 200                                # dono


def test_list_and_filter_by_status(client, auth, admin, db, pending):
    make(db, "semconfirmar@gmail.com", verified=False)
    make(db, "ativo@gmail.com", approved=True)
    make(db, "off@gmail.com", approved=True, active=False)
    mine = {ADMIN_EMAIL, "pendente@gmail.com", "semconfirmar@gmail.com", "ativo@gmail.com", "off@gmail.com"}

    def by(status):  # só os e-mails deste teste: o banco pode ter outros usuários reais
        rows = client.get(URL, params={"status": status}, headers=auth).json()
        return sorted(u["email"] for u in rows if u["email"] in mine)

    assert by("pending_approval") == ["pendente@gmail.com"]
    assert by("pending_email") == ["semconfirmar@gmail.com"]
    assert by("disabled") == ["off@gmail.com"]
    assert by("active") == sorted([ADMIN_EMAIL, "ativo@gmail.com"])
    everyone = client.get(URL, headers=auth)
    assert mine <= {u["email"] for u in everyone.json()}
    assert client.get(URL, params={"status": "lixo"}, headers=auth).status_code == 422
    assert "password" not in everyone.text and "google_sub" not in everyone.text


def test_approving_gives_access_to_the_panel(client, auth, db, pending):
    assert client.get("/api/v1/clients", headers=h(pending)).status_code == 403
    r = client.post(f"{URL}/{pending.id}/approve", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert client.get("/api/v1/clients", headers=h(pending)).status_code == 200      # o mesmo token já funciona
    assert client.get(URL, headers=h(pending)).status_code == 403                    # mas continua sem poder gerir usuários
    assert client.post(f"{URL}/{pending.id}/approve", headers=auth).status_code == 200   # repetir é inofensivo
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == pending.id))]
    assert actions.count("user_approve") == 1


def test_cannot_approve_an_unconfirmed_email_or_a_disabled_user(client, auth, db):
    unconfirmed = make(db, "x@gmail.com", verified=False)
    assert client.post(f"{URL}/{unconfirmed.id}/approve", headers=auth).status_code == 409
    off = make(db, "y@gmail.com", active=False)
    assert client.post(f"{URL}/{off.id}/approve", headers=auth).status_code == 409
    assert client.post(f"{URL}/999999/approve", headers=auth).status_code == 404


def test_deactivating_cuts_access_immediately_and_reactivating_requires_a_new_login(client, auth, db):
    staff = make(db, "func@gmail.com", approved=True)
    old = h(staff)
    assert client.get("/api/v1/clients", headers=old).status_code == 200
    assert client.post(f"{URL}/{staff.id}/deactivate", headers=auth).json()["status"] == "disabled"
    assert client.get("/api/v1/clients", headers=old).status_code == 401
    assert client.post(f"{URL}/{staff.id}/reactivate", headers=auth).json()["status"] == "active"
    assert client.get("/api/v1/clients", headers=old).status_code == 401          # o token antigo não ressuscita
    db.refresh(staff)
    assert client.get("/api/v1/clients", headers=h(staff)).status_code == 200      # um novo funciona


def test_cannot_deactivate_yourself_or_another_owner(client, auth, admin, db):
    assert client.post(f"{URL}/{admin.id}/deactivate", headers=auth).status_code == 409
    other_owner = make(db, "socio@gmail.com", approved=True, owner=True)
    assert client.post(f"{URL}/{other_owner.id}/deactivate", headers=auth).status_code == 409
    db.refresh(admin)
    assert admin.is_active


def test_deactivated_user_cannot_log_in_with_google_either(client, auth, db, monkeypatch):
    from app.api.v1 import auth as auth_module
    from app.core.config import settings
    monkeypatch.setattr(settings, "google_client_id", "x.apps.googleusercontent.com")
    staff = make(db, "func@gmail.com", approved=True)
    client.post(f"{URL}/{staff.id}/deactivate", headers=auth)
    monkeypatch.setattr(auth_module, "verify_google_token", lambda c: {"sub": "5", "email": "func@gmail.com", "email_verified": True})
    assert client.post("/api/v1/auth/google", json={"credential": "x"}).status_code == 401
