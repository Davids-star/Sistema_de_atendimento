import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import engine, get_db
from app.main import app
from app.models import AdminUser

ADMIN_EMAIL, ADMIN_PASSWORD = "dono@teste.com", "senha-de-teste-123"


@pytest.fixture
def db():
    """Sessão dentro de uma transação que é sempre desfeita no fim (o banco real fica intacto)."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin(db):
    user = AdminUser(email=ADMIN_EMAIL, name="Dono", password_hash=hash_password(ADMIN_PASSWORD))
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def auth(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
