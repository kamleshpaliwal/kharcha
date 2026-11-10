# Spec: Delete Expense

## Overview
Step 9 replaces the `/expenses/<id>/delete` placeholder with a working delete action. A logged-in user can remove one of their own expenses from the profile transactions table; after deletion they are redirected to `/profile`, where the totals, category breakdown and recent transactions no longer include it. Deletion changes data, so it is a POST-only action triggered by a small form with a button (not a GET link), protected by an ownership check. It completes the expense CRUD started in Steps 7 (add) and 8 (edit).

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 2/3: Registration and login/logout (`session["user_id"]`)
- Step 5/6: Profile page, which lists the expenses and gets the Delete buttons
- Step 8: Edit expense (`_get_expense` helper, the "Actions" column and `profile-edit-link` styling)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense and redirect to `/profile` — logged-in (owner only)

Anonymous users are redirected to `/login`. If the expense does not exist **or belongs to another user**, return 404 (same response for both, so ids of other users' expenses are not revealed). `GET` is no longer allowed (Flask returns 405), because a GET that deletes data can be triggered by link prefetching or a cross-site `<img>`/link. The existing `delete_expense` function name must not change.

## Database changes
No database changes. Verified against `database/db.py`: the `expenses` table has no dependent tables or foreign keys pointing at it, so a plain `DELETE` is safe. No soft-delete column is added.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html` — in each row's "Actions" cell, next to the Edit link, add a `<form method="post" action="{{ url_for('delete_expense', id=e.id) }}">` with a "Delete" submit button. Add a confirmation step (e.g. `onsubmit="return confirm('Delete this expense?')"` or a handler in `static/js/main.js`) so a mis-click does not delete immediately; the form must still work server-side without JS.

## Files to change
- `app.py`:
  - change `delete_expense` to `methods=["POST"]` with the auth guard
  - add a `_delete_expense(conn, expense_id, user_id)` helper that runs `DELETE FROM expenses WHERE id = ? AND user_id = ?` and returns `cur.rowcount > 0`
- `templates/profile.html`
- `static/css/style.css` — style the Delete button (as a text-style button matching the Edit link, using `--danger`) and keep the two actions aligned
- `static/js/main.js` — only if the confirmation is implemented there instead of inline

## Files to create
- `tests/test_09-delete-expense.py` (written via `/test-feature 09-delete-expense`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — `DELETE FROM expenses WHERE id = ? AND user_id = ?`
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Deletion is POST only; never delete on GET
- `user_id` comes from `session`, never from the form or URL
- Ownership is enforced in the DELETE itself (`AND user_id = ?`); if `rowcount` is 0, `abort(404)` and do not reveal whether the id exists for someone else
- Commit after the delete and close the DB connection in a `finally` block, as the other routes do
- Redirect with Post/Redirect/Get to `url_for("profile")` on success
- Deleting must not affect any other expense or any user row
- Do not change `edit_expense`, `add_expense` or the profile queries

## Definition of done
- [ ] A POST to `/expenses/<id>/delete` while logged out redirects to `/login` and deletes nothing
- [ ] Each row in the profile transactions table has a "Delete" button beside "Edit"
- [ ] Clicking Delete asks for confirmation; cancelling keeps the expense
- [ ] Confirming deletes the expense and redirects to `/profile`
- [ ] The deleted expense disappears from recent transactions, and the total, count, this-month total and category breakdown update accordingly
- [ ] Deleting the last expense in a category removes that category from the breakdown
- [ ] Deleting the user's only expense shows the profile's empty state without errors
- [ ] Only the chosen expense is removed; the user's other expenses are unchanged
- [ ] POST for an id that does not exist returns 404
- [ ] POST for another user's expense id returns 404 and that row still exists
- [ ] `GET /expenses/<id>/delete` returns 405 and deletes nothing
- [ ] Posting the same delete twice: the second request returns 404
- [ ] The edit and add flows still work
- [ ] No hardcoded hex colours in the changed templates or CSS
- [ ] The app starts without errors and `pytest` passes
