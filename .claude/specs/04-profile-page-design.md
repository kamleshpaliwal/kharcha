# Spec: Profile Page Design

## Overview
Replace the `/profile` placeholder string with a real, designed page. Step 03 already redirects every successful login to `/profile`, so today users land on the text "Profile page — coming in Step 4". This step builds the page they should see: an account header (name, email, member-since), a row of spending summary cards (total spent, this month, number of expenses, top category), a category breakdown, and a list of recent expenses. All data is read-only and comes from the existing `users` and `expenses` tables. Adding, editing and deleting expenses stay in Steps 7–9.

## Depends on
- Step 01 — Database setup (`get_db()`, `users` and `expenses` tables, demo seed data)
- Step 02 — Registration (real accounts)
- Step 03 — Login and Logout (`session["user_id"]`, navbar with current user name, `POST /logout`)

## Routes
- `GET /profile` — render the profile page for the logged-in user; if there is no `user_id` in the session, redirect to `/login` — logged-in

(The existing `profile` route function name must not change: `login`, `register` and `base.html` use `url_for('profile')`.)

## Database changes
No database changes. Read-only queries against existing columns: `users(id, name, email, created_at)` and `expenses(user_id, amount, category, date, description)`.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; sections: profile header, summary cards, category breakdown, recent expenses (with an empty state for users who have no expenses)
- **Modify:** none (`base.html` navbar already links to `profile`)

## Files to change
- `app.py` — implement the `profile` route (session check, queries, `render_template`)
- `static/css/style.css` — add profile page styles (header/avatar, stat cards, category bars, expense list, responsive layout), using existing CSS variables

## Files to create
- `templates/profile.html`
- `tests/test_profile.py` — pytest tests for the profile route

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only; every query filters by the session's `user_id`, so a user can never see another user's data
- Passwords hashed with werkzeug — never select or render `password_hash`
- Use CSS variables — never hardcode hex values (reuse `--accent`, `--paper-card`, `--border`, `--radius-md`, `--font-display`, etc. from `style.css`; add new variables to `:root` only if truly needed)
- All templates extend `base.html`
- Not logged in → `redirect(url_for("login"))`. If the session has a `user_id` for a user that no longer exists, clear the session and redirect to login
- Always close the DB connection (`try/finally`)
- Do the aggregation in SQL (`SUM`, `COUNT`, `GROUP BY category`), not by looping over every row in Python
- Page contents:
  - Header: initial-letter avatar, name, email, "Member since <Month YYYY>" from `created_at`
  - Summary cards: total spent, spent this calendar month, number of expenses, top category (show "—" when there are no expenses)
  - Category breakdown: each category with its total and percentage of overall spend, sorted highest first, shown as a horizontal bar whose width is the percentage (inline `style="width: N%"` is allowed for the dynamic width only)
  - Recent expenses: the latest 10 by `date DESC, id DESC` showing date, description, category and amount
  - Amounts use the rupee sign and two decimals (e.g. `₹1,800.00`), matching the "Track every rupee" branding
- Autoescape stays on; never use `|safe` on user-provided text such as descriptions
- Layout must work on mobile widths (cards stack to one column, no horizontal scroll)
- No add/edit/delete buttons or links, no filters, no charts library, no JavaScript — those belong to later steps
- Do not touch the other placeholder routes or `seed_db()`

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` lands on a designed profile page, not a placeholder string
- [ ] The header shows the demo user's name, email and "Member since" month and year
- [ ] Summary cards show the correct total spent (₹6,110.00 for the seed data), this-month total, expense count (8) and top category (Shopping)
- [ ] The category breakdown lists every category with its total and percentage, highest first, and the percentages add up to about 100%
- [ ] The recent expenses list shows the latest 10 expenses newest first, with date, description, category and amount
- [ ] A freshly registered user with no expenses sees zeros, "—" for top category and an empty-state message, with no errors
- [ ] A user only ever sees their own expenses (verified with two accounts)
- [ ] An expense description containing `<script>` is displayed as text, not executed
- [ ] The page is readable at a ~375px wide viewport with no horizontal scrolling
- [ ] The navbar still shows the user's name and "Sign out", and signing out still works from this page
- [ ] The app starts without errors and `pytest` passes
