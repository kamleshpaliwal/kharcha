import os
import sqlite3
from datetime import date, datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# The fallback key is for local development only; set SECRET_KEY in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

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


# ---- SUMMARY STATS (owned by subagent 2) --------------------------- #
def _get_summary(conn, user_id):
    """Return a dict with total, count and month_total for the user."""
    this_month = date.today().strftime("%Y-%m")
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, "
        "COUNT(*) AS count, "
        "COALESCE(SUM(CASE WHEN substr(date, 1, 7) = ? THEN amount END), 0) "
        "AS month_total "
        "FROM expenses WHERE user_id = ?",
        (this_month, user_id),
    ).fetchone()
    return {
        "total": row["total"],
        "count": row["count"],
        "month_total": row["month_total"],
    }
# ---- END SUMMARY STATS --------------------------------------------- #


# ---- CATEGORY BREAKDOWN (owned by subagent 3) ---------------------- #
def _get_category_breakdown(conn, user_id, overall):
    """Return a list of {category, total, percent}, highest total first."""
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY category ORDER BY total DESC, category",
        (user_id,),
    ).fetchall()
    return [
        {
            "category": row["category"],
            "total": row["total"],
            "percent": round(row["total"] / overall * 100, 1) if overall else 0,
        }
        for row in rows
    ]
# ---- END CATEGORY BREAKDOWN ---------------------------------------- #


# ---- TRANSACTION HISTORY (owned by subagent 1) --------------------- #
def _get_recent_expenses(conn, user_id, limit=10):
    """Return the user's most recent expenses, newest first."""
    return conn.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
# ---- END TRANSACTION HISTORY --------------------------------------- #


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for("login"))

        summary = _get_summary(conn, user_id)
        categories = _get_category_breakdown(conn, user_id, summary["total"])
        recent = _get_recent_expenses(conn, user_id)
    finally:
        conn.close()

    member_since = datetime.strptime(
        user["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")

    return render_template(
        "profile.html",
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


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
