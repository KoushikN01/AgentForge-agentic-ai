"""
Supervisor Agent.

Deliberately the simplest node: it marks the incident as being worked on
and lets LangGraph's static edges (app/graph/workflow.py) route onward.
This workflow is linear enough (every incident goes investigate -> retrieve
-> debug -> code -> test -> review) that dynamic routing here would be
complexity without benefit. The one place the graph DOES branch is after
Review (route_after_review in workflow.py), where a real routing decision
is needed: approve, retry, or give up.
"""

from app.models.incident_state import IncidentState, IncidentStatus


def start_investigation(state: IncidentState) -> dict:
    return {
        "incident": state.incident.model_copy(update={"status": IncidentStatus.IN_PROGRESS}),
        "messages": state.messages + [f"Investigation started for: {state.incident.title}"],
    }
