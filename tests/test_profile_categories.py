import database.db as db
from app import _get_category_breakdown

from tests.test_profile import add_expense, make_user


def breakdown(user_id):
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS t FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return _get_category_breakdown(conn, user_id, row["t"])
    finally:
        conn.close()


def test_ordered_by_total_desc(app):
    uid = make_user()
    add_expense(uid, 100, "Food")
    add_expense(uid, 300, "Rent")
    add_expense(uid, 200, "Travel")
    assert [c["category"] for c in breakdown(uid)] == ["Rent", "Travel", "Food"]


def test_tie_broken_by_category_name(app):
    uid = make_user()
    add_expense(uid, 100, "Travel")
    add_expense(uid, 100, "Food")
    add_expense(uid, 100, "Bills")
    assert [c["category"] for c in breakdown(uid)] == ["Bills", "Food", "Travel"]


def test_totals_aggregate_per_category(app):
    uid = make_user()
    add_expense(uid, 40, "Food")
    add_expense(uid, 60, "Food")
    result = breakdown(uid)
    assert len(result) == 1
    assert result[0]["total"] == 100
    assert result[0]["percent"] == 100


def test_percentages_sum_to_about_100(app):
    uid = make_user()
    add_expense(uid, 100, "Food")
    add_expense(uid, 100, "Rent")
    add_expense(uid, 100, "Travel")
    result = breakdown(uid)
    assert abs(sum(c["percent"] for c in result) - 100) < 0.5


def test_no_expenses_returns_empty_list(app):
    uid = make_user()
    assert breakdown(uid) == []


def test_zero_total_does_not_divide_by_zero(app):
    uid = make_user()
    add_expense(uid, 0, "Food")
    result = breakdown(uid)
    assert result[0]["percent"] == 0


def test_user_isolation(app):
    a = make_user()
    b = make_user(email="other@example.com", name="Other")
    add_expense(a, 100, "Food")
    add_expense(b, 900, "Shopping")
    result = breakdown(a)
    assert [c["category"] for c in result] == ["Food"]
    assert result[0]["percent"] == 100
