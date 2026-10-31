# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Spendly" — a Flask + SQLite expense tracker built as a step-by-step teaching project. Currently only the landing/auth/legal pages are rendered; everything else is a stub.

## Commands

```
source venv/bin/activate
pip install -r requirements.txt
python app.py              # dev server, debug on, http://localhost:5001
pytest                     # pytest + pytest-flask are installed; no tests exist yet
pytest path/to/test.py::test_name   # single test
```

No linter or build step is configured.

## Architecture

- `app.py` — single Flask app with all routes. Implemented routes (`/`, `/register`, `/login`, `/terms`, `/privacy`) just render templates; there is no form handling or session logic yet (register/login are GET-only). The remaining routes (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) are placeholders returning strings labelled "coming in Step N" — they are meant to be implemented in that step order.
- `database/db.py` — intentionally a comment-only stub describing the planned `get_db()` (SQLite connection with `row_factory` and foreign keys on), `init_db()` (`CREATE TABLE IF NOT EXISTS`), and `seed_db()`. Nothing imports it yet.
- `templates/` — all pages extend `base.html` (navbar, `title`/`head`/`content` blocks, Google Fonts). Links use `url_for(...)` with the route function names, so renaming a route function breaks templates.
- `static/css/style.css` — single hand-written stylesheet (no framework); `static/js/main.js` is currently empty.

## Conventions

- Git commits in this repo use a `landing: ...` style prefix for landing-page work.
