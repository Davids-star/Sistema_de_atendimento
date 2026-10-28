import logging

from app.main import app


@app.get("/_boom")
def boom():
    raise RuntimeError("falha simulada")


def test_unhandled_error_is_logged_with_request_id(client, caplog):
    with caplog.at_level(logging.ERROR):
        r = client.get("/_boom")
    assert r.status_code == 500
    rid = r.json()["request_id"]
    assert r.headers["X-Request-ID"] == rid
    assert "falha simulada" in caplog.text and "ERRO NAO TRATADO" in caplog.text
    assert "Traceback" in caplog.text


def test_success_has_request_id_header(client):
    assert len(client.get("/health").headers["X-Request-ID"]) == 8


def test_failed_login_logged_without_password(client, admin, caplog):
    with caplog.at_level(logging.WARNING):
        client.post("/api/v1/auth/login", json={"email": "dono@teste.com", "password": "SEGREDO123"})
    assert "login falhou" in caplog.text
    assert "SEGREDO123" not in caplog.text
