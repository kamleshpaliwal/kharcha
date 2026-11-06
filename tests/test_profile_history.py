from datetime import date, timedelta

import database.db as db
from app import _get_recent_expenses

from tests.test_profile import add_expense, login, make_user


def recent_for(user_id):
    conn = db.get_db()
    try:
        return _get_recent_expenses(conn, user_id)
    finally:
        conn.close()


def day(n):
    return (date.today() - timedelta(days=n)).isoformat()


def test_recent_capped_at_ten(app):
    uid = make_user()
    for i in range(15):
        add_expense(uid, 10 + i, when=day(i), description=f"e{i}")
    assert len(recent_for(uid)) == 10


def test_recent_newest_first_with_id_tiebreak(app):
    uid = make_user()
    add_expense(uid, 1, when=day(5), description="old")
    add_expense(uid, 2, when=day(1), description="same-a")
    add_expense(uid, 3, when=day(1), description="same-b")
    add_expense(uid, 4, when=day(3), description="mid")
    descs = [r["description"] for r in recent_for(uid)]
    assert descs == ["same-b", "same-a", "mid", "old"]


def test_recent_excludes_other_users(app):
    uid = make_user()
    other = make_user(email="other@example.com", name="Other")
    add_expense(uid, 5, description="mine")
    add_expense(other, 99, description="theirs")
    descs = [r["description"] for r in recent_for(uid)]
    assert descs == ["mine"]


def test_recent_empty_for_user_without_expenses(app):
    uid = make_user()
    other = make_user(email="other@example.com", name="Other")
    add_expense(other, 99)
    assert list(recent_for(uid)) == []


def test_profile_page_isolation_and_cap(app, client):
    uid = make_user()
    other = make_user(email="other@example.com", name="Other")
    for i in range(12):
        add_expense(uid, 10, when=day(i), description=f"mine{i}")
    add_expense(other, 77, description="SECRETITEM")
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "SECRETITEM" not in html
    assert "mine0" in html and "mine11" not in html
