"""
Workflow observability events.

A WorkflowEvent is one structured record of "this node ran, this is how
long it took" - the minimum needed to answer "what did the workflow
actually do for this incident, and how long did each step take" without
an external tracing service. Collected by app/api/routes.py's
_run_investigation (which streams the graph node-by-node instead of a
single invoke()) and app/models/incident_state.IncidentState.events, and
exposed via GET /incidents/{id}/timeline.
"""

from pydantic import BaseModel


class WorkflowEvent(BaseModel):
    node: str  # which graph node this is about, e.g. "coding"
    status: str  # "completed" or "failed"
    timestamp: str  # ISO 8601, when the node finished
    duration_ms: float
    detail: str | None = None  # populated on status == "failed"
