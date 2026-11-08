# Spec: Add Expense

## Overview
Step 7 replaces the `/expenses/add` placeholder with a working form that lets a
logged-in user record a new expense (amount, category, date, optional
description). On success the expense is saved to the `expenses` table and the
user is redirected to `/profile`, where it appears in the summary, category
breakdown and recent transactions. This is the first write path for expense
data and a prerequisite for edit (Step 8) and delete (Step 9).

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 2/3: Registration and login/logout (`session["user_id"]`)
- Step 5/6: Profile page, which displays the saved expense

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in
- `POST /expenses/add` — validate and insert the expense, redirect to `/profile` — logged-in

Anonymous users are redirected to `/login` on both methods.

## Database changes
No database changes. The existing `expenses` table
(`user_id`, `amount REAL`, `category TEXT`, `date TEXT`, `description TEXT`)
already covers every field.

## Templates
- **Create:** `templates/add_expense.html` — form with amount (number, step
  0.01), category (select), date (`type="date"`, defaults to today),
  description (text, optional), submit and cancel (link to `profile`)
- **Modify:** `templates/profile.html` — add an "Add expense" link/button to
  `url_for("add_expense")`
- **Modify:** `templates/base.html` — optional navbar link to add expense for
  logged-in users

## Files to change
- `app.py` — convert `add_expense` to `methods=["GET", "POST"]`, add auth
  guard, validation and insert; add a module-level `CATEGORIES` list
- `templates/profile.html` — add entry-point link
- `static/css/style.css` — form styles using existing CSS variables

## Files to create
- `templates/add_expense.html`
- `tests/test_add_expense.py` (written via `/test-feature 07-add-expense`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- `user_id` comes from `session`, never from the form
- Fixed category list, matching the seed data: Food, Transport, Bills, Health,
  Entertainment, Shopping, Other. Reject any value not in the list
- Amount: must parse as a number, be greater than 0, and be finite (reject
  `nan`/`inf`); store as float rounded to 2 decimals
- Date: validate with `_parse_date`; reject missing/malformed values
- Description: stripped, optional, max 200 characters
- On validation error, re-render the form with status 400, an error message and
  the user's previously entered values
- Close the DB connection in a `finally` block, as the other routes do
- Keep the `inr` filter for any amount display

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows the form with today's date
  prefilled and all seven categories listed
- [ ] Submitting valid data creates a row for the logged-in user and redirects
  to `/profile`
- [ ] The new expense appears in recent transactions and updates the total,
  count and category breakdown on `/profile`
- [ ] Description left blank is accepted
- [ ] Empty amount, zero, negative, non-numeric, `nan` and `inf` amounts show an
  error and save nothing
- [ ] Invalid or missing date shows an error and saves nothing
- [ ] A category outside the fixed list shows an error and saves nothing
- [ ] After a validation error the form keeps the entered values
- [ ] A POST containing a `user_id` field cannot create an expense for another
  user
- [ ] The form and profile link render correctly with no hardcoded hex colours
