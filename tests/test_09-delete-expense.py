"""Tests for Step 9: Delete Expense (spec 09-delete-expense).

The `app` fixture in conftest.py points database.db.DB_PATH at a per-test
temporary file, so the real spendly.db is never touched.
"""
import html as html_lib
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

import database.db as db

EMAIL = "asha@example.com"
PASSWORD = "secret123"
OTHER_EMAIL = "other@example.com"
OTHER_PASSWORD = "otherpass"
PROFILE_URL = "/profile"
TODAY = date.today().isoformat()


def delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


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


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def make_expense(
    user_id,
    amount=100.0,
    category="Food",
    date_str=TODAY,
    description="Original description",
):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date_str, description),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_expense(expense_id):
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, amount, category, date, description "
            "FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_expenses(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def count_users():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def profile_page(client):
    resp = client.get(PROFILE_URL)
    assert resp.status_code == 200, "Profile should render for logged-in user"
    return html_lib.unescape(resp.get_data(as_text=True))


@pytest.fixture
def user_id(app):
    return make_user()


@pytest.fixture
def other_user_id(app, user_id):
    return make_user(email=OTHER_EMAIL, password=OTHER_PASSWORD, name="Other Person")


@pytest.fixture
def auth_client(client, user_id):
    resp = login(client)
    assert resp.status_code in (200, 302), "Login helper failed"
    return client


@pytest.fixture
def expense_id(user_id):
    return make_expense(user_id, description="DeleteMeMarker")


@pytest.fixture
def other_expense_id(other_user_id):
    return make_expense(
        other_user_id,
        amount=55.0,
        category="Bills",
        description="Other users secret",
    )


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_post_logged_out_redirects_to_login(self, client, expense_id):
        resp = client.post(delete_url(expense_id))
        assert resp.status_code == 302, "Anonymous POST should redirect"
        assert "/login" in resp.headers["Location"]

    def test_post_logged_out_deletes_nothing(self, client, expense_id):
        client.post(delete_url(expense_id))
        assert get_expense(expense_id) is not None, "Row must survive anon POST"

    def test_post_logged_out_nonexistent_id_redirects_to_login(self, client, app):
        resp = client.post(delete_url(9999))
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# HTTP semantics: POST only                                           #
# ------------------------------------------------------------------ #

class TestMethods:
    def test_get_logged_in_returns_405(self, auth_client, expense_id):
        resp = auth_client.get(delete_url(expense_id))
        assert resp.status_code == 405, "GET must not be allowed"

    def test_get_logged_in_deletes_nothing(self, auth_client, expense_id):
        auth_client.get(delete_url(expense_id))
        assert get_expense(expense_id) is not None, "GET must never delete"

    @pytest.mark.parametrize("method", ["put", "patch", "delete"])
    def test_other_methods_not_allowed(self, auth_client, expense_id, method):
        resp = getattr(auth_client, method)(delete_url(expense_id))
        assert resp.status_code == 405, f"{method.upper()} should be 405"
        assert get_expense(expense_id) is not None

    def test_non_integer_id_returns_404(self, auth_client):
        resp = auth_client.post("/expenses/abc/delete")
        assert resp.status_code == 404, "Route requires an int id"


# ------------------------------------------------------------------ #
# Happy path and DB side effects                                      #
# ------------------------------------------------------------------ #

class TestDelete:
    def test_post_redirects_to_profile(self, auth_client, expense_id):
        resp = auth_client.post(delete_url(expense_id))
        assert resp.status_code == 302, "Expected PRG redirect"
        assert resp.headers["Location"].endswith("/profile")

    def test_post_removes_row(self, auth_client, expense_id):
        auth_client.post(delete_url(expense_id))
        assert get_expense(expense_id) is None, "Row should be deleted"

    def test_only_chosen_expense_removed(self, auth_client, user_id):
        target = make_expense(user_id, amount=10.0, description="TargetRow")
        keep1 = make_expense(user_id, amount=20.0, description="KeepRowOne")
        keep2 = make_expense(user_id, amount=30.0, category="Bills",
                             description="KeepRowTwo")
        before1, before2 = get_expense(keep1), get_expense(keep2)
        auth_client.post(delete_url(target))
        assert get_expense(target) is None
        assert get_expense(keep1) == before1, "Other expense changed"
        assert get_expense(keep2) == before2, "Other expense changed"
        assert count_expenses(user_id) == 2

    def test_other_users_rows_untouched(
        self, auth_client, expense_id, other_expense_id
    ):
        before = get_expense(other_expense_id)
        auth_client.post(delete_url(expense_id))
        assert get_expense(other_expense_id) == before

    def test_user_rows_not_deleted(self, auth_client, user_id, expense_id):
        users_before = count_users()
        auth_client.post(delete_url(expense_id))
        assert count_users() == users_before, "No user may be removed"

    def test_second_post_returns_404(self, auth_client, expense_id):
        first = auth_client.post(delete_url(expense_id))
        assert first.status_code == 302
        second = auth_client.post(delete_url(expense_id))
        assert second.status_code == 404, "Repeat delete should be 404"

    def test_user_id_in_form_is_ignored(
        self, auth_client, other_user_id, other_expense_id
    ):
        resp = auth_client.post(
            delete_url(other_expense_id), data={"user_id": str(other_user_id)}
        )
        assert resp.status_code == 404
        assert get_expense(other_expense_id) is not None

    def test_sql_injection_in_form_is_harmless(self, auth_client, expense_id):
        resp = auth_client.post(
            delete_url(expense_id), data={"id": "1 OR 1=1", "user_id": "' OR '1'='1"}
        )
        assert resp.status_code == 302
        assert get_expense(expense_id) is None


# ------------------------------------------------------------------ #
# 404 cases                                                           #
# ------------------------------------------------------------------ #

