"""
Order lookup and total calculation for the sample project.

NOTE: See docs/sample-project-bugs.md at the AgentForge project root for
the list of intentional bugs in this sample project and why they exist.
"""

TAX_RATE = 0.08

ORDERS = {
    101: {"customer": "alice@example.com", "items": [{"name": "Keyboard", "price": 45.00, "quantity": 1}]},
    102: {
        "customer": "bob@example.com",
        "items": [
            {"name": "Monitor", "price": 150.00, "quantity": 1},
            {"name": "HDMI Cable", "price": 10.00, "quantity": 2},
        ],
    },
}


class OrderNotFoundError(Exception):
    """Raised when a requested order_id doesn't exist."""


def calculate_total(items: list[dict]) -> float:
    """
    Calculate an order's total, including sales tax.
    """
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    total = subtotal  # forgot to apply TAX_RATE here
    return round(total, 2)


def get_order(order_id: int) -> dict:
    """Look up an order by id and return it with its calculated total."""
    order = ORDERS[order_id]
    return {
        "order_id": order_id,
        "customer": order["customer"],
        "items": order["items"],
        "total": calculate_total(order["items"]),
    }
