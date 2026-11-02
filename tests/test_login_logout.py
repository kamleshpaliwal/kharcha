import database.db as db
from werkzeug.security import generate_password_hash

from tests.conftest import fetch_users

EMAIL = "asha@example.com"
PASSWORD = "secret123"


def make_user(email=EMAIL, password=PASSWORD, name="Asha Rao"):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def test_get_login_renders_form(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Welcome back" in resp.data
    assert b'action="/login"' in resp.data


def test_valid_login_sets_session_and_redirects(client):
    user_id = make_user()
    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    with client.session_transaction() as sess:
        assert sess["user_id"] == user_id


def test_login_email_is_case_insensitive(client):
    make_user()
    resp = login(client, email="  Asha@Example.COM ")
    assert resp.status_code == 302


def test_wrong_password_rejected(client):
    make_user()
    resp = login(client, password="wrongpass")
    assert resp.status_code == 400
    assert b"Invalid email or password." in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_unknown_email_gets_same_error(client):
    make_user()
    resp = login(client, email="nobody@example.com")
    assert resp.status_code == 400
    assert b"Invalid email or password." in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_blank_fields_rejected(client):
    for data in ({"email": "", "password": ""}, {"email": EMAIL, "password": ""}):
        resp = client.post("/login", data=data)
        assert resp.status_code == 400
        assert b"Email and password are required." in resp.data


def test_failed_login_keeps_email_but_not_password(client):
    make_user()
    resp = login(client, password="wrongpass")
    assert f'value="{EMAIL}"'.encode() in resp.data
    assert b"wrongpass" not in resp.data


def test_login_page_redirects_when_logged_in(client):
    make_user()
    login(client)
    resp = client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_register_redirects_when_logged_in(client):
    make_user()
    login(client)
    resp = client.get("/register")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")

    resp = client.post(
        "/register",
        data={
            "name": "Other",
            "email": "other@example.com",
            "password": "password1",
            "confirm_password": "password1",
        },
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert len(fetch_users()) == 1


def test_logout_clears_session_and_redirects(client):
    make_user()
    login(client)
    resp = client.post("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_get_logout_not_allowed(client):
    assert client.get("/logout").status_code == 405


def test_navbar_reflects_login_state(client):
    make_user()
    resp = client.get("/login")
    assert b"Sign in" in resp.data
    assert b"Sign out" not in resp.data

    login(client)
    resp = client.get("/terms")
    assert b"Sign out" in resp.data
    assert b"Get started" not in resp.data


def test_login_after_registering(client):
    client.post(
        "/register",
        data={
            "name": "Ravi",
            "email": "ravi@example.com",
            "password": "password1",
            "confirm_password": "password1",
        },
    )
    resp = login(client, email="ravi@example.com", password="password1")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