class TestNotFound:
    def test_nonexistent_id_returns_404(self, auth_client):
        resp = auth_client.post(delete_url(9999))
        assert resp.status_code == 404

    def test_other_users_expense_returns_404(self, auth_client, other_expense_id):
        resp = auth_client.post(delete_url(other_expense_id))
        assert resp.status_code == 404, "Foreign expense must be 404"

    def test_other_users_expense_still_exists(self, auth_client, other_expense_id):
        auth_client.post(delete_url(other_expense_id))
        assert get_expense(other_expense_id) is not None

    def test_foreign_and_missing_responses_identical(
        self, auth_client, other_expense_id
    ):
        foreign = auth_client.post(delete_url(other_expense_id))
        missing = auth_client.post(delete_url(other_expense_id + 1000))
        assert foreign.status_code == missing.status_code == 404
        assert foreign.get_data() == missing.get_data(), (
            "404 bodies must not reveal whether the id exists"
        )

    def test_failed_delete_does_not_change_row_count(
        self, auth_client, expense_id, other_expense_id
    ):
        before = count_expenses()
        auth_client.post(delete_url(other_expense_id))
        auth_client.post(delete_url(99999))
        assert count_expenses() == before


# ------------------------------------------------------------------ #
# Profile page                                                        #
# ------------------------------------------------------------------ #

class TestProfileIntegration:
    def test_profile_has_delete_form_for_each_expense(
        self, auth_client, user_id
    ):
        a = make_expense(user_id, description="RowA")
        b = make_expense(user_id, description="RowB")
        page = profile_page(auth_client)
        for eid in (a, b):
            assert delete_url(eid) in page, f"Delete action for {eid} missing"
        assert "Delete" in page, "Delete button label expected"
        assert 'method="post"' in page.lower(), "Delete must be a POST form"

    def test_profile_does_not_offer_delete_for_other_users(
        self, auth_client, expense_id, other_expense_id
    ):
        page = profile_page(auth_client)
        assert delete_url(other_expense_id) not in page

    def test_following_redirect_shows_profile(self, auth_client, expense_id):
        resp = auth_client.post(delete_url(expense_id), follow_redirects=True)
        assert resp.status_code == 200
        assert "Asha" in resp.get_data(as_text=True) or "Profile" in resp.get_data(
            as_text=True
        )

    def test_deleted_expense_disappears_from_transactions(
        self, auth_client, user_id
    ):
        gone = make_expense(user_id, description="VanishingMarker")
        make_expense(user_id, description="StaysMarker")
        assert "VanishingMarker" in profile_page(auth_client)
        auth_client.post(delete_url(gone))
        page = profile_page(auth_client)
        assert "VanishingMarker" not in page, "Deleted row still listed"
        assert "StaysMarker" in page, "Other row should remain"
        assert delete_url(gone) not in page

    def test_total_updates_after_delete(self, auth_client, user_id):
        big = make_expense(user_id, amount=7777.77, description="Big")
        make_expense(user_id, amount=11.0, description="Small")
        assert "7777.77" in profile_page(auth_client).replace(",", "")
        auth_client.post(delete_url(big))
        page = profile_page(auth_client).replace(",", "")
        assert "7777.77" not in page, "Total should drop the deleted amount"
        assert "7788.77" not in page

    def test_deleting_last_in_category_removes_it_from_breakdown(
        self, auth_client, user_id
    ):
        only_health = make_expense(user_id, category="Health", description="H")
        make_expense(user_id, category="Food", description="F")
        assert "Health" in profile_page(auth_client)
        auth_client.post(delete_url(only_health))
        page = profile_page(auth_client)
        assert "Health" not in page, "Empty category must leave the breakdown"
        assert "Food" in page

    def test_deleting_one_of_two_in_category_keeps_category(
        self, auth_client, user_id
    ):
        first = make_expense(user_id, category="Shopping", description="S1")
        make_expense(user_id, category="Shopping", description="S2")
        auth_client.post(delete_url(first))
        assert "Shopping" in profile_page(auth_client)

    def test_deleting_only_expense_shows_empty_state(
        self, auth_client, expense_id
    ):
        resp = auth_client.post(delete_url(expense_id), follow_redirects=True)
        assert resp.status_code == 200, "Empty profile must render without error"
        page = html_lib.unescape(resp.get_data(as_text=True))
        assert "DeleteMeMarker" not in page
        assert count_expenses() == 0

    def test_other_users_profile_unaffected(
        self, client, user_id, other_user_id, expense_id
    ):
        other_exp = make_expense(
            other_user_id, category="Entertainment", description="OtherKeepMarker"
        )
        login(client)
        client.post(delete_url(expense_id))
        client.get("/logout")
        login(client, OTHER_EMAIL, OTHER_PASSWORD)
        page = profile_page(client)
        assert "OtherKeepMarker" in page
        assert get_expense(other_exp) is not None


# ------------------------------------------------------------------ #
# Neighbouring flows still work                                       #
# ------------------------------------------------------------------ #

class TestRegression:
    def test_edit_page_still_loads(self, auth_client, expense_id):
        resp = auth_client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200

    def test_add_page_still_loads(self, auth_client):
        resp = auth_client.get("/expenses/add")
        assert resp.status_code == 200

    def test_add_then_delete_roundtrip(self, auth_client, user_id):
        resp = auth_client.post(
            "/expenses/add",
            data={
                "amount": "42.50",
                "category": "Food",
                "date": TODAY,
                "description": "RoundTripMarker",
            },
        )
        assert resp.status_code in (200, 302)
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT id FROM expenses WHERE description = ?", ("RoundTripMarker",)
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, "Add flow should have created the row"
        auth_client.post(delete_url(row["id"]))
        assert get_expense(row["id"]) is None
