# Spec: Login and Logout

## Overview
Make `/login` and `/logout` functional. Today `/login` only renders a form (GET-only, and the form posts to a route that does not accept POST) and `/logout` is a placeholder string. This step adds credential checking against the `users` table, Flask session handling (`secret_key`, storing `user_id`), a working logout, and a navbar that reflects whether the visitor is signed in. It builds on the accounts created in Step 02 and unlocks every logged-in feature that follows (profile, add/edit/delete expense).

## Depends on
- Step 01 — Database setup (`get_db()`, `users` table, demo user `demo@spendly.com` / `demo123`)
- Step 02 — Registration (real accounts with werkzeug password hashes; `login?registered=1` notice)

## Routes
- `GET /login` — render the sign-in form; if already logged in, redirect to `/profile` — public
- `POST /login` — validate email + password, on success store `user_id` in the session and redirect to `/profile`; on failure re-render the form with an error and HTTP 400 — public
- `POST /logout` — clear the session and redirect to `/` — logged-in (a logged-out request is harmless: it just redirects to `/`)

- `GET /register` and `POST /register` (existing, Step 02) — if already logged in, redirect to `/profile` without creating an account — public

(The existing `login` and `logout` route function names must not change because templates use `url_for('login')` / `url_for('logout')`. `logout` changes from a GET placeholder to POST-only so a link or image on another site cannot sign the user out.)

## Database changes
No database changes. Login reads `id`, `name`, `email` and `password_hash` from the existing `users` table.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change `action="/login"` to `action="{{ url_for('login') }}"`; re-populate the `email` input from the submitted value after an error (never the password); keep the existing `registered` success notice and `{% if error %}` block
  - `templates/base.html` — in the navbar, when `session.user_id` is set show the user's name/"Profile" link and a "Sign out" button inside a `<form method="POST" action="{{ url_for('logout') }}">`; otherwise keep the existing "Sign in" and "Get started" links

## Files to change
- `app.py` — import `session` (and `check_password_hash`); set `app.secret_key`; implement `login` (GET + POST) and `logout` (POST); add a logged-in redirect at the top of `register`; add a context processor (or `before_request`) that exposes the current user's name to templates
- `templates/login.html`
- `templates/base.html`
- `static/css/style.css` — style the navbar sign-out button so it matches the nav links, using CSS variables

## Files to create
- `tests/test_login_logout.py` — pytest tests for the login and logout routes

## New dependencies
No new dependencies (Flask's built-in signed-cookie `session` and `werkzeug.security.check_password_hash` are already available).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`; never compare plaintext, never log or echo passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` is read from an environment variable (e.g. `SECRET_KEY`) with a clearly-labelled development fallback; do not hardcode a production secret
- Normalise the submitted email with `.strip().lower()` before the lookup (registration stores lowercased emails)
- Validation, each failure returns the form with HTTP 400 and an `error` message:
  - email and password both present, otherwise "Email and password are required."
  - unknown email **or** wrong password returns the same message, "Invalid email or password.", so the form does not reveal which emails are registered
- On success call `session.clear()` before setting `session["user_id"]` to avoid carrying over stale session data, then redirect (Post/Redirect/Get) to `url_for("profile")`
- Store only `user_id` in the session — look up the name from the database per request rather than trusting cookie contents
- Always close the DB connection (`try/finally`)
- Do not implement the real profile page, route protection for expense routes, or `flash()` messages — those belong to later steps; `/profile` stays the existing placeholder
- The only change to `register` is the logged-in redirect to `url_for("profile")` at the top of the function (applies to GET and POST); its validation and insert logic stay untouched
- Do not touch `seed_db()` or the other placeholder routes

## Definition of done
- [ ] `GET /login` renders the form, and the form posts to `/login` via `url_for`
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects to `/profile` and the navbar then shows a "Sign out" button instead of "Sign in" / "Get started"
- [ ] Logging in with a freshly registered account (from Step 02) works
- [ ] Email matching is case-insensitive (`Demo@Spendly.com` logs in)
- [ ] A wrong password shows "Invalid email or password." with HTTP 400 and the session is not set
- [ ] An unknown email shows the exact same error message as a wrong password
- [ ] Blank email or password shows "Email and password are required."
- [ ] After a failed login the email field keeps its value and the password field is empty
- [ ] Visiting `/login` while already logged in redirects to `/profile`
- [ ] Visiting `/register` while already logged in redirects to `/profile`, and POSTing to it creates no new user
- [ ] Clicking "Sign out" clears the session, redirects to `/`, and the navbar shows "Sign in" / "Get started" again
- [ ] `GET /logout` returns 405 (logout is POST-only)
- [ ] The session cookie contains only the signed `user_id`, never the password or hash
- [ ] The `registered=1` success notice on `/login` still works
- [ ] The app starts without errors and `pytest` passes
