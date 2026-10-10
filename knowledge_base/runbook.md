# Incident Runbook

## If login returns 500

1. Check `logs/app.log` for `ERROR` entries around the time of the report,
   filtered by the affected request's `request_id` if known.
2. Confirm the deployment environment has `JWT_SECRET` set — this is the
   single most common cause of login 500s. See `deployment_notes.md`.
3. If `JWT_SECRET` is set correctly and the error persists, check
   `app/auth.py` for how the secret is read and used.
4. See `incidents/` for a previously resolved incident of this exact type.

## If an endpoint returns an unexpected 500

1. Reproduce with `pytest` locally against `sample_project/`.
2. Check whether the failing code path raises an exception type that the
   calling API route doesn't explicitly catch — FastAPI turns any
   uncaught exception into a generic 500.

## General investigation order

Logs (what happened) → source code (why it happened) → previous incidents
and documentation (has this happened before, what's the expected
behavior) → propose and test a fix.
