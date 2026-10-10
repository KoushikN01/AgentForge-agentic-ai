# Observability

Deliberately lightweight: structured per-node workflow events and Python
logging, not an external tracing service. "Prefer structured logs over
unnecessary infrastructure" is the same judgment this project applies to
Celery/Kubernetes/etc elsewhere.

## Workflow events (the timeline)

Each incident's `IncidentState.events` (`backend/app/models/events.py`'s
`WorkflowEvent`) is a list of:

```python
class WorkflowEvent(BaseModel):
    node: str           # "investigation", "coding", "review", ...
    status: str          # "completed" or "failed"
    timestamp: str        # ISO 8601
    duration_ms: float
    detail: str | None    # populated on "failed"
```

Populated by `backend/app/api/routes.py`'s `_run_investigation`, which
runs the compiled graph via `graph.stream(..., stream_mode="updates")`
instead of a single `.invoke()` - this yields control back after every
node, so each node's wall-clock duration can actually be measured, not
estimated. If the graph raises, a `status="failed"` event with the
exception message is recorded instead of the crash being silently lost -
see the `except` branch in `_run_investigation`.

Exposed via `GET /incidents/{id}/timeline`, and rendered in the frontend's
`Timeline.jsx` ("Activity" section) alongside the existing
`IncidentState.messages` log (the human-readable narration each agent
already appends to - "Debugging: root cause = ... (confidence 0.90)").

This answers every item the project's observability requirement asks
for: incident ID (the URL/the record itself), workflow run (one
`IncidentState` per investigation), agent/node name, start/completion/
failure, duration, and final state - all without adding a tracing
backend.

## Logging

`backend/app/core/logging_config.py`'s `get_logger(__name__)` gives every
module a logger with a consistent `time | level | module | message`
format, configured once from `LOG_LEVEL` (`.env.example`). Gemini calls
log their model name and call type (never the API key -
`app/llm/gemini.py` never includes `config.gemini_api_key` in a log line).

## What's genuinely not done

No metrics/counters (request rates, token usage, cost per incident), no
distributed tracing, no log aggregation or a dashboard beyond the
frontend's own Activity section, and no export to an external service.
`langsmith` is installed (a dependency of `langgraph` itself) but never
configured or used - this project makes zero calls to any LangSmith
endpoint. All of this would be legitimate production hardening; none of
it was needed to demonstrate the concept, which is why it isn't here.
