# Sample Project

A small FastAPI service used as AgentForge's controlled investigation
sandbox. It has authentication and order-lookup endpoints, its own test
suite, and a log file — enough surface area for AgentForge's tools
(repo, logs, docs, tests, git) to actually investigate in later phases.

## Endpoints

- `GET /health` — liveness check
- `POST /api/auth/login` — `{"email": ..., "password": ...}` -> access token
- `GET /api/orders/{order_id}` — order details including calculated total

## Required environment variables

- `JWT_SECRET` — secret key used to sign access tokens (see the project's
  runbook in `knowledge_base/` for details)

## Running it standalone

```bash
cd sample_project
pip install -r requirements.txt
export JWT_SECRET=some-local-secret
uvicorn app.main:app --reload
```

## Running its tests

```bash
cd sample_project
pytest -v
```
