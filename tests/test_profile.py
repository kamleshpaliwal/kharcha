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
