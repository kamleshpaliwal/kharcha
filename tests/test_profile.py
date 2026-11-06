from datetime import date, timedelta

import database.db as db
from werkzeug.security import generate_password_hash

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


def add_expense(user_id, amount, category="Food", when=None, description="Item"):
    when = when or date.today().isoformat()
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, when, description),
        )
        conn.commit()
    finally:
        conn.close()


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def get_profile(client):
    resp = client.get("/profile")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def long_ago():
    return (date.today().replace(day=1) - timedelta(days=40)).isoformat()


def test_logged_out_redirects_to_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_stale_session_redirects_and_clears(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_header_shows_identity(client):
    make_user()
    login(client)
    html = get_profile(client)
    assert "Asha Rao" in html
    assert EMAIL in html
    assert f"Member since {date.today().strftime('%B %Y')}" in html


def test_summary_cards(client):
    uid = make_user()
    add_expense(uid, 1000, "Shopping")
    add_expense(uid, 250.5, "Food")
    add_expense(uid, 500, "Bills", when=long_ago())
    login(client)
    html = get_profile(client)
    assert "₹1,750.50" in html  # total
    assert "₹1,250.50" in html  # this month
    assert 'profile-stat-value">3<' in html  # count
    assert 'profile-stat-value">Shopping<' in html  # top category


def test_category_breakdown_order_and_percent(client):
    uid = make_user()
    add_expense(uid, 100, "Food")
    add_expense(uid, 300, "Bills")
    login(client)
    html = get_profile(client)
    assert html.index("Bills") < html.index('profile-cat-name">Food')
    assert "75.0%" in html
    assert "25.0%" in html


def test_recent_limited_to_ten_newest_first(client):
    uid = make_user()
    today = date.today()
    for i in range(12):
        add_expense(
            uid, 10 + i, "Food",
            when=(today - timedelta(days=i)).isoformat(),
            description=f"expense-{i:02d}",
        )
    login(client)
    html = get_profile(client)
    assert "expense-00" in html
    assert "expense-09" in html
    assert "expense-10" not in html
    assert "expense-11" not in html
    assert html.index("expense-00") < html.index("expense-09")


def test_empty_state(client):
    make_user()
    login(client)
    html = get_profile(client)
    assert "₹0.00" in html
    assert 'profile-stat-value">—<' in html
    assert "No expenses yet" in html


def test_user_sees_only_own_expenses(client):
    a = make_user()
    b = make_user(email="other@example.com", name="Other Person")
    add_expense(a, 111, "Food", description="mine-only")
    add_expense(b, 999, "Travel", description="theirs-only")
    login(client)
    html = get_profile(client)
    assert "mine-only" in html
    assert "theirs-only" not in html
    assert "₹999.00" not in html


def test_description_is_escaped(client):
    uid = make_user()
    add_expense(uid, 5, "Food", description="<script>alert(1)</script>")
    login(client)
    html = get_profile(client)
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_password_hash_never_rendered(client):
    make_user()
    login(client)
    html = get_profile(client)
    assert "password_hash" not in html
    assert "pbkdf2" not in html and "scrypt" not in html


def test_navbar_still_has_sign_out(client):
    make_user()
    login(client)
    assert "Sign out" in get_profile(client)


# ------------------------------------------------------------------ #
# Date filter (Step 6)                                                #
# ------------------------------------------------------------------ #

def filter_url(date_from, date_to):
    return f"/profile?date_from={date_from}&date_to={date_to}"


def seed_dated(uid):
    add_expense(uid, 100, "Food", "2026-01-10", "jan-early")
    add_expense(uid, 200, "Travel", "2026-01-20", "jan-late")
    add_expense(uid, 400, "Food", "2026-02-15", "feb-item")


def test_filter_absent_returns_all(client):
    uid = make_user()
    seed_dated(uid)
    login(client)
    html = get_profile(client)
    assert "₹700.00" in html
    assert "jan-early" in html and "feb-item" in html


def test_filter_applies_to_all_sections(client):
    uid = make_user()
    seed_dated(uid)
    login(client)
    resp = client.get(filter_url("2026-01-01", "2026-01-31"))
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "₹300.00" in html
    assert "jan-early" in html and "feb-item" not in html
    assert "66.7%" in html and "33.3%" in html  # Travel / Food of 300


def test_filter_bounds_are_inclusive(client):
    uid = make_user()
    seed_dated(uid)
    login(client)
    html = client.get(filter_url("2026-01-10", "2026-01-20")).get_data(as_text=True)
    assert "jan-early" in html and "jan-late" in html
    assert "₹300.00" in html


def test_filter_empty_range_shows_empty_state(client):
    uid = make_user()
    seed_dated(uid)
    login(client)
    html = client.get(filter_url("2020-01-01", "2020-01-31")).get_data(as_text=True)
    assert "₹0.00" in html
    assert "No expenses in this date range." in html


def test_filter_reversed_range_shows_error_and_all_data(client):
    uid = make_user()
    seed_dated(uid)
    login(client)
    html = client.get(filter_url("2026-02-01", "2026-01-01")).get_data(as_text=True)
    assert "Start date must be before end date." in html
    assert "₹700.00" in html


def test_filter_malformed_dates_fall_back(client):
    uid = make_user()
    seed_dated(uid)
    login(client)
    for query in (
        "date_from=not-a-date&date_to=2026-01-31",
        "date_from=' OR 1=1 --&date_to=2026-01-31",
        "date_from=2026-01-01",
    ):
        resp = client.get("/profile?" + query)
        assert resp.status_code == 200
        assert "₹700.00" in resp.get_data(as_text=True)


def test_filter_inputs_prefilled_and_active_preset(client):
    uid = make_user()
    seed_dated(uid)
    login(client)
    html = client.get(filter_url("2026-01-01", "2026-01-31")).get_data(as_text=True)
    assert 'value="2026-01-01"' in html and 'value="2026-01-31"' in html
    assert "is-active" not in html  # custom range matches no preset


def test_filter_all_time_preset_active_by_default(client):
    make_user()
    login(client)
    html = get_profile(client)
    assert 'is-active" href="/profile">All Time' in html


def test_filter_this_month_preset(client):
    uid = make_user()
    add_expense(uid, 50, "Food", description="now-item")
    add_expense(uid, 70, "Food", long_ago(), "old-item")
    login(client)
    today = date.today()
    start = today.replace(day=1).isoformat()
    html = client.get(filter_url(start, today.isoformat())).get_data(as_text=True)
    assert "now-item" in html and "old-item" not in html
    assert 'is-active" href="/profile?date_from=' in html


def test_filter_month_total_ignores_filter(client):
    uid = make_user()
    add_expense(uid, 50, "Food", description="now-item")
    login(client)
    html = client.get(filter_url("2020-01-01", "2020-01-31")).get_data(as_text=True)
    assert 'profile-stat-value">₹50.00<' in html


def test_filter_never_leaks_other_users(client):
    a = make_user()
    b = make_user(email="other@example.com", name="Other Person")
    add_expense(a, 10, "Food", "2026-01-10", "mine-only")
    add_expense(b, 999, "Travel", "2026-01-10", "theirs-only")
    login(client)
    html = client.get(filter_url("2026-01-01", "2026-01-31")).get_data(as_text=True)
    assert "mine-only" in html and "theirs-only" not in html


def test_filter_logged_out_redirects(client):
    resp = client.get(filter_url("2026-01-01", "2026-01-31"))
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_months_ago_clamps_day():
    from app import _months_ago

    assert _months_ago(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert _months_ago(date(2026, 1, 15), 3) == date(2025, 10, 15)
