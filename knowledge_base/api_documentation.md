# API Documentation

## `GET /health`

Liveness check. Returns `{"status": "ok"}` with HTTP 200.

## `POST /api/auth/login`

Request body:

```json
{"email": "alice@example.com", "password": "wonderland123"}
```

- **200** — `{"access_token": "<token>"}` on valid credentials.
- **401** — invalid email or password.
- Should never return 500 for a well-formed request; if it does, the
  service is misconfigured (see Troubleshooting Guide).

## `GET /api/orders/{order_id}`

- **200** — order details, including a `total` field that is the sum of
  each line item's `price * quantity`, plus applicable sales tax.
- **404** — no order exists with that id.
- Should never return 500 for a well-formed request.
