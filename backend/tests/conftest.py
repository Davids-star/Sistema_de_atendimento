from datetime import datetime, timezone

import pytest

from app.core.config import settings

# Se TEST_DATABASE_URL estiver no .env, TODOS os testes usam esse banco (o principal fica intocado).
# Precisa ser decidido antes de importar app.db.session, que cria a conexão.
if settings.test_database_url:
    settings.database_url = settings.test_database_url

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import rate_limit  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import engine, get_db
from app.main import app
from app.models import AdminUser

ADMIN_EMAIL, ADMIN_PASSWORD = "dono@teste.com", "senha-de-teste-123"


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Contadores são globais em memória: zera antes de cada teste para um não afetar o outro."""
    rate_limit.general.clear()
    rate_limit.login_failures.clear()
    rate_limit.reset_requests.clear()
    rate_limit.signups.clear()


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
    now = datetime.now(timezone.utc)
    user = AdminUser(email=ADMIN_EMAIL, name="Dono", password_hash=hash_password(ADMIN_PASSWORD),
                     email_verified_at=now, approved_at=now, is_owner=True)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def auth(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
