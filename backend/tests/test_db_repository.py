"""
Tests for the database layer. Real SQLite (in-memory, shared via
StaticPool), no mocking - genuinely exercises SQLAlchemy.
"""

import pytest

from app.db import repository
from app.db.database import create_session_factory
from app.models.incident_state import Incident, IncidentState, IncidentStatus


@pytest.fixture
def session():
    factory = create_session_factory("sqlite:///:memory:")
    with factory() as s:
        yield s


def make_state(**overrides) -> IncidentState:
    incident = Incident(title="Login returns 500", description="details")
    return IncidentState(incident=incident, **overrides)


def test_save_and_load_round_trips_full_state(session):
    state = make_state(evidence=["log line 1"], messages=["started"])

    repository.save_state(session, state)
    loaded = repository.load_state(session, state.incident.id)

    assert loaded == state


def test_load_returns_none_for_unknown_id(session):
    assert repository.load_state(session, "does-not-exist") is None


def test_save_state_twice_updates_the_same_row(session):
    state = make_state()
    repository.save_state(session, state)

    updated = state.model_copy(
        update={
            "incident": state.incident.model_copy(update={"status": IncidentStatus.IN_PROGRESS}),
            "evidence": ["new evidence"],
        }
    )
    repository.save_state(session, updated)

    loaded = repository.load_state(session, state.incident.id)
    assert loaded.incident.status == IncidentStatus.IN_PROGRESS
    assert loaded.evidence == ["new evidence"]
    assert len(repository.list_incident_records(session)) == 1  # not a second row


def test_list_incident_records_returns_all_saved_incidents(session):
    repository.save_state(session, make_state())
    repository.save_state(session, make_state())

    records = repository.list_incident_records(session)

    assert len(records) == 2


def test_record_and_list_approvals(session):
    state = make_state()
    repository.save_state(session, state)

    repository.record_approval(session, state.incident.id, approved=False)
    repository.record_approval(session, state.incident.id, approved=True)

    approvals = repository.list_approvals(session, state.incident.id)
    assert [a.approved for a in approvals] == [False, True]
