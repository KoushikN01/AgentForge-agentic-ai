# Architecture

## System diagram

```
React frontend (frontend/, Vite dev server :5173)
        |  fetch() JSON over HTTP, CORS-permitted
        v
FastAPI (backend/app/api/) :8000
        |
        v
SQLAlchemy / SQLite (backend/app/db/) - IncidentState persisted as JSON
        |
        v
IncidentState (backend/app/models/incident_state.py) - the shared contract
        |
        v
LangGraph (backend/app/graph/workflow.py)
  supervisor -> investigation -> knowledge -> debugging -> coding -> testing -> review
                                                               ^                  |
                                                               '--- retry <------'
                                        approve -> awaiting_approval -> (human) -> resolved
                                        fail (retries used up)  -> failed
        |
        v
Sandbox workspace (backend/app/agents/workspace.py) - a throwaway copy of
sample_project/; every agent edit happens here, never on the real directory
        |
        v
apply_human_decision() - the ONLY code path allowed to modify sample_project/
```

## Request flow for one incident

1. `POST /incidents` - creates a DB row, status `new`.
2. `POST /incidents/{id}/investigate` - flips status to `in_progress`, returns
   immediately, and runs the graph as a FastAPI `BackgroundTask`.
3. The background task creates a sandbox copy of `sample_project/`, streams
   the compiled graph node-by-node (recording a `WorkflowEvent` per node -
   see `docs/observability.md`), and persists the final `IncidentState` -
   including a `FAILED` state if the graph itself raised, so a real error is
   recorded, never silently lost.
4. The client polls `GET /incidents/{id}` until status is no longer
   `new`/`in_progress`.
5. If `awaiting_approval`: `POST /incidents/{id}/approve {"approved": true|false}`.
   `true` copies the fixed file from the sandbox into the real
   `sample_project/` and marks the incident `resolved`. `false` leaves it
   untouched and marks it `failed`. Either way the sandbox is then cleaned up.

## Why each layer exists (and what was deliberately left out)

- **FastAPI**, not Flask/Django: async-native, built-in OpenAPI docs,
  minimal boilerplate for the handful of endpoints this needs.
- **SQLite by default**: zero setup for a learning project; `DATABASE_URL`
  swaps to Postgres with no code change (`backend/app/db/database.py`).
- **FastAPI `BackgroundTasks`**, not Celery/a task queue: one function call
  is enough for "run this after the response is sent" - a queue, broker,
  and worker process would be infrastructure this project doesn't need.
- **LangGraph**, not a hand-rolled loop: the retry/approve/fail branching
  after Review is a real graph routing decision, and LangGraph's
  `StateGraph` makes that explicit and testable (`route_after_review` in
  `backend/app/graph/workflow.py`) rather than buried in if/else.
- **Chroma in-memory**, not a persistent vector DB: the knowledge base is
  re-ingested at startup (`backend/app/main.py`); nothing needs it to
  survive a restart on its own.
- **No React Router, no state-management library**: the frontend has
  exactly two views (list, detail); a boolean bit of state in `App.jsx`
  is simpler and equally correct.

This reasoning is also repeated in the relevant code's own docstrings
rather than living only here - e.g. `backend/app/agents/workspace.py`'s
module docstring, `backend/app/api/routes.py`'s module docstring.
