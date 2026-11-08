import calendar
import math
import os
import sqlite3
from datetime import date, datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# The fallback key is for local development only; set SECRET_KEY in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

# Add-expense validation limits and choices
CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]
MAX_AMOUNT = 1_000_000_000
MAX_DESCRIPTION = 200

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


def _valid_email(email):
    local, sep, domain = email.partition("@")
    return bool(sep and local and domain and "@" not in domain)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    def fail(message):
        return (
            render_template("register.html", error=message, name=name, email=email),
            400,
        )

    if not name or not email or not password or not confirm_password:
        return fail("Name, email, password and confirm password are required.")
    if not _valid_email(email):
        return fail("Please enter a valid email address.")
    if len(password) < 8:
        return fail("Password must be at least 8 characters.")
    if password != confirm_password:
        return fail("Passwords do not match.")

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return fail("An account with that email already exists.")
    finally:
        conn.close()

    return redirect(url_for("login", registered=1))


@app.context_processor
def inject_user():
    user_id = session.get("user_id")
    if not user_id:
        return {"current_user_name": None}

    conn = get_db()
    try:
        row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        session.clear()
        return {"current_user_name": None}
    return {"current_user_name": row["name"]}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(message):
        return render_template("login.html", error=message, email=email), 400

    if not email or not password:
        return fail("Email and password are required.")

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return fail("Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.template_filter("inr")
def inr(value):
    return f"₹{value:,.2f}"


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) restricting expenses.date to a range.

    The fragment must stay a hardcoded literal: dates go in via placeholders,
    and nothing user-supplied may ever be concatenated into the SQL text.
    """
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


def _parse_date(value):
    """Return value as a zero-padded YYYY-MM-DD string, or None if invalid."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        return None


def _parse_date_range(args):
    """Return (date_from, date_to, error) from request args.

    Missing or malformed values mean no filter. A reversed range also means
    no filter, plus an error message for the user.
    """
    date_from = _parse_date(args.get("date_from", "").strip())
    date_to = _parse_date(args.get("date_to", "").strip())
    if not date_from or not date_to:
        return None, None, None
    if date_from > date_to:
        return None, None, "Start date must be before end date."
    return date_from, date_to, None


def _months_ago(today, months):
    """Return the date `months` calendar months before today (day clamped)."""
    index = today.year * 12 + today.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _build_presets(today, date_from=None, date_to=None):
    """Return the quick-select filter presets, relative to today.

    Each preset carries an `active` flag marking whether it matches the
    currently applied range.
    """
    end = today.isoformat()
    ranges = [
        ("This Month", today.replace(day=1).isoformat(), end),
        ("Last 3 Months", _months_ago(today, 3).isoformat(), end),
        ("Last 6 Months", _months_ago(today, 6).isoformat(), end),
        ("All Time", None, None),
    ]
    return [
        {
            "label": label,
            "date_from": start,
            "date_to": stop,
            "active": (start, stop) == (date_from, date_to),
        }
        for label, start, stop in ranges
    ]


def _get_summary(conn, user_id, date_from=None, date_to=None):
    """Return a dict with total, count and month_total for the user.

    total and count honour the date range; month_total is intentionally
    independent of the filter and is always the current calendar month.
    """
    clause, extra = _date_clause(date_from, date_to)
    this_month = date.today().strftime("%Y-%m")
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ?" + clause,
        (user_id,) + extra,
    ).fetchone()
    month_total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE user_id = ? AND substr(date, 1, 7) = ?",
        (user_id, this_month),
    ).fetchone()[0]
    return {
        "total": row["total"],
        "count": row["count"],
        "month_total": month_total,
    }


def _get_category_breakdown(
    conn, user_id, overall, date_from=None, date_to=None
):
    """Return a list of {category, total, percent}, highest total first."""
    clause, extra = _date_clause(date_from, date_to)
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ?" + clause +
        " GROUP BY category ORDER BY total DESC, category",
        (user_id,) + extra,
    ).fetchall()
    return [
        {
            "category": row["category"],
            "total": row["total"],
            "percent": round(row["total"] / overall * 100, 1) if overall else 0,
        }
        for row in rows
    ]


def _get_recent_expenses(conn, user_id, limit=10, date_from=None, date_to=None):
    """Return the user's most recent expenses, newest first."""
    clause, extra = _date_clause(date_from, date_to)
    return conn.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
        (user_id,) + extra + (limit,),
    ).fetchall()


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    date_from, date_to, filter_error = _parse_date_range(request.args)

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for("login"))

        summary = _get_summary(conn, user_id, date_from, date_to)
        categories = _get_category_breakdown(
            conn, user_id, summary["total"], date_from, date_to
        )
        recent = _get_recent_expenses(
            conn, user_id, date_from=date_from, date_to=date_to
        )
    finally:
        conn.close()

    member_since = datetime.strptime(
        user["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")

    presets = _build_presets(date.today(), date_from, date_to)

    return render_template(
        "profile.html",
        presets=presets,
        date_from=date_from,
        date_to=date_to,
        filter_error=filter_error,
        user=user,
        member_since=member_since,
        total=summary["total"],
        month_total=summary["month_total"],
        count=summary["count"],
        month_name=date.today().strftime("%B"),
        top_category=categories[0]["category"] if categories else None,
        categories=categories,
        recent=recent,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


def _validate_expense_form(form):
    """Validate the add/edit expense form.

    Returns (clean, error). `clean` is a dict ready for the database when the
    form is valid, otherwise None; `error` is a user-facing message or None.
    """
    amount_raw = form.get("amount", "").strip()
    category = form.get("category", "")
    date_raw = form.get("date", "").strip()
    description = form.get("description", "").strip()

    try:
        amount = round(float(amount_raw), 2)
    except ValueError:
        return None, "Please enter a valid amount."
    if not math.isfinite(amount) or amount <= 0:
        return None, "Amount must be greater than zero."
    if amount > MAX_AMOUNT:
        return None, "Amount is too large."
    if category not in CATEGORIES:
        return None, "Please choose a valid category."
    parsed_date = _parse_date(date_raw)
    if parsed_date is None:
        return None, "Please enter a valid date."
    if len(description) > MAX_DESCRIPTION:
        return None, f"Description must be {MAX_DESCRIPTION} characters or fewer."

    return {
        "amount": amount,
        "category": category,
        "date": parsed_date,
        "description": description or None,
    }, None


def _render_expense_form(status=200, **context):
    return (
        render_template(
            "add_expense.html",
            categories=CATEGORIES,
            max_description=MAX_DESCRIPTION,
            **context,
        ),
        status,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if request.method == "GET":
        return _render_expense_form(date_raw=date.today().isoformat())

    clean, error = _validate_expense_form(request.form)
    if error:
        return _render_expense_form(
            400,
            error=error,
            amount_raw=request.form.get("amount", "").strip(),
            category=request.form.get("category", ""),
            date_raw=request.form.get("date", "").strip(),
            description=request.form.get("description", "").strip(),
        )

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                clean["amount"],
                clean["category"],
                clean["date"],
                clean["description"],
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # The user row no longer exists (e.g. deleted); the session is stale.
        session.clear()
        return redirect(url_for("login"))
    finally:
        conn.close()

    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
