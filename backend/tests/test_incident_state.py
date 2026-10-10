"""
Tests for app.models.incident_state.

Pure Pydantic model tests — no Gemini, no network.
"""

import pytest
from pydantic import ValidationError

from app.models.incident_state import Incident, IncidentState, IncidentStatus, Severity


def test_incident_gets_default_id_status_and_severity():
    incident = Incident(
        title="Login returns 500",
        description="POST /api/users/login started failing after deploy.",
    )

    assert incident.id  # a uuid string was generated
    assert incident.status == IncidentStatus.NEW
    assert incident.severity == Severity.MEDIUM
    assert incident.created_at is not None


def test_incident_requires_title_and_description():
    with pytest.raises(ValidationError):
        Incident(title="Missing description")


def test_incident_severity_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Incident(
            title="x",
            description="y",
            severity="catastrophic",  # not a real Severity value
        )


def test_incident_state_wraps_incident_and_starts_with_no_messages():
    incident = Incident(title="x", description="y")
    state = IncidentState(incident=incident)

    assert state.incident == incident
    assert state.messages == []


def test_incident_state_add_message_appends():
    incident = Incident(title="x", description="y")
    state = IncidentState(incident=incident)

    state.add_message("Incident created")
    state.add_message("Investigation started")

    assert state.messages == ["Incident created", "Investigation started"]
