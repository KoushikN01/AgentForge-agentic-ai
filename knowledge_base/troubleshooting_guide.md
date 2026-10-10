# Troubleshooting Guide

## Login endpoint returns 500

Most commonly caused by a missing or misnamed environment variable — the
login flow needs `JWT_SECRET` to be set in order to sign access tokens.
Check the application logs for a `KeyError` around the time of the
failing request, and confirm the deployment environment actually has
`JWT_SECRET` set (see Deployment Notes and Runbook).

## Orders endpoint returns wrong total

Check whether sales tax is being applied. The order total should equal
`sum(price * quantity for each item) * (1 + TAX_RATE)`. If the returned
total exactly matches the pre-tax subtotal, tax is not being applied.

## Orders endpoint returns 500 instead of 404 for an unknown order

Indicates an exception type mismatch somewhere between the order lookup
code and its caller — the lookup is raising a different exception type
than the one the API layer is catching.
