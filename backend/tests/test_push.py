import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, password_version
from app.models import AdminUser, DeviceToken, Notification
from app.services import push

UTC = timezone.utc
TOKEN_A = "dGVzdC10b2tlbi1hbmRyb2lkLUE6QVBBOTFiR_exampleTOKEN-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOKEN_B = "dGVzdC10b2tlbi1hbmRyb2lkLUI6QVBBOTFiR_exampleTOKEN-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body if body is not None else {}
        self.ok = 200 <= status < 300
    def json(self):
        return self._body


def fcm_error(status, code, grpc=None):
    return Resp(status, {"error": {"code": status, "status": grpc or code, "details": [{"errorCode": code}] if code else []}})


@pytest.fixture
def fcm(monkeypatch):
    """FCM simulado. `box.responses` é uma fila de respostas por chamada (a última se repete)."""
    box = SimpleNamespace(calls=[], responses=[Resp(200)], sleeps=[])
    monkeypatch.setattr(settings, "fcm_service_account_file", "/tmp/nao-existe.json")
    monkeypatch.setattr(push, "_credentials", lambda: SimpleNamespace(project_id="meu-projeto", token="ACCESS", valid=True))
    def post(url, json=None, headers=None, timeout=None):
        box.calls.append(SimpleNamespace(url=url, json=json, headers=headers))
        item = box.responses[min(len(box.calls) - 1, len(box.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(push.requests, "post", post)
    monkeypatch.setattr(push.time, "sleep", lambda s: box.sleeps.append(s))
    return box


def make_user(db, email="bia@gmail.com", owner=False):
    now = datetime.now(UTC)
    u = AdminUser(email=email, name="Bia", password_hash=None, is_owner=owner, email_verified_at=now, approved_at=now)
    db.add(u)
    db.flush()
    return u


def make_notice(db, user, **kw):
    n = Notification(user_id=user.id, kind="appointment_cancelled", title="Agendamento cancelado", body="Maria · Manicure", link="/agendamentos", **kw)
    db.add(n)
    db.flush()
    return n


def add_device(db, user, token=TOKEN_A):
    d = DeviceToken(user_id=user.id, token=token)
    db.add(d)
    db.flush()
    return d


# ---------------- mensagem ----------------
def test_message_shape_matches_the_fcm_v1_api():
    m = push.build_message("TOK", "Título", "Corpo", "/agendamentos", 7, "appointment_cancelled")["message"]
    assert m["token"] == "TOK" and m["notification"] == {"title": "Título", "body": "Corpo"}
    assert m["data"] == {"notification_id": "7", "kind": "appointment_cancelled", "link": "/agendamentos"}
    assert all(isinstance(v, str) for v in m["data"].values())                      # o FCM exige texto nos valores de "data"
    assert m["android"] == {"priority": "HIGH", "notification": {"channel_id": "avisos"}}


def test_message_without_a_link_omits_it():
    assert "link" not in push.build_message("T", "t", "b", None, 1, "x")["message"]["data"]


# ---------------- envio e regras de erro ----------------
def test_a_successful_send_uses_the_project_and_the_bearer_token(fcm):
    assert push.send_one(TOKEN_A, {"message": {}}) == "ok"
    call = fcm.calls[0]
    assert call.url == "https://fcm.googleapis.com/v1/projects/meu-projeto/messages:send"
    assert call.headers == {"Authorization": "Bearer ACCESS"}


@pytest.mark.parametrize("resp", [fcm_error(404, "UNREGISTERED", "NOT_FOUND"), fcm_error(404, None, "NOT_FOUND")])
def test_unregistered_tokens_are_reported_for_removal_without_retrying(fcm, resp):
    fcm.responses = [resp]
    assert push.send_one(TOKEN_A, {}) == "unregistered" and len(fcm.calls) == 1


def test_invalid_argument_is_not_retried_and_does_not_remove_the_token(fcm):
    fcm.responses = [fcm_error(400, "INVALID_ARGUMENT")]
    assert push.send_one(TOKEN_A, {}) == "error" and len(fcm.calls) == 1


@pytest.mark.parametrize("status,code", [(403, "SENDER_ID_MISMATCH"), (401, "THIRD_PARTY_AUTH_ERROR"), (429, "QUOTA_EXCEEDED")])
def test_other_client_errors_are_not_retried_and_never_remove_the_token(fcm, status, code):
    fcm.responses = [fcm_error(status, code)]
    assert push.send_one(TOKEN_A, {}) == "error" and len(fcm.calls) == 1


def test_server_errors_are_retried_with_a_wait_and_then_give_up(fcm):
    fcm.responses = [fcm_error(503, "UNAVAILABLE")]
    assert push.send_one(TOKEN_A, {}, attempts=3) == "failed"
    assert len(fcm.calls) == 3 and fcm.sleeps == [2, 4]                              # espera crescente entre as tentativas


def test_a_transient_error_followed_by_success_is_ok(fcm):
    fcm.responses = [fcm_error(500, "INTERNAL"), Resp(200)]
    assert push.send_one(TOKEN_A, {}) == "ok" and len(fcm.calls) == 2


def test_a_network_failure_is_retried_and_never_raises(fcm, caplog):
    import requests
    fcm.responses = [requests.ConnectionError(f"falha em {TOKEN_A}"), Resp(200)]
    with caplog.at_level(logging.DEBUG):
        assert push.send_one(TOKEN_A, {}) == "ok"
    assert TOKEN_A not in caplog.text


def test_tokens_and_response_bodies_never_reach_the_logs(fcm, caplog):
    fcm.responses = [fcm_error(400, "INVALID_ARGUMENT")]
    with caplog.at_level(logging.DEBUG):
        push.send_one(TOKEN_A, push.build_message(TOKEN_A, "t", "b", None, 1, "k"))
    assert TOKEN_A not in caplog.text and "ACCESS" not in caplog.text


# ---------------- despachante ----------------
def test_dispatch_does_nothing_when_push_is_not_configured(db, monkeypatch):
    monkeypatch.setattr(settings, "fcm_service_account_file", "")
    user = make_user(db)
    add_device(db, user)
    make_notice(db, user)
    assert push.dispatch_pending(db) == 0


def test_dispatch_sends_to_every_device_of_the_recipient_only(db, fcm):
    bia, other = make_user(db), make_user(db, "outra@gmail.com")
    add_device(db, bia, TOKEN_A); add_device(db, bia, TOKEN_B)
    add_device(db, other, "outro-token-do-outro-aparelho-com-mais-de-vinte-caracteres")
    n = make_notice(db, bia)
    assert push.dispatch_pending(db) >= 1
    assert sorted(c.json["message"]["token"] for c in fcm.calls) == sorted([TOKEN_A, TOKEN_B])      # nada para a outra pessoa
    assert all(c.json["message"]["data"]["notification_id"] == str(n.id) for c in fcm.calls)
    db.refresh(n)
    assert n.pushed_at is not None


def test_each_notification_is_pushed_only_once(db, fcm):
    user = make_user(db)
    add_device(db, user)
    make_notice(db, user)
    push.dispatch_pending(db)
    sent = len(fcm.calls)
    assert push.dispatch_pending(db) == 0 and len(fcm.calls) == sent


def test_notifications_already_read_in_the_app_get_no_push(db, fcm):
    user = make_user(db)
    add_device(db, user)
    n = make_notice(db, user, read_at=datetime.now(UTC))
    push.dispatch_pending(db)
    assert fcm.calls == []
    db.refresh(n)
    assert n.pushed_at is not None                                                   # marcado, para não ser reavaliado


def test_old_notifications_are_not_pushed_when_push_is_enabled_later(db, fcm):
    user = make_user(db)
    add_device(db, user)
    old = make_notice(db, user)
    old.created_at = datetime.now(UTC) - timedelta(minutes=settings.push_max_age_minutes + 5)
    db.flush()
    push.dispatch_pending(db)
    assert fcm.calls == []


def test_an_unregistered_token_is_deleted_and_others_are_kept(db, fcm):
    user = make_user(db)
    dead, alive = add_device(db, user, TOKEN_A), add_device(db, user, TOKEN_B)
    dead_id, alive_id = dead.id, alive.id
    make_notice(db, user)
    fcm.responses = [fcm_error(404, "UNREGISTERED", "NOT_FOUND"), Resp(200)]
    push.dispatch_pending(db)
    ids = [d.id for d in db.scalars(select(DeviceToken).where(DeviceToken.user_id == user.id))]
    assert dead_id not in ids and alive_id in ids


def test_a_temporary_failure_keeps_the_token(db, fcm, monkeypatch):
    user = make_user(db)
    device = add_device(db, user)
    device_id = device.id
    make_notice(db, user)
    fcm.responses = [fcm_error(503, "UNAVAILABLE")]
    push.dispatch_pending(db)
    assert db.get(DeviceToken, device_id) is not None


def test_two_dispatchers_cannot_send_the_same_notification(db, fcm):
    user = make_user(db)
    add_device(db, user)
    n = make_notice(db, user, pushed_at=datetime.now(UTC))                           # outro processo já despachou
    assert push.dispatch_pending(db) == 0 and fcm.calls == []


def test_a_user_without_devices_is_simply_marked_as_handled(db, fcm):
    user = make_user(db)
    n = make_notice(db, user)
    push.dispatch_pending(db)
    db.refresh(n)
    assert fcm.calls == [] and n.pushed_at is not None


def test_the_loop_survives_errors_and_stops(monkeypatch, caplog):
    import contextlib, threading
    stop, calls = threading.Event(), []
    def flaky(db, now=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("banco caiu")
        stop.set()
        return 0
    monkeypatch.setattr(push, "dispatch_pending", flaky)
    monkeypatch.setattr(push, "SessionLocal", lambda: contextlib.nullcontext(None))
    t = threading.Thread(target=push.run_loop, kwargs={"interval": 0.01, "stop": stop})
    t.start(); t.join(5)
    assert not t.is_alive() and len(calls) == 2 and "falha no despachante de push" in caplog.text


def test_the_api_starts_the_dispatcher_only_when_push_is_configured(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    started = []
    monkeypatch.setattr(push, "run_loop", lambda **kw: started.append(1))
    monkeypatch.setattr(settings, "fcm_service_account_file", "")
    with TestClient(app):
        pass
    assert started == []
    monkeypatch.setattr(settings, "fcm_service_account_file", "/x.json")
    import time
    with TestClient(app):
        time.sleep(0.2)
    assert started == [1]


# ---------------- API de aparelhos ----------------
URL = "/api/v1/devices"


def headers(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, password_version(u))}"}


def test_devices_require_login_and_panel_access(client, db):
    pending = AdminUser(email="p@gmail.com", name="P", password_hash=None, email_verified_at=datetime.now(UTC))
    db.add(pending); db.flush()
    assert client.post(URL, json={"token": TOKEN_A}).status_code == 401
    assert client.post(URL, json={"token": TOKEN_A}, headers=headers(pending)).status_code == 403


def test_register_a_device(client, db, admin):
    r = client.post(URL, json={"token": TOKEN_A, "platform": "android"}, headers=headers(admin))
    assert r.status_code == 201 and r.json() == {"registered": True}
    assert db.scalar(select(DeviceToken).where(DeviceToken.token == TOKEN_A)).user_id == admin.id
    assert client.post(URL, json={"token": TOKEN_A}, headers=headers(admin)).status_code == 201        # repetir é inofensivo
    assert len(db.scalars(select(DeviceToken).where(DeviceToken.token == TOKEN_A)).all()) == 1


def test_the_same_device_logging_in_with_another_account_moves_the_token(client, db, admin):
    other = make_user(db)
    client.post(URL, json={"token": TOKEN_A}, headers=headers(admin))
    client.post(URL, json={"token": TOKEN_A}, headers=headers(other))
    assert db.scalar(select(DeviceToken).where(DeviceToken.token == TOKEN_A)).user_id == other.id       # a conta anterior para de receber


@pytest.mark.parametrize("body", [{"token": "curto"}, {"token": "com espaço " + "x" * 30}, {"token": "x" * 30, "platform": "ios"},
                                  {"token": "x" * 5000}, {"token": "<script>" + "x" * 30}, {}])
def test_invalid_registrations_are_rejected(client, admin, body):
    assert client.post(URL, json=body, headers=headers(admin)).status_code == 422


def test_removing_a_device_only_removes_your_own(client, db, admin):
    other = make_user(db)
    add_device(db, other, TOKEN_B)
    add_device(db, admin, TOKEN_A)
    assert client.post(f"{URL}/remove", json={"token": TOKEN_B}, headers=headers(admin)).status_code == 204   # não é dela: nada acontece
    assert db.scalar(select(DeviceToken).where(DeviceToken.token == TOKEN_B)) is not None
    assert client.post(f"{URL}/remove", json={"token": TOKEN_A}, headers=headers(admin)).status_code == 204
    assert db.scalar(select(DeviceToken).where(DeviceToken.token == TOKEN_A)) is None
    assert client.post(f"{URL}/remove", json={"token": TOKEN_A}).status_code == 401


def test_deleting_a_user_removes_their_devices(db):
    user = make_user(db)
    add_device(db, user)
    db.delete(user)
    db.flush()
    assert db.scalars(select(DeviceToken).where(DeviceToken.token == TOKEN_A)).all() == []
