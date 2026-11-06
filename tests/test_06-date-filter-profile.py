"""Tests for Step 6: date-range filter on GET /profile (spec 06-date-filter-profile)."""
import html as html_lib
import re
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

import database.db as db

EMAIL = "asha@example.com"
PASSWORD = "secret123"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

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
    if isinstance(when, date):
        when = when.isoformat()
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


def snapshot_expenses():
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT id, user_id, amount, category, date, description "
            "FROM expenses ORDER BY id"
        ).fetchall()
        return [tuple(r) for r in rows]
    finally:
        conn.close()


def get_profile(client, **params):
    resp = client.get("/profile", query_string=params)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    return resp.get_data(as_text=True)


def count_shown(page):
    m = re.search(r'profile-stat-value">(\d+)<', page)
    assert m, "Expected a transaction count on the page"
    return int(m.group(1))


def preset_href(page, label):
    """Return the href of the preset link whose visible text is `label`."""
    m = re.search(
        r'<a\b[^>]*href="([^"]*)"[^>]*>\s*' + re.escape(label) + r"\s*</a>", page
    )
    assert m, f"Expected a preset link labelled {label!r}"
    return html_lib.unescape(m.group(1))


def days_ago(n):
    return date.today() - timedelta(days=n)


@pytest.fixture
def user_client(client):
    uid = make_user()
    login(client)
    return client, uid


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_logged_out_with_filter_params_redirects_to_login(self, client):
        resp = client.get(
            "/profile", query_string={"date_from": "2024-01-01", "date_to": "2024-12-31"}
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_logged_out_with_malformed_params_redirects_to_login(self, client):
        resp = client.get("/profile", query_string={"date_from": "garbage"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")


# ------------------------------------------------------------------ #
# Unfiltered behaviour                                                #
# ------------------------------------------------------------------ #

class TestUnfiltered:
    def test_no_params_shows_all_expenses(self, user_client):
        client, uid = user_client
        add_expense(uid, 100, description="zzold-one", when="2020-01-15")
        add_expense(uid, 200, description="zznew-one")
        page = get_profile(client)
        assert "zzold-one" in page
        assert "zznew-one" in page
        assert count_shown(page) == 2
        assert "₹300.00" in page

    def test_filter_bar_has_date_inputs_and_apply(self, user_client):
        client, _ = user_client
        page = get_profile(client)
        assert 'type="date"' in page
        assert 'name="date_from"' in page
        assert 'name="date_to"' in page
        assert "Apply" in page

    def test_filter_bar_has_all_four_presets(self, user_client):
        client, _ = user_client
        page = get_profile(client)
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            assert label in page, f"Missing preset {label}"

    def test_no_error_message_without_params(self, user_client):
        client, _ = user_client
        page = get_profile(client)
        assert "Start date must be before end date." not in page


# ------------------------------------------------------------------ #
# Custom range                                                        #
# ------------------------------------------------------------------ #

class TestCustomRange:
    def test_range_filters_transactions(self, user_client):
        client, uid = user_client
        add_expense(uid, 10, description="zzbefore", when="2023-05-31")
        add_expense(uid, 20, description="zzinside", when="2023-06-15")
        add_expense(uid, 30, description="zzafter", when="2023-07-01")
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "zzinside" in page
        assert "zzbefore" not in page
        assert "zzafter" not in page

    def test_range_filters_summary_total_and_count(self, user_client):
        client, uid = user_client
        add_expense(uid, 10, when="2023-05-31")
        add_expense(uid, 20, when="2023-06-15")
        add_expense(uid, 35.5, when="2023-06-20")
        add_expense(uid, 30, when="2023-07-01")
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "₹55.50" in page
        assert count_shown(page) == 2

    def test_range_filters_category_breakdown(self, user_client):
        client, uid = user_client
        add_expense(uid, 75, category="Travel", when="2023-06-10")
        add_expense(uid, 25, category="Food", when="2023-06-11")
        add_expense(uid, 900, category="Entertainment", when="2023-01-11")
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "Travel" in page
        assert "Food" in page
        assert "Entertainment" not in page
        assert "75.0%" in page
        assert "25.0%" in page

    def test_lower_bound_is_inclusive(self, user_client):
        client, uid = user_client
        add_expense(uid, 10, description="zzlowerbound", when="2023-06-01")
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "zzlowerbound" in page

    def test_upper_bound_is_inclusive(self, user_client):
        client, uid = user_client
        add_expense(uid, 10, description="zzupperbound", when="2023-06-30")
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "zzupperbound" in page

    def test_single_day_range_includes_that_day_only(self, user_client):
        client, uid = user_client
        add_expense(uid, 10, description="zzday-before", when="2023-06-14")
        add_expense(uid, 20, description="zzthe-day", when="2023-06-15")
        add_expense(uid, 30, description="zzday-after", when="2023-06-16")
        page = get_profile(client, date_from="2023-06-15", date_to="2023-06-15")
        assert "zzthe-day" in page
        assert "zzday-before" not in page
        assert "zzday-after" not in page
        assert count_shown(page) == 1

    def test_active_range_reflected_in_date_inputs(self, user_client):
        client, _ = user_client
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "2023-06-01" in page
        assert "2023-06-30" in page

    def test_amounts_keep_rupee_symbol_when_filtered(self, user_client):
        client, uid = user_client
        add_expense(uid, 1234.5, category="Bills", when="2023-06-10")
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "₹1,234.50" in page
        assert page.count("₹") >= 3, "Expected rupee symbol on total and rows"

    def test_filtering_does_not_modify_data(self, user_client):
        client, uid = user_client
        add_expense(uid, 10, when="2023-05-31")
        add_expense(uid, 20, when="2023-06-15")
        before = snapshot_expenses()
        get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        get_profile(client, date_from="2030-01-01", date_to="2030-01-02")
        get_profile(client, date_from="2023-06-30", date_to="2023-06-01")
        assert snapshot_expenses() == before

    def test_other_users_expenses_never_leak(self, client):
        uid = make_user()
        other = make_user(email="bob@example.com", name="Bob Other")
        add_expense(uid, 20, description="zzmine", when="2023-06-15")
        add_expense(other, 9999, description="zztheirs", category="Secret", when="2023-06-15")
        login(client)
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "zzmine" in page
        assert "zztheirs" not in page
        assert "Secret" not in page
        assert "₹9,999.00" not in page
        assert count_shown(page) == 1

    def test_sql_injection_in_dates_is_harmless(self, user_client):
        client, uid = user_client
        add_expense(uid, 20, description="zzsafe", when="2023-06-15")
        before = snapshot_expenses()
        resp = client.get(
            "/profile",
            query_string={
                "date_from": "2023-01-01'; DROP TABLE expenses;--",
                "date_to": "2023-12-31' OR '1'='1",
            },
        )
        assert resp.status_code == 200
        assert snapshot_expenses() == before


# ------------------------------------------------------------------ #
# Empty range                                                         #
# ------------------------------------------------------------------ #

class TestEmptyRange:
    def test_empty_range_shows_zero_total_and_zero_count(self, user_client):
        client, uid = user_client
        add_expense(uid, 500, description="zzoutside", when="2023-06-15")
        page = get_profile(client, date_from="2021-01-01", date_to="2021-01-31")
        assert "₹0.00" in page
        assert count_shown(page) == 0
        assert "zzoutside" not in page

    def test_empty_range_has_empty_category_breakdown(self, user_client):
        client, uid = user_client
        add_expense(uid, 500, category="Travel", when="2023-06-15")
        page = get_profile(client, date_from="2021-01-01", date_to="2021-01-31")
        assert 'class="profile-cat-row"' not in page
        assert "Travel" not in page

    def test_future_range_is_empty_without_error(self, user_client):
        client, uid = user_client
        add_expense(uid, 500, when="2023-06-15")
        resp = client.get(
            "/profile", query_string={"date_from": "2999-01-01", "date_to": "2999-12-31"}
        )
        assert resp.status_code == 200
        assert count_shown(resp.get_data(as_text=True)) == 0

    def test_user_with_no_expenses_at_all_is_fine(self, user_client):
        client, _ = user_client
        page = get_profile(client, date_from="2023-06-01", date_to="2023-06-30")
        assert "₹0.00" in page
        assert count_shown(page) == 0


# ------------------------------------------------------------------ #
# Malformed / missing / reversed                                      #
# ------------------------------------------------------------------ #

class TestInvalidInput:
    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "not-a-date", "date_to": "2023-06-30"},
            {"date_from": "2023-06-01", "date_to": "not-a-date"},
            {"date_from": "not-a-date", "date_to": "also-bad"},
            {"date_from": "2023-13-01", "date_to": "2023-06-30"},
            {"date_from": "2023-02-30", "date_to": "2023-06-30"},
            {"date_from": "06/01/2023", "date_to": "06/30/2023"},
            {"date_from": "", "date_to": ""},
            {"date_from": "<script>alert(1)</script>", "date_to": "2023-06-30"},
        ],
    )
    def test_malformed_dates_fall_back_to_unfiltered(self, user_client, params):
        client, uid = user_client
        add_expense(uid, 10, description="zzold", when="2020-01-01")
        add_expense(uid, 20, description="zzrecent", when="2023-06-15")
        resp = client.get("/profile", query_string=params)
        assert resp.status_code == 200, "Malformed dates must not crash the app"
        page = resp.get_data(as_text=True)
        assert "zzold" in page
        assert "zzrecent" in page
        assert count_shown(page) == 2
        assert "<script>alert(1)</script>" not in page

    @pytest.mark.parametrize("param", ["date_from", "date_to"])
    def test_only_one_bound_falls_back_to_unfiltered(self, user_client, param):
        client, uid = user_client
        add_expense(uid, 10, description="zzold", when="2020-01-01")
        add_expense(uid, 20, description="zzrecent", when="2023-06-15")
        page = get_profile(client, **{param: "2023-06-01"})
        assert "zzold" in page
        assert "zzrecent" in page
        assert count_shown(page) == 2

    def test_malformed_dates_show_no_error_message(self, user_client):
        client, _ = user_client
        page = get_profile(client, date_from="not-a-date", date_to="2023-06-30")
        assert "Start date must be before end date." not in page

    def test_reversed_range_falls_back_to_unfiltered(self, user_client):
        client, uid = user_client
        add_expense(uid, 10, description="zzold", when="2020-01-01")
        add_expense(uid, 20, description="zzrecent", when="2023-06-15")
        page = get_profile(client, date_from="2023-06-30", date_to="2023-06-01")
        assert "zzold" in page
        assert "zzrecent" in page
        assert count_shown(page) == 2
        assert "₹30.00" in page

    def test_reversed_range_shows_error_message(self, user_client):
        client, _ = user_client
        page = get_profile(client, date_from="2023-06-30", date_to="2023-06-01")
        assert "Start date must be before end date." in page

    def test_reversed_range_error_not_sticky_on_next_request(self, user_client):
        client, _ = user_client
        get_profile(client, date_from="2023-06-30", date_to="2023-06-01")
        page = get_profile(client)
        assert "Start date must be before end date." not in page

    def test_equal_dates_are_not_an_error(self, user_client):
        client, _ = user_client
        page = get_profile(client, date_from="2023-06-15", date_to="2023-06-15")
        assert "Start date must be before end date." not in page


