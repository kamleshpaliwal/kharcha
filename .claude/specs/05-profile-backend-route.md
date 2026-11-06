# Spec: Profile Backend Route

## Overview
This feature connects the `/profile` page to the database. Step 4 built the profile UI with hardcoded data; this step replaces that data with real queries against the logged-in user's `users` and `expenses` rows: user info and member-since date, total spent, this-month total, transaction count, per-category totals with percentages, and the 10 most recent expenses. It is the "backend connection" step that Step 4 deferred, and it must land before the expense CRUD steps (7–9) so that added, edited and deleted expenses show up on the profile.

Note: the current `/profile` view in `app.py` already contains these queries (added in commit `186eba3`). This spec records the intended behaviour so the code, tests and docs share one definition. Implementation work is limited to any gaps found when checking the code against the Definition of done.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables, `get_db()`)
- Step 2: Registration (users can be created)
- Step 3: Login + Logout (`session["user_id"]` is set)
- Step 4: Profile page design (`templates/profile.html` exists)

## Routes
- `GET /profile` — render the profile page from live database data — logged-in only (redirect to `/login` if there is no session, or if the session's user no longer exists, in which case the session is cleared)

No other new routes.

## Database changes
No database changes. The existing `users` (`id`, `name`, `email`, `password_hash`, `created_at`) and `expenses` (`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`) tables in `database/db.py` are sufficient.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — must render the context variables below instead of hardcoded values. Context passed by the view:
  - `user` (id, name, email, created_at), `member_since` ("Month YYYY")
  - `total`, `month_total`, `count`, `month_name`, `top_category` (None when there are no expenses)
  - `categories` — list of `{category, total, percent}` ordered by total descending, then category name
  - `recent` — up to 10 rows of `date, description, category, amount`, ordered by date descending, then id descending
  - Must show a sensible empty state when the user has no expenses.

## Files to change
- `app.py` — `profile()` view (queries and context)
- `templates/profile.html` — render live context, empty state
- `tests/test_profile.py` — cover the behaviours in the Definition of done
- `.claude/specs/04-profile-page-design.md` — optional: note that real data was wired in Step 5

## Files to create
- `.claude/specs/05-profile-backend-route.md` (this file)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw sqlite3 via `get_db()`
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Authentication guard: `session.get("user_id")`; if absent, `redirect(url_for("login"))`
- Every expense query must filter on `user_id` so one user never sees another user's data
- Close the connection in a `finally` block
- Format money with the existing `inr` template filter
- Compute category percentages in Python, guarding against a zero total (no division by zero)

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Visiting `/profile` while logged in returns HTTP 200
- [ ] If the session's `user_id` has no matching user, the session is cleared and the visitor is redirected to `/login`
- [ ] The page shows the logged-in user's real name, email and member-since month
- [ ] Logging in as `demo@spendly.com` shows total ₹6,110.00 across 8 transactions, with Shopping as the top category
- [ ] The this-month total counts only expenses dated in the current month
- [ ] The category breakdown percentages sum to about 100% and are ordered highest first
- [ ] The recent list shows at most 10 expenses, newest first
- [ ] A user with no expenses sees zeros and an empty state, with no errors
- [ ] A second user's expenses never appear on the first user's profile
- [ ] No hex colour values appear in `profile.html` — only CSS variables
- [ ] `pytest tests/test_profile.py` passes
