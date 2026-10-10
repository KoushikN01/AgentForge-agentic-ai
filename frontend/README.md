# AgentForge frontend

A small React + Vite single-page app for the AgentForge API
(`../backend`) - a dashboard to report incidents, watch the multi-agent
investigation run, and approve or reject the proposed fix. No router
library, no state-management library, no component framework: a handful
of components and `fetch`, because that's all this actually needs.

## Running it

```bash
npm install
npm run dev       # http://localhost:5173
```

The backend must already be running on `http://localhost:8000` (see
`../backend/app/main.py` / the root `README.md`), and must have been
started with CORS allowing `http://localhost:5173` (the default - see
`backend/app/api/app_factory.py`).

## What it does, and doesn't, verify

This was built and `npm run build` was verified to succeed (see the
project's `BUILD_VERIFICATION.md`) - that proves the code compiles
correctly: every import resolves, JSX is valid, there are no syntax
errors. It does **not** prove the UI looks right or behaves correctly
when clicked through in a real browser - that needs a human (or a browser
automation tool neither available nor used here). Run it yourself with
`npm run dev` and a real backend to see it work end to end.

## Structure

```
src/
  api.js                     fetch wrapper - the ONLY file that knows the API's URLs/shapes
  App.jsx                    switches between the dashboard and incident-detail views
  components/
    Dashboard.jsx             incident list + "report an incident" form
    IncidentDetail.jsx        polls one incident, renders every section below
    StatusBadge.jsx           small colored status pill
    Timeline.jsx              the per-node workflow events (GET /incidents/{id}/timeline)
```

## The approval boundary

`IncidentDetail` only renders an enabled "Approve" / "Reject" action when
the backend reports `status === "awaiting_approval"` - never earlier, and
never by guessing. Approving calls `POST /incidents/{id}/approve`, the
same endpoint and the same `apply_human_decision()` safety path the
backend's own tests exercise; the frontend has no code path that touches
`sample_project/` directly or bypasses that endpoint.
