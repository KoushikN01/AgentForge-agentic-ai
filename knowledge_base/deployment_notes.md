# Deployment Notes

## Required environment variables

| Variable      | Purpose                                      | Required |
|---------------|-----------------------------------------------|----------|
| `JWT_SECRET`  | Secret key used to sign login access tokens    | Yes      |

All required environment variables must be set **before** the service
starts handling requests, or the affected endpoints will fail at request
time rather than at startup (the app itself starts fine even if
`JWT_SECRET` is missing — only `/api/auth/login` is affected, since the
secret is only read when a token actually needs to be signed).

## Deploy checklist

1. Set `JWT_SECRET` in the deployment environment.
2. Run the test suite (`pytest`) and confirm it's green before deploying.
3. Deploy the new version.
4. Hit `GET /health` to confirm the service is up.
5. Smoke-test `POST /api/auth/login` with a known test account.
