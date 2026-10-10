# sample_project's Intentional Bugs

This file lives outside `sample_project/` and `knowledge_base/` on
purpose: AgentForge's tools only ever operate inside the workspace roots
they're given (`sample_project/`, `knowledge_base/`), so this "answer key"
isn't something a future agent could stumble onto instead of actually
investigating.

## Bug A — Login returns 500 (wrong environment variable name)

**Where:** `sample_project/app/auth.py`, `create_access_token()`

**What:** The code reads `os.environ["JWT_SECRET_KEY"]`, but every piece
of documentation (`sample_project/README.md`,
`knowledge_base/deployment_notes.md`, `knowledge_base/runbook.md`) calls
the required variable `JWT_SECRET`. Whatever value is set for
`JWT_SECRET`, the code never finds it under the name it's actually
looking for, so it raises `KeyError` and the request fails as an unhandled
500.

**Why this bug:** It's realistic (env var naming drift between docs and
code is a very common real-world incident cause) and it's the clearest
demonstration of why a Knowledge/RAG agent matters — the fix isn't
findable by reading `auth.py` alone; you have to cross-reference it
against the documented contract to see the mismatch.

**Test that proves it:** `sample_project/tests/test_auth.py::test_login_with_valid_credentials_returns_a_token`

## Bug B — Order total is missing sales tax

**Where:** `sample_project/app/orders.py`, `calculate_total()`

**What:** `TAX_RATE = 0.08` is defined and the docstring says the total
"includes sales tax", but the function never actually multiplies by it —
`total = subtotal` instead of `total = subtotal * (1 + TAX_RATE)`.

**Why this bug:** A classic "looks right, silently wrong" bug — nothing
crashes, no error is logged, the endpoint returns 200. It demonstrates why
the Test Agent (a later phase) matters as much as the Debugging Agent: a
passing-looking response can still be an incorrect one, and only an
assertion against the *expected* value catches it.

**Test that proves it:** `sample_project/tests/test_orders.py::test_get_order_total_includes_sales_tax`

## Bug C — Unknown order returns 500 instead of 404

**Where:** `sample_project/app/orders.py`, `get_order()` and
`sample_project/app/main.py`'s `read_order()` route

**What:** `get_order()` does a raw dict lookup (`ORDERS[order_id]`), which
raises a plain `KeyError` for an unknown id. The API route only catches
`OrderNotFoundError` — a different exception type — so the `KeyError`
propagates uncaught and FastAPI turns it into a generic 500.

**Why this bug:** Demonstrates a very common real bug class — the "right
error handling shape, wrong exception type" mismatch — and gives the
Review Agent (a later phase) something concrete to catch: a fix that
changes the *error message* without changing the *exception type* would
still be wrong.

**Test that proves it:** `sample_project/tests/test_orders.py::test_get_nonexistent_order_returns_404`

## How I verified these are real, not fake

I ran `sample_project`'s test suite as shipped (3 failed, 4 passed — exact
output in `BUILD_VERIFICATION.md`), then temporarily applied the real fix
for all three bugs and re-ran the suite (7 passed, 0 failed), then
reverted the fixes before packaging the project. So these are genuine,
fixable bugs with tests that actually detect them — not narrated ones.
