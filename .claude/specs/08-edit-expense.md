# Spec: Edit Expense

## Overview
Step 8 replaces the `/expenses/<id>/edit` placeholder with a working form that lets a logged-in user change an existing expense (amount, category, date, description). The form is pre-filled with the saved values; on success the row is updated and the user is redirected to `/profile`, where the summary, category breakdown and recent transactions reflect the change. It builds directly on Step 7 (add expense), reusing its validation and form layout, and comes before delete (Step 9). To make editing reachable, the profile transactions table gains an "Edit" link per row, which requires the recent-expenses query to also return each expense's `id`.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 2/3: Registration and login/logout (`session["user_id"]`)
- Step 5/6: Profile page, which lists the expenses and gets the Edit links
- Step 7: Add expense (`_validate_expense_form`, `CATEGORIES`, form styles)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense's current values — logged-in (owner only)
- `POST /expenses/<int:id>/edit` — validate and update the expense, redirect to `/profile` — logged-in (owner only)

Anonymous users are redirected to `/login` on both methods. If the expense does not exist **or belongs to another user**, return 404 (same response for both, so ids of other users' expenses are not revealed). The existing `edit_expense` function name must not change.

## Database changes
No database changes. The existing `expenses` table (`id`, `user_id`, `amount REAL`, `category TEXT`, `date TEXT`, `description TEXT`, `created_at`) already covers every field. Verified against `database/db.py`: no new columns or constraints are needed (no `updated_at` is added in this step).

## Templates
- **Create:** none (the form is shared with Step 7)
- **Modify:**
  - `templates/add_expense.html` — make it serve both add and edit: take the page heading, subtitle, form `action` and submit-button label from context (e.g. `form_title`, `form_action`, `submit_label`) instead of hardcoding "Add expense"; keep all existing fields, error block and value re-population. Rename to `templates/expense_form.html` only if the add route and tests are updated in the same change; otherwise keep the filename.
  - `templates/profile.html` — add an "Edit" link to `url_for("edit_expense", id=e.id)` in each row of the recent-transactions table (new column header, e.g. "Actions")

## Files to change
- `app.py`:
  - convert `edit_expense` to `methods=["GET", "POST"]` with the auth guard
  - add a helper to load one expense by `id` AND `user_id`
  - extend `_get_recent_expenses` to select `id`
  - extend `_render_expense_form` (or its callers) to pass the heading/action/label context for both add and edit
  - leave `delete_expense` untouched (Step 9)
- `templates/add_expense.html`
- `templates/profile.html`
- `static/css/style.css` — style the row "Edit" link using existing CSS variables
- `tests/test_07-add-expense.py` — only if the shared-template change alters what those tests assert

## Files to create
- `tests/test_08-edit-expense.py` (written via `/test-feature 08-edit-expense`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — including `UPDATE expenses SET ... WHERE id = ? AND user_id = ?`
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- `user_id` comes from `session`, never from the form or URL; the form must not be able to change an expense's owner
- Ownership check on both GET and POST: fetch with `WHERE id = ? AND user_id = ?`; `abort(404)` if no row. The UPDATE itself also includes `AND user_id = ?`
- Reuse `_validate_expense_form` and `CATEGORIES` — do not duplicate validation rules (amount > 0 and finite, ≤ `MAX_AMOUNT`, fixed categories, valid date, description ≤ `MAX_DESCRIPTION`)
- On validation error, re-render the form with status 400, an error message and the user's submitted values (not the stored ones)
- On GET, pre-fill from the stored row (amount, category, date, description; a NULL description shows as empty)
- Keep `created_at` unchanged; do not change `id` or `user_id`
- Close the DB connection in a `finally` block, as the other routes do
- Redirect with Post/Redirect/Get to `url_for("profile")` on success
- Keep the `inr` filter for any amount display

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Each row in the profile transactions table has an "Edit" link that opens that expense's edit form
- [ ] The edit form is pre-filled with the expense's current amount, category (selected), date and description, with all seven categories listed
- [ ] Submitting valid changes updates the row and redirects to `/profile`
- [ ] The updated values appear in recent transactions, and the total and category breakdown on `/profile` reflect the change
- [ ] Changing the category moves the amount between categories in the breakdown
- [ ] Clearing the description is accepted and saves as empty
- [ ] Empty, zero, negative, non-numeric, `nan` and `inf` amounts show an error with HTTP 400 and leave the stored row unchanged
- [ ] An invalid date or a category outside the fixed list shows an error with HTTP 400 and leaves the stored row unchanged
- [ ] After a validation error the form keeps the submitted values
- [ ] Requesting an id that does not exist returns 404
- [ ] Requesting (GET or POST) another user's expense id returns 404 and the row is not modified
- [ ] A POST containing a `user_id` field does not change the expense's owner
- [ ] Editing does not change the number of expenses or the expense's `created_at`
- [ ] The Add expense page still works with the shared template (heading and button read "Add expense" / "Save expense")
- [ ] No hardcoded hex colours in the changed templates or CSS
- [ ] The app starts without errors and `pytest` passes
