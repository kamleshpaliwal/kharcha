from datetime import date

import database.db as db
from app import _get_summary
from tests.test_profile import add_expense, make_user


def summary_for(user_id):
    conn = db.get_db()
    try:
        return _get_summary(conn, user_id)
    finally:
        conn.close()


def previous_month_date():
    today = date.today()
    year, month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    return date(year, month, 15).isoformat()


def test_demo_style_totals(app):
    uid = make_user()
    amounts = [1200, 450.5, 800, 99.5, 1500, 300, 1360, 400]
    for i, amt in enumerate(amounts):
        add_expense(uid, amt, when=date.today().replace(day=1).isoformat())
    s = summary_for(uid)
    assert s["count"] == 8
    assert s["total"] == sum(amounts)
    assert s["month_total"] == sum(amounts)


def test_month_total_excludes_other_months(app):
    uid = make_user()
    add_expense(uid, 100)
    add_expense(uid, 250, when=previous_month_date())
    add_expense(uid, 999, when=date.today().replace(year=date.today().year - 1).isoformat())
    s = summary_for(uid)
    assert s["count"] == 3
    assert s["total"] == 1349
    assert s["month_total"] == 100


def test_no_expenses_gives_zeros(app):
    uid = make_user()
    assert summary_for(uid) == {"total": 0, "count": 0, "month_total": 0}


def test_user_isolation(app):
    a = make_user()
    b = make_user(email="b@example.com", name="Bo")
    add_expense(a, 100)
    add_expense(b, 5000)
    add_expense(b, 70, when=previous_month_date())
    assert summary_for(a) == {"total": 100, "count": 1, "month_total": 100}
    assert summary_for(b) == {"total": 5070, "count": 2, "month_total": 5000}
