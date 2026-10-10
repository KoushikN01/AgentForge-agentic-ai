"""
The incident API.

    POST   /incidents                    create an incident (status: new)
    POST   /incidents/{id}/investigate    kick off the multi-agent workflow (background)
    GET    /incidents                     list incidents
    GET    /incidents/{id}                full current state
    GET    /incidents/{id}/evidence       what the Investigation Agent found
    GET    /incidents/{id}/patch          the Coding Agent's proposed fix
    GET    /incidents/{id}/timeline       structured per-node workflow events
    POST   /incidents/{id}/approve        the human-in-the-loop gate ({"approved": true|false})
    POST   /incidents/{id}/reject         sugar for approve with approved=false
    GET    /incidents/{id}/report         a flattened final report

/investigate runs the LangGraph workflow (Phase 4) as a FastAPI
BackgroundTask, so the request returns immediately with status
"in_progress" and the caller polls GET /incidents/{id} for progress -
this is what makes the status-checking endpoint meaningful, rather than
just re-reporting a result the first request already had. It is plain
FastAPI BackgroundTasks, not Celery or any task queue - one function call,
matching the project's "no unnecessary infrastructure" principle.

The sandbox workspace for an incident's investigation is recorded on
IncidentState.workspace_path (so it's persisted to the DB with everything
else) rather than kept only in an in-process dict - this means POST
/approve can still find and use the sandbox even if the API process
restarted since /investigate ran. The sandbox itself (the temp directory's
files) does NOT survive a restart - only its path is remembered, so a
restart mid-investigation still means that investigation must be re-run
(a new, fresh sandbox) - seeapp/agents/workspace.py and
BUILD_VERIFICATION.md for what this does and doesn't solve.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.human_approval import apply_human_decision
from app.agents.workspace import cleanup_workspace, create_incident_workspace
from app.api.deps import get_db
from app.api.schemas import ApprovalRequest, CreateIncidentRequest, FinalReportResponse, IncidentSummaryResponse
from app.db import repository
from app.db.models import IncidentRecord
from app.graph.workflow import build_graph
from app.llm.gemini import GeminiClient
from app.models.agent_outputs import PatchProposal
from app.models.events import WorkflowEvent
from app.models.incident_state import Incident, IncidentState, IncidentStatus

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _run_investigation(
    incident_id: str,
    session_factory,
    gemini_client: GeminiClient,
    kb_collection,
    sample_project_root: Path,
    knowledge_base_root: Path | None,
    rag_mode: str,
) -> None:
    """
    The background task: build a fresh sandbox, run the compiled graph
    node-by-node (via .stream(), not .invoke()) so each node's completion
    can be timed and recorded as a WorkflowEvent, and persist whatever
    state results - including a FAILED state if the graph itself raises,
    so a real error (a Gemini failure, a bug) is recorded and visible via
    GET /incidents/{id}, never silently lost.
    """
    with session_factory() as session:
        state = repository.load_state(session, incident_id)
        if state is None:
            return

        workspace = create_incident_workspace(sample_project_root)
        # Persist the workspace path immediately, before the graph runs,
        # so it's recoverable even if the process restarts mid-run.
        state = state.model_copy(update={"workspace_path": str(workspace)})
        repository.save_state(session, state)

        graph = build_graph(
            gemini_client, kb_collection, sample_project_root, workspace, knowledge_base_root, rag_mode
        )

        events: list[WorkflowEvent] = []
        last_tick = time.monotonic()
        try:
            merged: dict = {}
            for update in graph.stream(state, stream_mode="updates"):
                for node_name, node_update in update.items():
                    now = time.monotonic()
                    events.append(
                        WorkflowEvent(
                            node=node_name,
                            status="completed",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            duration_ms=round((now - last_tick) * 1000, 1),
                        )
                    )
                    last_tick = now
                    merged.update(node_update)
            final_state = state.model_copy(update=merged)
            final_state = final_state.model_copy(update={"events": state.events + events})
        except Exception as exc:  # noqa: BLE001 - record the real failure, don't hide it
            events.append(
                WorkflowEvent(
                    node="workflow",
                    status="failed",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    duration_ms=round((time.monotonic() - last_tick) * 1000, 1),
                    detail=str(exc),
                )
            )
            final_state = state.model_copy(
                update={
                    "incident": state.incident.model_copy(update={"status": IncidentStatus.FAILED}),
                    "messages": state.messages + [f"Investigation crashed: {exc}"],
                    "events": state.events + events,
                }
            )

        repository.save_state(session, final_state)

        # A FAILED outcome never reaches human approval, so the sandbox
        # holds nothing anything will read again - safe to clean up now.
        # AWAITING_APPROVAL must keep its sandbox; approve_incident()
        # cleans that one up after the human decides.
        if final_state.incident.status == IncidentStatus.FAILED and final_state.workspace_path:
            cleanup_workspace(Path(final_state.workspace_path))


def _require_state(db: Session, incident_id: str) -> IncidentState:
    state = repository.load_state(db, incident_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return state


def _to_summary(state: IncidentState) -> IncidentSummaryResponse:
    return IncidentSummaryResponse(
        id=state.incident.id,
        title=state.incident.title,
        status=state.incident.status.value,
        retry_count=state.retry_count,
        created_at=state.incident.created_at,
    )


def _record_to_summary(record: IncidentRecord) -> IncidentSummaryResponse:
    return IncidentSummaryResponse(
        id=record.id, title=record.title, status=record.status,
        retry_count=record.retry_count, created_at=record.created_at,
    )


def _to_report(state: IncidentState) -> FinalReportResponse:
    return FinalReportResponse(
        incident_id=state.incident.id,
        title=state.incident.title,
        severity=state.incident.severity.value,
        status=state.incident.status.value,
        root_cause=state.root_cause.root_cause if state.root_cause else None,
        confidence=state.root_cause.confidence if state.root_cause else None,
        proposed_fix=state.patch_proposal.explanation if state.patch_proposal else None,
        target_file=state.patch_proposal.target_file if state.patch_proposal else None,
        test_summary=state.test_result.summary if state.test_result else None,
        review_approved=state.review_result.approved if state.review_result else None,
        retry_count=state.retry_count,
    )


def _decide_approval(incident_id: str, request: Request, db: Session, approved: bool) -> FinalReportResponse:
    state = _require_state(db, incident_id)
    if state.incident.status != IncidentStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409, detail=f"Incident is not awaiting approval (status={state.incident.status.value})"
        )
    if not state.workspace_path:
        raise HTTPException(status_code=500, detail="No sandbox workspace recorded for this incident")

    workspace = Path(state.workspace_path)
    resolved = apply_human_decision(state, request.app.state.sample_project_root, workspace, approved=approved)
    repository.save_state(db, resolved)
    repository.record_approval(db, incident_id, approved)
    cleanup_workspace(workspace)  # the decision is made either way - the sandbox is no longer needed
    return _to_report(resolved)


@router.post("", response_model=IncidentSummaryResponse, status_code=201)
def create_incident(payload: CreateIncidentRequest, db: Session = Depends(get_db)):
    incident = Incident(title=payload.title, description=payload.description, severity=payload.severity)
    state = IncidentState(incident=incident)
    repository.save_state(db, state)
    return _to_summary(state)


@router.post("/{incident_id}/investigate", response_model=IncidentSummaryResponse)
def start_investigation(incident_id: str, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    state = _require_state(db, incident_id)
    if state.incident.status != IncidentStatus.NEW:
        raise HTTPException(status_code=409, detail=f"Incident is already {state.incident.status.value}")

    app_state = request.app.state
    in_progress = state.model_copy(
        update={"incident": state.incident.model_copy(update={"status": IncidentStatus.IN_PROGRESS})}
    )
    repository.save_state(db, in_progress)

    background_tasks.add_task(
        _run_investigation,
        incident_id,
        app_state.session_factory,
        app_state.gemini_client,
        app_state.kb_collection,
        app_state.sample_project_root,
        app_state.knowledge_base_root,
        app_state.rag_mode,
    )
    return _to_summary(in_progress)


@router.get("", response_model=list[IncidentSummaryResponse])
def list_incidents(db: Session = Depends(get_db)):
    return [_record_to_summary(r) for r in repository.list_incident_records(db)]


@router.get("/{incident_id}", response_model=IncidentState)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    return _require_state(db, incident_id)


@router.get("/{incident_id}/evidence", response_model=list[str])
def get_evidence(incident_id: str, db: Session = Depends(get_db)):
    return _require_state(db, incident_id).evidence


@router.get("/{incident_id}/patch", response_model=PatchProposal)
def get_patch(incident_id: str, db: Session = Depends(get_db)):
    state = _require_state(db, incident_id)
    if state.patch_proposal is None:
        raise HTTPException(status_code=404, detail="No patch has been proposed yet")
    return state.patch_proposal


@router.get("/{incident_id}/timeline", response_model=list[WorkflowEvent])
def get_timeline(incident_id: str, db: Session = Depends(get_db)):
    return _require_state(db, incident_id).events


@router.post("/{incident_id}/approve", response_model=FinalReportResponse)
def approve_incident(incident_id: str, payload: ApprovalRequest, request: Request, db: Session = Depends(get_db)):
    return _decide_approval(incident_id, request, db, approved=payload.approved)


@router.post("/{incident_id}/reject", response_model=FinalReportResponse)
def reject_incident(incident_id: str, request: Request, db: Session = Depends(get_db)):
    """Sugar for POST /approve {"approved": false} - same safety path, no real-project change."""
    return _decide_approval(incident_id, request, db, approved=False)


@router.get("/{incident_id}/report", response_model=FinalReportResponse)
def get_report(incident_id: str, db: Session = Depends(get_db)):
    return _to_report(_require_state(db, incident_id))
