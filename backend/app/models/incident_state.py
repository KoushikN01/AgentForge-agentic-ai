"""
Core data models for AgentForge.

`IncidentState` is the object that flows through the LangGraph workflow
(app/graph/workflow.py) - each agent node reads it and returns updates.
Fields were added only when the phase that uses them was built:
  - Phase 1: incident, messages
  - Phase 4: evidence, knowledge_context, root_cause, patch_proposal,
    test_result, review_result, retry_count, retry_feedback
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.agent_outputs import PatchProposal, ReviewResult, RootCauseAnalysis, TestOutcome
from app.models.events import WorkflowEvent


class Severity(str, Enum):
    """How serious the reported incident is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """
    Where an incident is in its lifecycle.

    Only NEW and IN_PROGRESS are reachable in Phase 1 (there's no
    investigation workflow yet to reach the other states). RESOLVED and
    FAILED are defined now because they're part of the incident's *data
    model*, not part of a workflow we haven't built — the multi-agent
    graph in a later phase will be what actually sets them.
    """

    NEW = "new"
    IN_PROGRESS = "in_progress"
    # The graph's honest stopping point: a passing, review-approved fix
    # exists in the sandbox, but a human has not yet decided.
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    FAILED = "failed"


class Incident(BaseModel):
    """A single reported incident, e.g. 'login endpoint returns 500'."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    severity: Severity = Severity.MEDIUM
    status: IncidentStatus = IncidentStatus.NEW
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentState(BaseModel):
    """
    Shared state for one incident's investigation.

    This is the object that will flow through the LangGraph workflow in a
    later phase — each agent reads from it and adds to it. For now it just
    wraps the incident itself plus a running log of what's happened, since
    that's the only "workflow" that exists yet.
    """

    incident: Incident
    # A simple running log, e.g. "Incident created", "Investigation started".
    # Later phases will use this same list for agent-to-agent messages.
    messages: list[str] = Field(default_factory=list)

    # --- Added in Phase 4, populated by the LangGraph agent workflow ---
    evidence: list[str] = Field(default_factory=list)  # Investigation Agent's raw findings
    knowledge_context: list[str] = Field(default_factory=list)  # Knowledge/RAG Agent's snippets
    root_cause: RootCauseAnalysis | None = None  # Debugging Agent's diagnosis
    patch_proposal: PatchProposal | None = None  # Coding Agent's proposed fix
    test_result: TestOutcome | None = None  # result of testing the fix in the sandbox
    review_result: ReviewResult | None = None  # Review Agent's verdict
    retry_count: int = 0
    retry_feedback: str | None = None  # why the previous attempt wasn't good enough

    # --- Added in the final completion phase ---
    # Where this incident's sandbox copy of sample_project currently lives.
    # Stored on the state (and so persisted to the DB) rather than kept only
    # in an in-process dict, so GET/POST /incidents/{id}/approve can find it
    # even if the API process restarted since the investigation ran.
    workspace_path: str | None = None
    # One entry per graph node that ran, for GET /incidents/{id}/timeline.
    events: list[WorkflowEvent] = Field(default_factory=list)

    def add_message(self, message: str) -> None:
        self.messages.append(message)
