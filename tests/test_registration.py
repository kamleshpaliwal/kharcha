import pytest
from werkzeug.security import check_password_hash

from tests.conftest import fetch_users

VALID = {
    "name": "Asha Rao",
    "email": "asha@example.com",
    "password": "secret123",
    "confirm_password": "secret123",
}


def post(client, **overrides):
    return client.post("/register", data={**VALID, **overrides})


def test_get_register_renders_form(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b"Create your account" in resp.data


def test_valid_registration_creates_hashed_user_and_redirects(client):
    resp = post(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login?registered=1")

    users = fetch_users()
    assert len(users) == 1
    assert users[0]["password_hash"] != VALID["password"]
    assert check_password_hash(users[0]["password_hash"], VALID["password"])


def test_login_notice_only_when_registered(client):
    assert b"Account created" in client.get("/login?registered=1").data
    assert b"Account created" not in client.get("/login").data


@pytest.mark.parametrize("email", ["asha@example.com", "ASHA@Example.com"])
def test_duplicate_email_rejected(client, email):
    post(client)
    resp = post(client, email=email)
    assert resp.status_code == 400
    assert b"already exists" in resp.data
    assert len(fetch_users()) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "short77", "confirm_password": "short77"},
        {"confirm_password": "different123"},
        {"confirm_password": ""},
        {"name": ""},
        {"name": "   "},
        {"email": "not-an-email"},
        {"email": "@example.com"},
        {"email": "asha@"},
    ],
)
def test_invalid_input_rejected(client, overrides):
    resp = post(client, **overrides)
    assert resp.status_code == 400
    assert fetch_users() == []


def test_form_has_confirm_password_field(client):
    assert b'name="confirm_password"' in client.get("/register").data


def test_mismatch_shows_error_message(client):
    resp = post(client, confirm_password="different123")
    assert b"Passwords do not match" in resp.data


def test_error_keeps_name_and_email_but_not_password(client):
    resp = post(client, password="short", confirm_password="short")
    body = resp.get_data(as_text=True)
    assert 'value="Asha Rao"' in body
    assert 'value="asha@example.com"' in body
    assert "short" not in body.replace("Password must be", "")
