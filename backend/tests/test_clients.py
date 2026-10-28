import pytest

from app.services.clients import get_or_create_by_phone, normalize_phone

URL = "/api/v1/clients"


@pytest.mark.parametrize("raw,expected", [
    ("(11) 99999-8888", "5511999998888"),
    ("11999998888", "5511999998888"),
    ("+55 11 99999-8888", "5511999998888"),
    ("5511999998888", "5511999998888"),
    ("1133334444", "551133334444"),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["123", "abc", "999999999999999999", "+1 415 555 2671"])
def test_normalize_phone_invalid(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_requires_auth(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"name": "A", "phone": "11999998888"}).status_code == 401
    assert client.get(f"{URL}/1").status_code == 401


def test_create_and_duplicate(client, auth):
    r = client.post(URL, json={"name": "João", "phone": "(11) 98888-7777"}, headers=auth)
    assert r.status_code == 201 and r.json()["phone"] == "5511988887777"
    dup = client.post(URL, json={"name": "Outro", "phone": "+55 11 98888-7777"}, headers=auth)
    assert dup.status_code == 409


def test_invalid_phone_422(client, auth):
    assert client.post(URL, json={"name": "A", "phone": "12345678"}, headers=auth).status_code == 422


def test_search_and_get(client, auth):
    cid = client.post(URL, json={"name": "Zeca Zebra", "phone": "11977776666"}, headers=auth).json()["id"]
    found = client.get(URL, params={"q": "zebra"}, headers=auth).json()
    assert [c["id"] for c in found] == [cid]
    assert client.get(URL, params={"q": "77776666"}, headers=auth).json()[0]["id"] == cid
    assert client.get(f"{URL}/{cid}", headers=auth).json()["name"] == "Zeca Zebra"
    assert client.get(f"{URL}/999999", headers=auth).status_code == 404


def test_patch_and_phone_conflict(client, auth):
    a = client.post(URL, json={"name": "A", "phone": "11911110000"}, headers=auth).json()["id"]
    client.post(URL, json={"name": "B", "phone": "11922220000"}, headers=auth)
    assert client.patch(f"{URL}/{a}", json={"name": "A2"}, headers=auth).json()["name"] == "A2"
    assert client.patch(f"{URL}/{a}", json={"phone": "11922220000"}, headers=auth).status_code == 409
    assert client.patch(f"{URL}/{a}", json={"name": None}, headers=auth).status_code == 422


def test_get_or_create_is_idempotent(db):
    c1, created1 = get_or_create_by_phone(db, "(11) 95555-4444", "Maria")
    c2, created2 = get_or_create_by_phone(db, "5511955554444", "Outro Nome")
    assert created1 and not created2 and c1.id == c2.id and c2.name == "Maria"


def test_client_appointments_empty(client, auth):
    cid = client.post(URL, json={"name": "A", "phone": "11933330000"}, headers=auth).json()["id"]
    assert client.get(f"{URL}/{cid}/appointments", headers=auth).json() == []
