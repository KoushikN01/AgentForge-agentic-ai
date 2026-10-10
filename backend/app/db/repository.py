"""
The one place that translates between IncidentState (the app's Pydantic
model, used everywhere else) and IncidentRecord (the SQLAlchemy row).
Nothing outside this module touches SQLAlchemy models directly.
"""

from sqlalchemy.orm import Session

from app.db.models import ApprovalRecord, IncidentRecord
from app.models.incident_state import IncidentState


def save_state(session: Session, state: IncidentState) -> None:
    """Insert or update the row for state.incident.id with its full current state."""
    record = session.get(IncidentRecord, state.incident.id)
    if record is None:
        record = IncidentRecord(id=state.incident.id)
        session.add(record)

    record.title = state.incident.title
    record.severity = state.incident.severity.value
    record.status = state.incident.status.value
    record.retry_count = state.retry_count
    record.state_json = state.model_dump_json()
    session.commit()


def load_state(session: Session, incident_id: str) -> IncidentState | None:
    record = session.get(IncidentRecord, incident_id)
    if record is None:
        return None
    return IncidentState.model_validate_json(record.state_json)


def list_incident_records(session: Session) -> list[IncidentRecord]:
    return session.query(IncidentRecord).order_by(IncidentRecord.created_at.desc()).all()


def record_approval(session: Session, incident_id: str, approved: bool) -> None:
    session.add(ApprovalRecord(incident_id=incident_id, approved=approved))
    session.commit()


def list_approvals(session: Session, incident_id: str) -> list[ApprovalRecord]:
    return (
        session.query(ApprovalRecord)
        .filter(ApprovalRecord.incident_id == incident_id)
        .order_by(ApprovalRecord.decided_at)
        .all()
    )
