import pytest

import database.db as db


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()

    from app import app as flask_app

    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def fetch_users():
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM users").fetchall()
    finally:
        conn.close()
