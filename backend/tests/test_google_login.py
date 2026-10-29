"""Login com Google: a verificação real do token é simulada (não chamamos o Google nos testes)."""
import pytest
from sqlalchemy import select

from app.api.v1 import auth as auth_module
from app.core.config import settings
from app.core.security import DUMMY_HASH, decode_access_token, hash_password
from app.models import AdminUser, AuditLog

from .conftest import ADMIN_EMAIL

URL = "/api/v1/auth/google"
SUB = "1122334455"


@pytest.fixture(autouse=True)
def google_on(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")


def fake_google(monkeypatch, **claims):
    data = {"sub": SUB, "email": ADMIN_EMAIL, "email_verified": True, **claims}
    monkeypatch.setattr(auth_module, "verify_google_token", lambda credential: data)


def invalid_google(monkeypatch):
    def boom(credential):
        raise ValueError("Token inválido")
    monkeypatch.setattr(auth_module, "verify_google_token", boom)


def test_config_exposes_client_id_or_null(client, monkeypatch):
    assert client.get("/api/v1/auth/config").json() == {"google_client_id": "test-client.apps.googleusercontent.com"}
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.get("/api/v1/auth/config").json() == {"google_client_id": None}


def test_disabled_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.post(URL, json={"credential": "x"}).status_code == 404


def test_known_admin_logs_in_and_account_is_linked(client, admin, db, monkeypatch):
    fake_google(monkeypatch)
    r = client.post(URL, json={"credential": "qualquer"})
    assert r.status_code == 200
    assert decode_access_token(r.json()["access_token"]) == admin.id
    db.refresh(admin)
    assert admin.google_sub == SUB
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_type == "admin_user"))]
    assert "google_link" in actions
    # o token serve de verdade
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == ADMIN_EMAIL


def test_email_is_case_insensitive(client, admin, monkeypatch):
    fake_google(monkeypatch, email=ADMIN_EMAIL.upper())
    assert client.post(URL, json={"credential": "x"}).status_code == 200


def test_unknown_google_account_gets_a_pending_account_with_no_access(client, admin, db, monkeypatch):
    fake_google(monkeypatch, sub="999", email="novo@gmail.com", name="Novo Usuário")
    r = client.post(URL, json={"credential": "x"})
    assert r.status_code == 200
    user = db.scalar(select(AdminUser).where(AdminUser.email == "novo@gmail.com"))
    assert user.google_sub == "999" and user.name == "Novo Usuário" and user.password_hash is None
    assert user.email_verified and not user.approved and not user.is_owner and user.phone is None

    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["status"] == "pending_approval" and me["approved"] is False
    # ...mas não enxerga nada do negócio
    for path in ("/api/v1/clients", "/api/v1/appointments", "/api/v1/dashboard/summary", "/api/v1/settings"):
        assert client.get(path, headers=headers).status_code == 403, path


def test_google_signup_without_a_name_uses_the_email_prefix(client, db, monkeypatch):
    fake_google(monkeypatch, sub="888", email="joao.silva@gmail.com")
    assert client.post(URL, json={"credential": "x"}).status_code == 200
    assert db.scalar(select(AdminUser).where(AdminUser.email == "joao.silva@gmail.com")).name == "joao.silva"


def test_google_login_confirms_the_email_of_an_unconfirmed_signup(client, db, monkeypatch):
    pending = AdminUser(email="ana@gmail.com", name="Ana", password_hash=hash_password("senha-qualquer-123"))
    db.add(pending)
    db.flush()
    assert not pending.email_verified
    fake_google(monkeypatch, sub="777", email="ana@gmail.com")
    assert client.post(URL, json={"credential": "x"}).status_code == 200
    db.refresh(pending)
    assert pending.email_verified and pending.google_sub == "777"


def test_unverified_email_is_rejected(client, admin, monkeypatch):
    fake_google(monkeypatch, email_verified=False)
    assert client.post(URL, json={"credential": "x"}).status_code == 401


def test_invalid_token_is_rejected(client, admin, monkeypatch):
    invalid_google(monkeypatch)
    assert client.post(URL, json={"credential": "lixo"}).status_code == 401


def test_other_google_account_cannot_take_over_a_linked_admin(client, admin, db, monkeypatch):
    admin.google_sub = SUB
    db.flush()
    fake_google(monkeypatch, sub="OUTRA-CONTA")           # mesmo e-mail, outra conta Google
    assert client.post(URL, json={"credential": "x"}).status_code == 401


def test_once_linked_login_follows_the_google_id_not_the_email(client, admin, db, monkeypatch):
    admin.google_sub = SUB
    db.flush()
    fake_google(monkeypatch, email="novo-email@gmail.com")  # a pessoa trocou o e-mail no Google
    assert client.post(URL, json={"credential": "x"}).status_code == 200


def test_inactive_admin_is_rejected(client, admin, db, monkeypatch):
    admin.is_active = False
    db.flush()
    fake_google(monkeypatch)
    assert client.post(URL, json={"credential": "x"}).status_code == 401


def test_failures_are_rate_limited(client, admin, monkeypatch):
    invalid_google(monkeypatch)
    for _ in range(settings.login_max_failures * 4):
        assert client.post(URL, json={"credential": "x"}).status_code == 401
    assert client.post(URL, json={"credential": "x"}).status_code == 429


# ---------- admin sem senha (só Google) ----------
@pytest.fixture
def google_only_admin(db):
    user = AdminUser(email="so-google@teste.com", name="Só Google", password_hash=None)
    db.add(user)
    db.flush()
    return user


def test_google_only_admin_can_log_in_with_google(client, google_only_admin, monkeypatch):
    fake_google(monkeypatch, email="so-google@teste.com", sub="777")
    assert client.post(URL, json={"credential": "x"}).status_code == 200


@pytest.mark.parametrize("password", ["", "qualquer", "senha-falsa-para-igualar-tempo"])
def test_google_only_admin_cannot_log_in_with_a_password(client, google_only_admin, password):
    """A última senha é a do hash falso usado para igualar tempo: não pode abrir a conta."""
    r = client.post("/api/v1/auth/login", json={"email": "so-google@teste.com", "password": password})
    assert r.status_code == 401


def test_password_login_still_works_for_normal_admin(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "senha-de-teste-123"})
    assert r.status_code == 200


def test_dummy_hash_really_matches_that_password():
    """Garante que o teste acima é relevante: a senha do hash falso de fato confere com ele."""
    from app.core.security import verify_password
    assert verify_password("senha-falsa-para-igualar-tempo", DUMMY_HASH)
