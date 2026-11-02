# Spec: Registration

## Overview
Make the `/register` page functional. Today it only renders a form that posts to `/register`, but the route is GET-only. This step adds form handling: validate input, hash the password, insert a new row into `users`, and send the user on to the login page. It is the first feature that writes user data and it unlocks login (Step 3), which needs real accounts to authenticate against.

## Depends on
- Step 01 — Database setup (`get_db()`, `init_db()`, `users` table with unique `email`)

## Routes
- `GET /register` — render the registration form — public
- `POST /register` — validate form (name, email, password and matching confirm password), create the user, redirect to `/login?registered=1` on success; re-render the form with an error message on failure — public

(The existing `register` route function is extended to accept both methods. The function name must not change because templates use `url_for('register')`.)

## Database changes
No database changes. The `users` table in `database/db.py` already has `id`, `name`, `email` (UNIQUE, NOT NULL), `password_hash` and `created_at`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — add a "Confirm password" input (`id`/`name` = `confirm_password`, type `password`, `required`) after the password field; change `action="/register"` to `action="{{ url_for('register') }}"`; re-populate `name` and `email` inputs from submitted values after an error (never the password); keep the existing `{% if error %}` block
  - `templates/login.html` — show a success notice ("Account created. Please sign in.") when `request.args.get('registered')` is set

## Files to change
- `app.py` — import `request`, `redirect`, `url_for`, `generate_password_hash`, `sqlite3`; make `register` accept GET and POST
- `templates/register.html`
- `templates/login.html`
- `static/css/style.css` — add a `.auth-success` style next to the existing `.auth-error` style, using CSS variables

## Files to create
- `tests/test_registration.py` — pytest tests for the register route

## New dependencies
No new dependencies (`werkzeug` and `pytest-flask` are already installed).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log plaintext passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validation (server side, in this order), each failure returns the form with HTTP 400 and an `error` message:
  - `name`, `email`, `password` and `confirm_password` are all present after `.strip()` (passwords are not stripped)
  - `email` is lowercased and contains `@` with text on both sides
  - `password` is at least 8 characters (matches the placeholder "Min. 8 characters")
  - `confirm_password` exactly equals `password`, otherwise "Passwords do not match." Never store or echo `confirm_password`
- Duplicate email: catch `sqlite3.IntegrityError` from the INSERT (the UNIQUE constraint is the source of truth, no check-then-insert race) and show "An account with that email already exists"
- Always close the DB connection (`try/finally`)
- Do not log the user in: sessions and `secret_key` arrive in Step 3. Do not use `flash()` for the same reason
- Do not touch the placeholder routes or `seed_db()`

## Definition of done
- [ ] `GET /register` still renders the form
- [ ] Submitting valid name, email and an 8+ character password creates a row in `users` and redirects to `/login?registered=1`
- [ ] The stored `password_hash` is a werkzeug hash, not the plaintext password
- [ ] The login page shows the "Account created" notice after registering
- [ ] Registering with an email that already exists (including different casing, e.g. `Demo@Spendly.com`) shows an error and creates no new row
- [ ] A password shorter than 8 characters shows an error and creates no row
- [ ] A blank name or invalid email shows an error and creates no row
- [ ] The form has a "Confirm password" field
- [ ] A confirm password that differs from the password (or is blank) shows an error and creates no row
- [ ] After any error, the name and email fields keep their values and both password fields are empty
- [ ] The app starts without errors and `pytest` passes
