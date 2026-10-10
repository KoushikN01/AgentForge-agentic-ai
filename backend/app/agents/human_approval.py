"""
Human-in-the-loop.

Two graph TERMINAL nodes (mark_awaiting_approval, mark_failed) only record
where the automated workflow stopped - they change nothing in the real
world. The actual "final action" - applying an approved patch to the real
sample project - happens in apply_human_decision(), deliberately NOT a
graph node: it's a plain function you call after a human has looked at the
AWAITING_APPROVAL state and decided.

    graph result: status == AWAITING_APPROVAL
        | a human inspects patch_proposal, test_result, review_result
    apply_human_decision(state, ..., approved=True/False)
        |
    RESOLVED (real project updated)  or  FAILED (real project untouched)
"""

from pathlib import Path

from app.agents.workspace import apply_patch_to_real_project
from app.models.incident_state import IncidentState, IncidentStatus


def mark_awaiting_approval(state: IncidentState) -> dict:
    return {
        "incident": state.incident.model_copy(update={"status": IncidentStatus.AWAITING_APPROVAL}),
        "messages": state.messages + ["Fix passed tests and review - awaiting human approval"],
    }


def mark_failed(state: IncidentState) -> dict:
    return {
        "incident": state.incident.model_copy(update={"status": IncidentStatus.FAILED}),
        "messages": state.messages + [f"Investigation failed after {state.retry_count} retry/retries"],
    }


def apply_human_decision(
    state: IncidentState, sample_project_root: Path, workspace_root: Path, approved: bool
) -> IncidentState:
    """
    approved=True copies the fixed file from the sandbox into the real
    project (the only path in the codebase that modifies it) and marks the
    incident RESOLVED. approved=False leaves the real project untouched and
    marks it FAILED - a human rejecting a passing fix is a legitimate,
    final outcome, not an error.
    """
    if not approved:
        return state.model_copy(
            update={
                "incident": state.incident.model_copy(update={"status": IncidentStatus.FAILED}),
                "messages": state.messages + ["Human rejected the proposed fix - not applied"],
            }
        )

    if state.patch_proposal is None:
        raise ValueError("Cannot approve - there is no patch_proposal on this state.")

    apply_patch_to_real_project(sample_project_root, workspace_root, state.patch_proposal.target_file)
    return state.model_copy(
        update={
            "incident": state.incident.model_copy(update={"status": IncidentStatus.RESOLVED}),
            "messages": state.messages
            + [f"Human approved - {state.patch_proposal.target_file} applied to the real project"],
        }
    )
