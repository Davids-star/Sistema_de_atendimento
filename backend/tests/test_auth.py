from app.core.security import create_access_token

from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def test_login_ok_and_me(client, admin, auth):
    r = client.get("/api/v1/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN_EMAIL
    assert "password" not in r.text


def test_login_wrong_password(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "errada"})
    assert r.status_code == 401


def test_login_unknown_email_same_message(client, admin):
    a = client.post("/api/v1/auth/login", json={"email": "x@y.com", "password": "qualquer"})
    b = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "errada"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_invalid_token(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer lixo"})
    assert r.status_code == 401


def test_token_of_deleted_admin(client, db, admin):
    token = create_access_token(admin.id)
    db.delete(admin)
    db.flush()
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_logout(client, auth):
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 204