# ------------------------------------------------------------------ #
# Presets (data placed relative to today)                             #
# ------------------------------------------------------------------ #

class TestPresets:
    @pytest.fixture
    def seeded(self, user_client):
        """Expenses at 0, 45, 120 and 250 days ago plus one far in the past.

        0 days   -> This Month, 3M, 6M
        45 days  -> 3M, 6M (never in the current calendar month)
        120 days -> 6M only
        250 days -> outside 6M
        """
        client, uid = user_client
        add_expense(uid, 1, description="zzd0", when=days_ago(0))
        add_expense(uid, 2, description="zzd45", when=days_ago(45))
        add_expense(uid, 4, description="zzd120", when=days_ago(120))
        add_expense(uid, 8, description="zzd250", when=days_ago(250))
        add_expense(uid, 16, description="zzancient", when="2015-03-03")
        return client

    def follow_preset(self, client, label):
        base = get_profile(client)
        href = preset_href(base, label)
        resp = client.get(href)
        assert resp.status_code == 200
        return resp.get_data(as_text=True)

    def test_this_month_preset_link_starts_on_first_of_month(self, seeded):
        href = preset_href(get_profile(seeded), "This Month")
        first = date.today().replace(day=1).isoformat()
        assert f"date_from={first}" in href
        assert f"date_to={date.today().isoformat()}" in href

    def test_this_month_preset_filters_to_current_month(self, seeded):
        page = self.follow_preset(seeded, "This Month")
        assert "zzd0" in page
        for gone in ("zzd45", "zzd120", "zzd250", "zzancient"):
            assert gone not in page
        assert count_shown(page) == 1

    def test_last_3_months_preset(self, seeded):
        page = self.follow_preset(seeded, "Last 3 Months")
        assert "zzd0" in page
        assert "zzd45" in page
        for gone in ("zzd120", "zzd250", "zzancient"):
            assert gone not in page
        assert count_shown(page) == 2
        assert "₹3.00" in page

    def test_last_6_months_preset(self, seeded):
        page = self.follow_preset(seeded, "Last 6 Months")
        for kept in ("zzd0", "zzd45", "zzd120"):
            assert kept in page
        for gone in ("zzd250", "zzancient"):
            assert gone not in page
        assert count_shown(page) == 3
        assert "₹7.00" in page

    def test_last_3_and_6_month_presets_end_today(self, seeded):
        base = get_profile(seeded)
        for label in ("Last 3 Months", "Last 6 Months"):
            href = preset_href(base, label)
            assert f"date_to={date.today().isoformat()}" in href, label

    def test_all_time_preset_is_clean_profile_url(self, seeded):
        href = preset_href(get_profile(seeded), "All Time")
        assert "date_from" not in href
        assert "date_to" not in href
        assert "?" not in href
        assert href.rstrip("/").endswith("/profile")

    def test_all_time_preset_shows_everything(self, seeded):
        page = self.follow_preset(seeded, "All Time")
        for kept in ("zzd0", "zzd45", "zzd120", "zzd250", "zzancient"):
            assert kept in page
        assert count_shown(page) == 5

    def test_future_dated_expense_excluded_from_presets_ending_today(self, user_client):
        client, uid = user_client
        add_expense(uid, 5, description="zzfuture", when=days_ago(-30))
        add_expense(uid, 5, description="zztoday", when=days_ago(0))
        base = get_profile(client)
        page = client.get(preset_href(base, "Last 3 Months")).get_data(as_text=True)
        assert "zztoday" in page
        assert "zzfuture" not in page

    def test_expense_dated_today_included_in_this_month(self, user_client):
        client, uid = user_client
        add_expense(uid, 5, description="zztoday")
        base = get_profile(client)
        page = client.get(preset_href(base, "This Month")).get_data(as_text=True)
        assert "zztoday" in page

    def test_preset_with_no_matching_data_shows_empty_state(self, user_client):
        client, uid = user_client
        add_expense(uid, 99, description="zzancient", when="2015-03-03")
        base = get_profile(client)
        page = client.get(preset_href(base, "This Month")).get_data(as_text=True)
        assert "₹0.00" in page
        assert count_shown(page) == 0
        assert "zzancient" not in page

    def test_active_preset_is_highlighted(self, seeded):
        """The active preset's link should carry an 'active' class."""
        page = self.follow_preset(seeded, "Last 3 Months")
        active = re.search(
            r'<a\b[^>]*class="[^"]*active[^"]*"[^>]*>\s*([^<]+?)\s*</a>', page
        )
        assert active, "Expected an active preset link"
        assert active.group(1) == "Last 3 Months"

    def test_all_time_highlighted_when_unfiltered(self, seeded):
        page = get_profile(seeded)
        active = re.search(
            r'<a\b[^>]*class="[^"]*active[^"]*"[^>]*>\s*([^<]+?)\s*</a>', page
        )
        assert active, "Expected All Time to be active with no filter"
        assert active.group(1) == "All Time"

    def test_presets_do_not_leak_other_users_data(self, client):
        uid = make_user()
        other = make_user(email="bob@example.com", name="Bob Other")
        add_expense(uid, 5, description="zzmine")
        add_expense(other, 777, description="zztheirs")
        login(client)
        base = get_profile(client)
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            page = client.get(preset_href(base, label)).get_data(as_text=True)
            assert "zztheirs" not in page, label
            assert "₹777.00" not in page, label
            assert "zzmine" in page, label
