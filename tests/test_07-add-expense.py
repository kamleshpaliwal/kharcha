"""Tests for Step 7: Add Expense (spec 07-add-expense).

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
CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]
ADD_URL = "/expenses/add"


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


def all_expenses():
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT id, user_id, amount, category, date, description "
            "FROM expenses ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def valid_form(**overrides):
    data = {
        "amount": "250.50",
        "category": "Food",
        "date": "2025-03-15",
        "description": "Lunch with team",
    }
    data.update(overrides)
    return data


@pytest.fixture
def user_id(app):
    return make_user()


@pytest.fixture
def auth_client(client, user_id):
    resp = login(client)
    assert resp.status_code in (200, 302), "Login helper failed"
    return client


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        resp = client.get(ADD_URL)
        assert resp.status_code == 302, "Expected redirect for anonymous GET"
        assert "/login" in resp.headers["Location"]

    def test_post_logged_out_redirects_to_login(self, client):
        resp = client.post(ADD_URL, data=valid_form())
        assert resp.status_code == 302, "Expected redirect for anonymous POST"
        assert "/login" in resp.headers["Location"]

    def test_post_logged_out_saves_nothing(self, client, user_id):
        client.post(ADD_URL, data=valid_form())
        assert all_expenses() == [], "Anonymous POST must not create an expense"


# ------------------------------------------------------------------ #
# GET form                                                            #
# ------------------------------------------------------------------ #

class TestForm:
    def test_get_logged_in_returns_200(self, auth_client):
        resp = auth_client.get(ADD_URL)
        assert resp.status_code == 200

    def test_form_has_expected_fields(self, auth_client):
        page = auth_client.get(ADD_URL).get_data(as_text=True)
        assert "<form" in page
        assert 'method="post"' in page.lower()
        for field in ("amount", "category", "date", "description"):
            assert f'name="{field}"' in page, f"Missing field {field}"

    def test_form_lists_all_seven_categories(self, auth_client):
        page = auth_client.get(ADD_URL).get_data(as_text=True)
        for cat in CATEGORIES:
            assert cat in page, f"Category {cat} missing from form"

    def test_form_date_defaults_to_today(self, auth_client):
        page = auth_client.get(ADD_URL).get_data(as_text=True)
        assert date.today().isoformat() in page, "Date should default to today"

    def test_form_has_cancel_link_to_profile(self, auth_client):
        page = auth_client.get(ADD_URL).get_data(as_text=True)
        assert 'href="/profile"' in page, "Cancel link to profile expected"

    def test_profile_has_link_to_add_expense(self, auth_client):
        page = auth_client.get("/profile").get_data(as_text=True)
        assert ADD_URL in page, "Profile should link to the add-expense page"


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

class TestHappyPath:
    def test_valid_post_redirects_to_profile(self, auth_client):
        resp = auth_client.post(ADD_URL, data=valid_form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

    def test_valid_post_creates_row_for_session_user(self, auth_client, user_id):
        auth_client.post(ADD_URL, data=valid_form())
        rows = all_expenses()
        assert len(rows) == 1, "Exactly one expense expected"
        row = rows[0]
        assert row["user_id"] == user_id
        assert row["amount"] == pytest.approx(250.50)
        assert row["category"] == "Food"
        assert row["date"] == "2025-03-15"
        assert row["description"] == "Lunch with team"

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_listed_category_accepted(self, auth_client, category):
        resp = auth_client.post(ADD_URL, data=valid_form(category=category))
        assert resp.status_code == 302
        assert all_expenses()[0]["category"] == category

    def test_blank_description_accepted(self, auth_client):
        resp = auth_client.post(ADD_URL, data=valid_form(description=""))
        assert resp.status_code == 302
        rows = all_expenses()
        assert len(rows) == 1
        assert not rows[0]["description"], "Blank description should be stored empty"

    def test_missing_description_field_accepted(self, auth_client):
        data = valid_form()
        del data["description"]
        resp = auth_client.post(ADD_URL, data=data)
        assert resp.status_code == 302
        assert len(all_expenses()) == 1

    def test_whitespace_description_is_stripped(self, auth_client):
        auth_client.post(ADD_URL, data=valid_form(description="   Taxi   "))
        assert all_expenses()[0]["description"] == "Taxi"

    def test_description_of_exactly_200_chars_accepted(self, auth_client):
        desc = "d" * 200
        resp = auth_client.post(ADD_URL, data=valid_form(description=desc))
        assert resp.status_code == 302
        assert all_expenses()[0]["description"] == desc

    def test_amount_rounded_to_two_decimals(self, auth_client):
        auth_client.post(ADD_URL, data=valid_form(amount="10.126"))
        assert all_expenses()[0]["amount"] == pytest.approx(10.13)

    def test_integer_amount_accepted(self, auth_client):
        resp = auth_client.post(ADD_URL, data=valid_form(amount="100"))
        assert resp.status_code == 302
        assert all_expenses()[0]["amount"] == pytest.approx(100.0)

    def test_amount_with_surrounding_whitespace_accepted(self, auth_client):
        resp = auth_client.post(ADD_URL, data=valid_form(amount="  42.00 "))
        assert resp.status_code == 302
        assert all_expenses()[0]["amount"] == pytest.approx(42.0)

    def test_multiple_posts_create_multiple_rows(self, auth_client):
        auth_client.post(ADD_URL, data=valid_form(amount="10"))
        auth_client.post(ADD_URL, data=valid_form(amount="20"))
        assert len(all_expenses()) == 2


# ------------------------------------------------------------------ #
# Profile integration                                                 #
# ------------------------------------------------------------------ #

class TestProfileIntegration:
    def test_new_expense_appears_on_profile(self, auth_client):
        today = date.today().isoformat()
        auth_client.post(
            ADD_URL,
            data=valid_form(
                amount="777.00",
                category="Health",
                date=today,
                description="UniqueDescriptionXYZ",
            ),
        )
        page = auth_client.get("/profile").get_data(as_text=True)
        assert "UniqueDescriptionXYZ" in page, "Description missing on profile"
        assert "777" in page, "Amount missing on profile"
        assert "Health" in page, "Category missing on profile"

    def test_following_redirect_shows_profile_with_expense(self, auth_client):
        resp = auth_client.post(
            ADD_URL,
            data=valid_form(
                date=date.today().isoformat(), description="FollowedRedirectItem"
            ),
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "FollowedRedirectItem" in resp.get_data(as_text=True)

    def test_profile_total_reflects_new_expense(self, auth_client):
        today = date.today().isoformat()
        auth_client.post(ADD_URL, data=valid_form(amount="1234.00", date=today))
        page = auth_client.get("/profile").get_data(as_text=True)
        assert "1,234" in page, "Total should include the new expense"


# ------------------------------------------------------------------ #
# Amount validation                                                   #
# ------------------------------------------------------------------ #

BAD_AMOUNTS = ["", "   ", "0", "0.00", "-5", "-0.01", "abc", "12abc", "nan",
               "NaN", "inf", "-inf", "Infinity", "1e999"]


class TestAmountValidation:
    @pytest.mark.parametrize("amount", BAD_AMOUNTS)
    def test_bad_amount_returns_400(self, auth_client, amount):
        resp = auth_client.post(ADD_URL, data=valid_form(amount=amount))
        assert resp.status_code == 400, f"Amount {amount!r} should be rejected"

    @pytest.mark.parametrize("amount", BAD_AMOUNTS)
    def test_bad_amount_saves_nothing(self, auth_client, amount):
        auth_client.post(ADD_URL, data=valid_form(amount=amount))
        assert all_expenses() == [], f"Amount {amount!r} must not be saved"

    def test_missing_amount_field_rejected(self, auth_client):
        data = valid_form()
        del data["amount"]
        resp = auth_client.post(ADD_URL, data=data)
        assert resp.status_code == 400
        assert all_expenses() == []

    def test_error_message_is_shown(self, auth_client):
        resp = auth_client.post(ADD_URL, data=valid_form(amount="-5"))
        page = resp.get_data(as_text=True)
        assert "error" in page.lower() or "amount" in page.lower()
        assert "<form" in page, "Form should be re-rendered on error"


# ------------------------------------------------------------------ #
# Date validation                                                     #
# ------------------------------------------------------------------ #

BAD_DATES = ["", "   ", "not-a-date", "2025-13-01", "2025-02-30", "15/03/2025",
             "2025/03/15", "2025-3-5x", "0000-00-00"]


class TestDateValidation:
    @pytest.mark.parametrize("bad", BAD_DATES)
    def test_bad_date_returns_400_and_saves_nothing(self, auth_client, bad):
        resp = auth_client.post(ADD_URL, data=valid_form(date=bad))
        assert resp.status_code == 400, f"Date {bad!r} should be rejected"
        assert all_expenses() == []

    def test_missing_date_field_rejected(self, auth_client):
        data = valid_form()
        del data["date"]
        resp = auth_client.post(ADD_URL, data=data)
        assert resp.status_code == 400
        assert all_expenses() == []


# ------------------------------------------------------------------ #
# Category validation                                                 #
# ------------------------------------------------------------------ #

class TestCategoryValidation:
    @pytest.mark.parametrize(
        "bad", ["", "Groceries", "food", "FOOD", "Food ", "Rent", "<script>", "1"]
    )
    def test_invalid_category_rejected(self, auth_client, bad):
        resp = auth_client.post(ADD_URL, data=valid_form(category=bad))
        assert resp.status_code == 400, f"Category {bad!r} should be rejected"
        assert all_expenses() == []

    def test_missing_category_field_rejected(self, auth_client):
        data = valid_form()
        del data["category"]
        resp = auth_client.post(ADD_URL, data=data)
        assert resp.status_code == 400
        assert all_expenses() == []


# ------------------------------------------------------------------ #
# Description validation                                              #
# ------------------------------------------------------------------ #

class TestDescriptionValidation:
    def test_description_over_200_chars_rejected(self, auth_client):
        resp = auth_client.post(ADD_URL, data=valid_form(description="d" * 201))
        assert resp.status_code == 400
        assert all_expenses() == []

    def test_very_long_description_rejected(self, auth_client):
        resp = auth_client.post(ADD_URL, data=valid_form(description="d" * 5000))
        assert resp.status_code == 400
        assert all_expenses() == []


# ------------------------------------------------------------------ #
# Values preserved after errors                                       #
# ------------------------------------------------------------------ #

class TestFormPreservation:
    def test_values_preserved_after_amount_error(self, auth_client):
        resp = auth_client.post(
            ADD_URL,
            data=valid_form(
                amount="abc",
                category="Transport",
                date="2025-04-01",
                description="KeepMeDescription",
            ),
        )
        page = resp.get_data(as_text=True)
        assert resp.status_code == 400
        assert "abc" in page, "Entered amount should be preserved"
        assert "2025-04-01" in page, "Entered date should be preserved"
        assert "KeepMeDescription" in page, "Description should be preserved"

    def test_selected_category_preserved_after_error(self, auth_client):
        resp = auth_client.post(
            ADD_URL, data=valid_form(amount="0", category="Shopping")
        )
        page = resp.get_data(as_text=True)
        # The Shopping option should be the selected one.
        idx = page.index("Shopping")
        option_start = page.rfind("<option", 0, idx)
        option_tag = page[option_start:page.index(">", idx)]
        assert "selected" in option_tag, (
            "Shopping option should remain selected"
        )

    def test_values_preserved_after_date_error(self, auth_client):
        resp = auth_client.post(
            ADD_URL,
            data=valid_form(amount="99.99", date="bogus", description="StillHere"),
        )
        page = resp.get_data(as_text=True)
        assert "99.99" in page
        assert "StillHere" in page

    def test_values_preserved_after_long_description_error(self, auth_client):
        resp = auth_client.post(
            ADD_URL, data=valid_form(amount="55.55", description="x" * 201)
        )
        page = resp.get_data(as_text=True)
        assert "55.55" in page
        assert "x" * 201 in page, "Entered description should be preserved"

    def test_preserved_values_are_html_escaped(self, auth_client):
        payload = '"><script>alert(1)</script>'
        resp = auth_client.post(ADD_URL, data=valid_form(amount="-1", description=payload))
        page = resp.get_data(as_text=True)
        assert "<script>alert(1)</script>" not in page, "Input must be escaped"
        assert html_lib.escape(payload) in page or "&lt;script&gt;" in page


# ------------------------------------------------------------------ #
# Security and DB side effects                                        #
# ------------------------------------------------------------------ #

class TestSecurity:
    def test_forged_user_id_is_ignored(self, auth_client, user_id):
        other_id = make_user(email="other@example.com", name="Other Person")
        assert other_id != user_id
        resp = auth_client.post(ADD_URL, data=valid_form(user_id=str(other_id)))
        assert resp.status_code == 302
        rows = all_expenses()
        assert len(rows) == 1
        assert rows[0]["user_id"] == user_id, "Expense must belong to session user"

    def test_forged_nonexistent_user_id_is_ignored(self, auth_client, user_id):
        auth_client.post(ADD_URL, data=valid_form(user_id="99999"))
        rows = all_expenses()
        assert len(rows) == 1
        assert rows[0]["user_id"] == user_id

    def test_expense_not_visible_to_other_user(self, app, client, user_id):
        make_user(email="other@example.com", password="otherpass", name="Other")
        login(client)
        client.post(
            ADD_URL,
            data=valid_form(date=date.today().isoformat(), description="PrivateItemQQ"),
        )
        client.post("/logout")
        login(client, email="other@example.com", password="otherpass")
        page = client.get("/profile").get_data(as_text=True)
        assert "PrivateItemQQ" not in page

    def test_sql_injection_in_description_stored_literally(self, auth_client):
        payload = "'); DROP TABLE expenses; --"
        resp = auth_client.post(ADD_URL, data=valid_form(description=payload))
        assert resp.status_code == 302
        rows = all_expenses()
        assert len(rows) == 1
        assert rows[0]["description"] == payload

    def test_sql_injection_in_category_rejected(self, auth_client):
        resp = auth_client.post(
            ADD_URL, data=valid_form(category="Food'; DROP TABLE expenses; --")
        )
        assert resp.status_code == 400
        assert all_expenses() == []


class TestIsolation:
    def test_tests_use_temporary_database(self, app):
        import os

        assert "spendly.db" not in os.path.basename(db.DB_PATH), (
            "Tests must not use the real spendly.db"
        )
