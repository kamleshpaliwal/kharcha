"""Tests for Step 8: Edit Expense (spec 08-edit-expense).

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
PROFILE_URL = "/profile"
TODAY = date.today().isoformat()


def edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


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
            "SELECT id, user_id, amount, category, date, description, created_at "
            "FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def valid_form(**overrides):
    data = {
        "amount": "321.75",
        "category": "Transport",
        "date": "2025-05-20",
        "description": "Edited description",
    }
    data.update(overrides)
    return data


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
    return make_expense(user_id)


@pytest.fixture
def other_expense_id(other_user_id):
    return make_expense(
        other_user_id,
        amount=55.0,
        category="Bills",
        date_str="2025-01-02",
        description="Other users secret",
    )


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client, expense_id):
        resp = client.get(edit_url(expense_id))
        assert resp.status_code == 302, "Expected redirect for anonymous GET"
        assert "/login" in resp.headers["Location"]

    def test_post_logged_out_redirects_to_login(self, client, expense_id):
        resp = client.post(edit_url(expense_id), data=valid_form())
        assert resp.status_code == 302, "Expected redirect for anonymous POST"
        assert "/login" in resp.headers["Location"]

    def test_post_logged_out_does_not_modify_row(self, client, expense_id):
        before = get_expense(expense_id)
        client.post(edit_url(expense_id), data=valid_form())
        assert get_expense(expense_id) == before, "Anonymous POST changed the row"

    def test_logged_out_nonexistent_id_still_redirects(self, client, app):
        resp = client.get(edit_url(99999))
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# GET form                                                            #
# ------------------------------------------------------------------ #

class TestForm:
    def test_get_returns_200(self, auth_client, expense_id):
        assert auth_client.get(edit_url(expense_id)).status_code == 200

    def test_form_has_expected_fields(self, auth_client, expense_id):
        page = auth_client.get(edit_url(expense_id)).get_data(as_text=True)
        assert "<form" in page
        assert 'method="post"' in page.lower()
        for field in ("amount", "category", "date", "description"):
            assert f'name="{field}"' in page, f"Missing field {field}"

    def test_form_posts_to_edit_url(self, auth_client, expense_id):
        page = auth_client.get(edit_url(expense_id)).get_data(as_text=True)
        assert edit_url(expense_id) in page, "Form action should be the edit URL"

    def test_form_lists_all_seven_categories(self, auth_client, expense_id):
        page = auth_client.get(edit_url(expense_id)).get_data(as_text=True)
        for cat in CATEGORIES:
            assert cat in page, f"Category {cat} missing from form"

    def test_form_prefilled_with_stored_values(self, auth_client, user_id):
        eid = make_expense(
            user_id,
            amount=1234.5,
            category="Health",
            date_str="2024-11-30",
            description="PrefillMarkerText",
        )
        page = auth_client.get(edit_url(eid)).get_data(as_text=True)
        assert "1234.5" in page, "Stored amount should pre-fill the form"
        assert "2024-11-30" in page, "Stored date should pre-fill the form"
        assert "PrefillMarkerText" in page, "Stored description should pre-fill"

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_stored_category_is_selected(self, auth_client, user_id, category):
        eid = make_expense(user_id, category=category)
        page = auth_client.get(edit_url(eid)).get_data(as_text=True)
        selected = [
            seg for seg in page.split("<option")[1:]
            if "selected" in seg.split(">")[0]
        ]
        assert len(selected) == 1, "Exactly one option should be selected"
        assert category in selected[0].split("</option>")[0], (
            f"{category} should be the selected option"
        )

    def test_null_description_shows_empty(self, auth_client, user_id):
        conn = db.get_db()
        try:
            cur = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, NULL)",
                (user_id, 10.0, "Food", TODAY),
            )
            conn.commit()
            eid = cur.lastrowid
        finally:
            conn.close()
        resp = auth_client.get(edit_url(eid))
        assert resp.status_code == 200
        assert "None" not in resp.get_data(as_text=True), (
            "NULL description must render as empty, not 'None'"
        )

    def test_stored_description_is_html_escaped(self, auth_client, user_id):
        payload = "<script>alert(1)</script>"
        eid = make_expense(user_id, description=payload)
        page = auth_client.get(edit_url(eid)).get_data(as_text=True)
        assert payload not in page, "Stored description must be escaped"
        assert html_lib.escape(payload) in page or "&lt;script&gt;" in page

    def test_get_does_not_modify_row(self, auth_client, expense_id):
        before = get_expense(expense_id)
        auth_client.get(edit_url(expense_id))
        assert get_expense(expense_id) == before

    def test_form_has_cancel_link_to_profile(self, auth_client, expense_id):
        page = auth_client.get(edit_url(expense_id)).get_data(as_text=True)
        assert 'href="/profile"' in page, "Cancel link to profile expected"


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

class TestHappyPath:
    def test_valid_post_redirects_to_profile(self, auth_client, expense_id):
        resp = auth_client.post(edit_url(expense_id), data=valid_form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

    def test_valid_post_updates_row(self, auth_client, expense_id, user_id):
        auth_client.post(edit_url(expense_id), data=valid_form())
        row = get_expense(expense_id)
        assert row["amount"] == pytest.approx(321.75)
        assert row["category"] == "Transport"
        assert row["date"] == "2025-05-20"
        assert row["description"] == "Edited description"
        assert row["user_id"] == user_id

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_listed_category_accepted(self, auth_client, user_id, category):
        eid = make_expense(user_id, category="Food")
        resp = auth_client.post(edit_url(eid), data=valid_form(category=category))
        assert resp.status_code == 302
        assert get_expense(eid)["category"] == category

    def test_blank_description_accepted(self, auth_client, expense_id):
        resp = auth_client.post(edit_url(expense_id), data=valid_form(description=""))
        assert resp.status_code == 302
        assert not get_expense(expense_id)["description"], (
            "Blank description should be stored empty"
        )

    def test_missing_description_field_accepted(self, auth_client, expense_id):
        data = valid_form()
        del data["description"]
        resp = auth_client.post(edit_url(expense_id), data=data)
        assert resp.status_code == 302

    def test_whitespace_description_is_stripped(self, auth_client, expense_id):
        auth_client.post(edit_url(expense_id), data=valid_form(description="  Taxi  "))
        assert get_expense(expense_id)["description"] == "Taxi"

    def test_description_of_exactly_200_chars_accepted(self, auth_client, expense_id):
        desc = "d" * 200
        resp = auth_client.post(edit_url(expense_id), data=valid_form(description=desc))
        assert resp.status_code == 302
        assert get_expense(expense_id)["description"] == desc

    def test_integer_amount_accepted(self, auth_client, expense_id):
        resp = auth_client.post(edit_url(expense_id), data=valid_form(amount="100"))
        assert resp.status_code == 302
        assert get_expense(expense_id)["amount"] == pytest.approx(100.0)

    def test_amount_rounded_to_two_decimals(self, auth_client, expense_id):
        auth_client.post(edit_url(expense_id), data=valid_form(amount="10.126"))
        assert get_expense(expense_id)["amount"] == pytest.approx(10.13)

    def test_unchanged_resubmit_keeps_values(self, auth_client, user_id):
        eid = make_expense(
            user_id, amount=42.0, category="Bills", date_str="2025-02-02",
            description="Same",
        )
        resp = auth_client.post(
            edit_url(eid),
            data={"amount": "42.00", "category": "Bills",
                  "date": "2025-02-02", "description": "Same"},
        )
        assert resp.status_code == 302
        row = get_expense(eid)
        assert row["amount"] == pytest.approx(42.0)
        assert row["category"] == "Bills"
        assert row["date"] == "2025-02-02"
        assert row["description"] == "Same"

    def test_only_target_expense_is_modified(self, auth_client, user_id, expense_id):
        sibling = make_expense(user_id, amount=7.0, description="Sibling")
        before = get_expense(sibling)
        auth_client.post(edit_url(expense_id), data=valid_form())
        assert get_expense(sibling) == before, "Other expenses must be untouched"

    def test_edit_does_not_change_row_count(self, auth_client, expense_id):
        before = count_expenses()
        auth_client.post(edit_url(expense_id), data=valid_form())
        assert count_expenses() == before == 1

    def test_edit_keeps_created_at_and_id(self, auth_client, expense_id):
        before = get_expense(expense_id)
        auth_client.post(edit_url(expense_id), data=valid_form())
        after = get_expense(expense_id)
        assert after["created_at"] == before["created_at"]
        assert after["id"] == before["id"]


# ------------------------------------------------------------------ #
# Profile integration                                                 #
# ------------------------------------------------------------------ #

class TestProfileIntegration:
    def test_profile_has_edit_link_for_each_expense(self, auth_client, user_id):
        ids = [make_expense(user_id, description=f"row{i}") for i in range(3)]
        page = auth_client.get(PROFILE_URL).get_data(as_text=True)
        assert "Edit" in page, "Edit label expected on profile"
        for eid in ids:
            assert f'href="{edit_url(eid)}"' in page, (
                f"Edit link for expense {eid} missing"
            )

    def test_profile_does_not_link_to_other_users_expense(
        self, auth_client, expense_id, other_expense_id
    ):
        page = auth_client.get(PROFILE_URL).get_data(as_text=True)
        assert edit_url(other_expense_id) not in page

    def test_edit_link_opens_form(self, auth_client, expense_id):
        resp = auth_client.get(edit_url(expense_id))
        assert resp.status_code == 200
        assert 'name="amount"' in resp.get_data(as_text=True)

    def test_updated_values_appear_in_recent_transactions(
        self, auth_client, expense_id
    ):
        auth_client.post(
            edit_url(expense_id),
            data=valid_form(
                amount="777.00", category="Health", date=TODAY,
                description="UpdatedMarkerXYZ",
            ),
        )
        page = auth_client.get(PROFILE_URL).get_data(as_text=True)
        assert "UpdatedMarkerXYZ" in page, "New description missing on profile"
        assert "777" in page, "New amount missing on profile"
        assert "Original description" not in page, "Old description still shown"

    def test_following_redirect_shows_profile(self, auth_client, expense_id):
        resp = auth_client.post(
            edit_url(expense_id),
            data=valid_form(date=TODAY, description="FollowedRedirectItem"),
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "FollowedRedirectItem" in resp.get_data(as_text=True)

    def test_profile_total_reflects_edit(self, auth_client, expense_id):
        auth_client.post(
            edit_url(expense_id), data=valid_form(amount="1234.00", date=TODAY)
        )
        page = auth_client.get(PROFILE_URL).get_data(as_text=True)
        assert "1,234" in page, "Total should reflect the edited amount"

    def test_category_change_moves_amount_in_breakdown(self, auth_client, user_id):
        eid = make_expense(user_id, amount=500.0, category="Food", description="x")
        before = auth_client.get(PROFILE_URL).get_data(as_text=True)
        assert "Health" not in before, "Precondition: no Health spend yet"
        food_before = before.count("Food")
        auth_client.post(
            edit_url(eid),
            data=valid_form(amount="500", category="Health", date=TODAY,
                            description="x"),
        )
        after = auth_client.get(PROFILE_URL).get_data(as_text=True)
        assert "Health" in after, "Health should appear after category change"
        assert after.count("Food") < food_before, (
            "Food should no longer be listed for the moved amount"
        )


# ------------------------------------------------------------------ #
# Amount validation                                                   #
# ------------------------------------------------------------------ #

BAD_AMOUNTS = ["", "   ", "0", "0.00", "-5", "-0.01", "abc", "12abc", "nan",
               "NaN", "inf", "-inf", "Infinity", "1e999"]


class TestAmountValidation:
    @pytest.mark.parametrize("amount", BAD_AMOUNTS)
    def test_bad_amount_returns_400(self, auth_client, expense_id, amount):
        resp = auth_client.post(edit_url(expense_id), data=valid_form(amount=amount))
        assert resp.status_code == 400, f"Amount {amount!r} should be rejected"

    @pytest.mark.parametrize("amount", BAD_AMOUNTS)
    def test_bad_amount_leaves_row_unchanged(self, auth_client, expense_id, amount):
        before = get_expense(expense_id)
        auth_client.post(edit_url(expense_id), data=valid_form(amount=amount))
        assert get_expense(expense_id) == before, (
            f"Amount {amount!r} must not modify the row"
        )

    def test_missing_amount_field_rejected(self, auth_client, expense_id):
        before = get_expense(expense_id)
        data = valid_form()
        del data["amount"]
        resp = auth_client.post(edit_url(expense_id), data=data)
        assert resp.status_code == 400
        assert get_expense(expense_id) == before

    def test_error_message_shown_and_form_rerendered(self, auth_client, expense_id):
        resp = auth_client.post(edit_url(expense_id), data=valid_form(amount="-5"))
        page = resp.get_data(as_text=True)
        assert "error" in page.lower() or "amount" in page.lower()
        assert "<form" in page, "Form should be re-rendered on error"


# ------------------------------------------------------------------ #
# Date / category / description validation                            #
# ------------------------------------------------------------------ #

BAD_DATES = ["", "   ", "not-a-date", "2025-13-01", "2025-02-30", "15/03/2025",
             "2025/03/15", "2025-3-5x", "0000-00-00"]
BAD_CATEGORIES = ["", "Groceries", "food", "FOOD", "Food ", "Rent", "<script>", "1"]


class TestOtherValidation:
    @pytest.mark.parametrize("bad", BAD_DATES)
    def test_bad_date_returns_400_and_row_unchanged(
        self, auth_client, expense_id, bad
    ):
        before = get_expense(expense_id)
        resp = auth_client.post(edit_url(expense_id), data=valid_form(date=bad))
        assert resp.status_code == 400, f"Date {bad!r} should be rejected"
        assert get_expense(expense_id) == before

    def test_missing_date_field_rejected(self, auth_client, expense_id):
        before = get_expense(expense_id)
        data = valid_form()
        del data["date"]
        resp = auth_client.post(edit_url(expense_id), data=data)
        assert resp.status_code == 400
        assert get_expense(expense_id) == before

    @pytest.mark.parametrize("bad", BAD_CATEGORIES)
    def test_bad_category_returns_400_and_row_unchanged(
        self, auth_client, expense_id, bad
    ):
        before = get_expense(expense_id)
        resp = auth_client.post(edit_url(expense_id), data=valid_form(category=bad))
        assert resp.status_code == 400, f"Category {bad!r} should be rejected"
        assert get_expense(expense_id) == before

    def test_missing_category_field_rejected(self, auth_client, expense_id):
        before = get_expense(expense_id)
        data = valid_form()
        del data["category"]
        resp = auth_client.post(edit_url(expense_id), data=data)
        assert resp.status_code == 400
        assert get_expense(expense_id) == before

    def test_description_over_200_chars_rejected(self, auth_client, expense_id):
        before = get_expense(expense_id)
        resp = auth_client.post(
            edit_url(expense_id), data=valid_form(description="d" * 201)
        )
        assert resp.status_code == 400
        assert get_expense(expense_id) == before

    def test_sql_injection_in_category_rejected(self, auth_client, expense_id):
        before = get_expense(expense_id)
        resp = auth_client.post(
            edit_url(expense_id),
            data=valid_form(category="Food'; DROP TABLE expenses; --"),
        )
        assert resp.status_code == 400
        assert get_expense(expense_id) == before

    def test_sql_injection_in_description_stored_literally(
        self, auth_client, expense_id
    ):
        payload = "'); DROP TABLE expenses; --"
        resp = auth_client.post(
            edit_url(expense_id), data=valid_form(description=payload)
        )
        assert resp.status_code == 302
        assert get_expense(expense_id)["description"] == payload


# ------------------------------------------------------------------ #
# Values preserved after errors                                       #
# ------------------------------------------------------------------ #

class TestFormPreservation:
    def test_submitted_values_shown_not_stored_ones(self, auth_client, user_id):
        eid = make_expense(
            user_id, amount=11.0, category="Food", date_str="2020-01-01",
            description="StoredDescriptionAAA",
        )
        resp = auth_client.post(
            edit_url(eid),
            data=valid_form(
                amount="abc", category="Transport", date="2025-04-01",
                description="SubmittedDescriptionBBB",
            ),
        )
        page = resp.get_data(as_text=True)
        assert resp.status_code == 400
        assert "abc" in page, "Submitted amount should be kept"
        assert "2025-04-01" in page, "Submitted date should be kept"
        assert "SubmittedDescriptionBBB" in page, "Submitted description kept"
        assert "StoredDescriptionAAA" not in page, "Stored description must not show"
        assert "2020-01-01" not in page, "Stored date must not show"

    def test_selected_category_is_submitted_one_after_error(
        self, auth_client, expense_id
    ):
        resp = auth_client.post(
            edit_url(expense_id), data=valid_form(amount="0", category="Shopping")
        )
        page = resp.get_data(as_text=True)
        selected = [
            seg for seg in page.split("<option")[1:]
            if "selected" in seg.split(">")[0]
        ]
        assert len(selected) == 1
        assert "Shopping" in selected[0].split("</option>")[0], (
            "Submitted category should remain selected"
        )

    def test_values_kept_after_date_error(self, auth_client, expense_id):
        resp = auth_client.post(
            edit_url(expense_id),
            data=valid_form(amount="99.99", date="bogus", description="StillHere"),
        )
        page = resp.get_data(as_text=True)
        assert resp.status_code == 400
        assert "99.99" in page
        assert "StillHere" in page

    def test_values_kept_after_long_description_error(self, auth_client, expense_id):
        resp = auth_client.post(
            edit_url(expense_id),
            data=valid_form(amount="55.55", description="x" * 201),
        )
        page = resp.get_data(as_text=True)
        assert "55.55" in page
        assert "x" * 201 in page

    def test_preserved_values_are_html_escaped(self, auth_client, expense_id):
        payload = '"><script>alert(1)</script>'
        resp = auth_client.post(
            edit_url(expense_id), data=valid_form(amount="-1", description=payload)
        )
        page = resp.get_data(as_text=True)
        assert "<script>alert(1)</script>" not in page, "Input must be escaped"
        assert html_lib.escape(payload) in page or "&lt;script&gt;" in page


# ------------------------------------------------------------------ #
# Ownership                                                           #
# ------------------------------------------------------------------ #

class TestOwnership:
    def test_get_nonexistent_id_returns_404(self, auth_client):
        assert auth_client.get(edit_url(99999)).status_code == 404

    def test_post_nonexistent_id_returns_404(self, auth_client):
        resp = auth_client.post(edit_url(99999), data=valid_form())
        assert resp.status_code == 404
        assert count_expenses() == 0, "POST to missing id must not create a row"

    def test_get_other_users_expense_returns_404(self, auth_client, other_expense_id):
        resp = auth_client.get(edit_url(other_expense_id))
        assert resp.status_code == 404
        assert "Other users secret" not in resp.get_data(as_text=True)

    def test_post_other_users_expense_returns_404_and_row_unmodified(
        self, auth_client, other_expense_id
    ):
        before = get_expense(other_expense_id)
        resp = auth_client.post(edit_url(other_expense_id), data=valid_form())
        assert resp.status_code == 404
        assert get_expense(other_expense_id) == before, (
            "Another user's expense must not be modified"
        )

    def test_invalid_post_to_other_users_expense_still_404(
        self, auth_client, other_expense_id
    ):
        resp = auth_client.post(
            edit_url(other_expense_id), data=valid_form(amount="abc")
        )
        assert resp.status_code == 404, "Ownership is checked before validation"

    def test_other_user_and_missing_id_look_identical(
        self, auth_client, other_expense_id
    ):
        missing = auth_client.get(edit_url(99999))
        foreign = auth_client.get(edit_url(other_expense_id))
        assert missing.status_code == foreign.status_code == 404
        assert missing.get_data() == foreign.get_data(), (
            "404 responses must not reveal that the id exists"
        )

    def test_non_integer_id_returns_404(self, auth_client):
        assert auth_client.get("/expenses/abc/edit").status_code == 404

    def test_forged_user_id_does_not_change_owner(
        self, auth_client, expense_id, user_id, other_user_id
    ):
        resp = auth_client.post(
            edit_url(expense_id), data=valid_form(user_id=str(other_user_id))
        )
        assert resp.status_code == 302
        assert get_expense(expense_id)["user_id"] == user_id, (
            "Owner must not be changeable via the form"
        )

    def test_forged_nonexistent_user_id_ignored(
        self, auth_client, expense_id, user_id
    ):
        resp = auth_client.post(edit_url(expense_id), data=valid_form(user_id="99999"))
        assert resp.status_code == 302
        assert get_expense(expense_id)["user_id"] == user_id

    def test_forged_id_field_does_not_change_id(self, auth_client, expense_id):
        auth_client.post(edit_url(expense_id), data=valid_form(id="424242"))
        assert get_expense(expense_id) is not None
        assert get_expense(424242) is None

    def test_other_user_can_edit_own_expense_not_first_users(
        self, client, user_id, other_user_id, expense_id, other_expense_id
    ):
        login(client, email=OTHER_EMAIL, password=OTHER_PASSWORD)
        assert client.get(edit_url(expense_id)).status_code == 404
        assert client.get(edit_url(other_expense_id)).status_code == 200


# ------------------------------------------------------------------ #
# Add expense page still works with the shared template               #
# ------------------------------------------------------------------ #

class TestAddPageUnaffected:
    def test_add_page_returns_200(self, auth_client):
        assert auth_client.get(ADD_URL).status_code == 200

    def test_add_page_reads_add_expense(self, auth_client):
        page = auth_client.get(ADD_URL).get_data(as_text=True)
        assert "Add expense" in page, "Heading should read 'Add expense'"

    def test_add_page_button_reads_save_expense(self, auth_client):
        page = auth_client.get(ADD_URL).get_data(as_text=True)
        assert "Save expense" in page, "Button should read 'Save expense'"

    def test_add_form_action_is_add_url(self, auth_client):
        page = auth_client.get(ADD_URL).get_data(as_text=True)
        assert 'name="amount"' in page
        assert "/edit" not in page.split("<form", 1)[1].split(">", 1)[0], (
            "Add form must not post to an edit URL"
        )

    def test_add_still_creates_a_new_row(self, auth_client, user_id):
        resp = auth_client.post(
            ADD_URL,
            data={"amount": "10", "category": "Food", "date": TODAY,
                  "description": "new"},
        )
        assert resp.status_code == 302
        assert count_expenses() == 1
