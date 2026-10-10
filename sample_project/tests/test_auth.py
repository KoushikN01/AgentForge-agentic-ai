import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def jwt_secret_env(monkeypatch):
    # The project's own docs (README.md, knowledge_base/runbook.md) say
    # the required variable is JWT_SECRET — so that's what we set here,
    # the way a real deployment would.
    monkeypatch.setenv("JWT_SECRET", "test-secret-value")


def test_login_with_valid_credentials_returns_a_token():
    """
    THIS TEST IS EXPECTED TO FAIL as long as BUG A is present.

    app/auth.py reads os.environ["JWT_SECRET_KEY"], but the documented
    (and set-here) variable is JWT_SECRET — so this request currently
    returns 500 instead of 200. See docs/sample-project-bugs.md.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wonderland123"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_returns_401():
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_with_unknown_email_returns_401():
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "anything"},
    )

    assert response.status_code == 401
