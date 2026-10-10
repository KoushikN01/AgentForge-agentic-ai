"""
SQLAlchemy table definitions.

Two tables, matching the project's actual needs rather than a fully
normalized schema for every nested field (the spec asks to "keep the
schema understandable"):

- `incidents`: one row per incident. The full IncidentState (evidence,
  root cause, patch, test result, review result, messages - everything)
  is stored as JSON in `state_json`, so the rest of the app has one
  source of truth (the Pydantic model) instead of two schemas to keep in
  sync. The plain columns (title, status, ...) are duplicated out of that
  JSON purely so they can be queried/sorted/filtered without parsing JSON
  for every row in `GET /incidents`.
- `approvals`: one row per human approve/reject decision - kept separate
  because it's a distinct real-world event (who/when/what was decided),
  not a property of the incident itself.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    status = Column(String, nullable=False)
    retry_count = Column(Integer, nullable=False, default=0)
    state_json = Column(Text, nullable=False)  # the full IncidentState, as JSON
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String, nullable=False)
    approved = Column(Boolean, nullable=False)
    decided_at = Column(DateTime, default=_utcnow)
