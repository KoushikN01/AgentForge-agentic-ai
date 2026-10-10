# Architecture

## What sample_project is

A small FastAPI service with two features: user login (`/api/auth/login`)
and order lookup (`/api/orders/{order_id}`). It has no real database —
users and orders are in-memory Python dictionaries (`app/users.py`,
`app/orders.py`) — that's intentional, to keep the sandbox simple to run
and investigate.

## Request flow

```
Client
  ↓
FastAPI (app/main.py)
  ↓
app/auth.py  (login)      app/orders.py  (order lookup)
  ↓                          ↓
app/users.py (fake DB)     in-memory ORDERS dict
```

## Authentication

Login checks the submitted email/password against `app/users.py`, and on
success issues an access token signed with a secret key. The secret key
comes from an environment variable — see the Deployment Notes and Runbook
for which variable name is required.

## Orders

Each order has a list of line items (name, price, quantity). The order
total is calculated by summing `price * quantity` across items and then
applying sales tax, per `app.orders.TAX_RATE`.
