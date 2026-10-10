from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_get_order_returns_correct_items_and_customer():
    response = client.get("/api/orders/101")

    body = response.json()
    assert response.status_code == 200
    assert body["customer"] == "alice@example.com"
    assert body["items"][0]["name"] == "Keyboard"


def test_get_order_total_includes_sales_tax():
    """
    THIS TEST IS EXPECTED TO FAIL as long as BUG B is present.

    Order 101 is one Keyboard at $45.00. app/orders.py's TAX_RATE is 0.08,
    but calculate_total() never applies it — so the API currently returns
    45.00 instead of 48.60. See docs/sample-project-bugs.md.
    """
    response = client.get("/api/orders/101")

    assert response.status_code == 200
    assert response.json()["total"] == 48.60  # 45.00 * 1.08


def test_get_nonexistent_order_returns_404():
    """
    THIS TEST IS EXPECTED TO FAIL as long as BUG C is present.

    app/orders.py's get_order() raises a plain KeyError for an unknown
    order_id, but app/main.py only catches OrderNotFoundError — so an
    unknown order currently returns 500 instead of 404. See
    docs/sample-project-bugs.md.
    """
    response = client.get("/api/orders/999999")

    assert response.status_code == 404
