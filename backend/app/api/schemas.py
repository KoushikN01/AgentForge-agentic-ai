"""
Request/response schemas for the API boundary.

IncidentState itself (app/models/incident_state.py) is returned directly
from GET /incidents/{id} - it's already a Pydantic model with everything
a client would want, and duplicating every one of its fields into a
second "response" schema would be exactly the kind of needless
abstraction the project avoids. These few schemas exist only where the
API's shape genuinely differs from the internal model: creating an
incident (no id/status yet), approving one (just a boolean), a slimmer
row for listing many incidents, and a flattened final report.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.incident_state import Severity


class CreateIncidentRequest(BaseModel):
    title: str
    description: str
    severity: Severity = Severity.MEDIUM


class ApprovalRequest(BaseModel):
    approved: bool


class IncidentSummaryResponse(BaseModel):
    id: str
    title: str
    status: str
    retry_count: int
    created_at: datetime


class FinalReportResponse(BaseModel):
    """Flattened for a client that just wants the outcome, not the whole state."""

    incident_id: str
    title: str
    severity: str
    status: str
    root_cause: str | None
    confidence: float | None
    proposed_fix: str | None
    target_file: str | None
    test_summary: str | None
    review_approved: bool | None
    retry_count: int
